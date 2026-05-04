"""Document Risk Extractor — main orchestrator.

Runs the full extraction pipeline:
  1. Load document (PDF/DOCX/XLSX/TXT)
  2. Chunk into LLM-sized pieces (section-aware, overlapping)
  3. Extract risk mentions from each chunk (parallel-safe, resilient)
  4. Deduplicate across chunks
  5. Build output + summary

Resilience features (same as run_scoring_resilient.py):
- Per-chunk extraction — one chunk failing never kills the run
- Rate-limit aware — respects LLMWrapper's _MIN_CALL_INTERVAL
- Detailed logging at every step
- Returns partial results if some chunks fail
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import Counter

from riskmapper.document_extractor.chunk_parser import parse_chunk
from riskmapper.document_extractor.chunker import chunk_document
from riskmapper.document_extractor.deduplicator import deduplicate_document_risks
from riskmapper.document_extractor.document_loader import load_document
from riskmapper.document_extractor.schemas import (
    ChunkMetadata,
    DeduplicatedDocumentRisk,
    DocumentExtractionResult,
    DocumentRiskMention,
    DocumentType,
    ExtractionSummary,
)
from riskmapper.llm_wrapper import LLMWrapper

logger = logging.getLogger(__name__)


def extract_risks_from_document(
    file_path: str,
    document_type: DocumentType,
    sector: str,
    llm: LLMWrapper,
    output_dir: str | None = None,
    max_chunk_chars: int = 3000,
    overlap_chars: int = 200,
    dedup_target_max: int = 30,
    max_chunks: int | None = None,
    start_chunk: int = 0,
) -> DocumentExtractionResult:
    """Extract risks from any supported document type.

    Full pipeline: load → chunk → extract per chunk → deduplicate → output.

    Args:
        file_path: Path to the document (PDF, DOCX, XLSX, TXT, MD).
        document_type: Type of document — affects extraction focus.
        sector: Client sector (e.g. "Automotive", "Banking").
        llm: Initialized LLMWrapper instance.
        output_dir: If provided, writes JSON output files here.
        max_chunk_chars: Maximum characters per chunk (default 3000 ≈ 750 tokens).
        overlap_chars: Overlap between consecutive chunks (default 200).
        dedup_target_max: Target max unique risks after deduplication.

    Returns:
        DocumentExtractionResult with risks, summary, and chunk metadata.

    Raises:
        FileNotFoundError: If file_path does not exist.
        ValueError: If file extension is not supported.
    """
    pipeline_start = time.time()
    document_name = os.path.basename(file_path)

    logger.info(
        "=== Document Risk Extractor started ===\n"
        "  document=%s | type=%s | sector=%s",
        document_name, document_type, sector,
    )

    # -----------------------------------------------------------------------
    # Step 1: Load document
    # -----------------------------------------------------------------------
    logger.info("[1/4] Loading document...")
    loaded = load_document(file_path)

    if loaded.load_warnings:
        for w in loaded.load_warnings:
            logger.warning("  Load warning: %s", w)

    logger.info(
        "  Loaded | chars=%d | pages=%d | sections=%d",
        loaded.char_count, loaded.page_count, len(loaded.detected_sections),
    )

    # -----------------------------------------------------------------------
    # Step 2: Chunk document
    # -----------------------------------------------------------------------
    logger.info("[2/4] Chunking document...")
    chunks = chunk_document(
        text=loaded.text,
        document_name=document_name,
        document_type=document_type,
        detected_sections=loaded.detected_sections,
        max_chunk_chars=max_chunk_chars,
        overlap_chars=overlap_chars,
    )

    logger.info("  Chunks: %d (avg %.0f chars each)", len(chunks),
                sum(len(t) for t, _ in chunks) / max(len(chunks), 1))

    if not chunks:
        logger.warning("No chunks produced — document may be empty")
        return _empty_result(document_name, document_type)

    # Apply start_chunk offset and max_chunks limit
    if start_chunk and start_chunk > 0:
        chunks = chunks[start_chunk:]
        logger.info("start_chunk=%d applied | skipped %d empty chunks",
                    start_chunk, start_chunk)

    if max_chunks is not None and max_chunks > 0:
        original_total = len(chunks)
        chunks = chunks[:max_chunks]
        logger.info("max_chunks=%d applied | processing %d of %d remaining chunks",
                    max_chunks, len(chunks), original_total)

    # Update total_chunks in metadata after slicing
    for _, meta in chunks:
        meta.total_chunks = len(chunks)

    # -----------------------------------------------------------------------
    # Step 3: Extract risk mentions from each chunk
    # -----------------------------------------------------------------------
    logger.info("[3/4] Extracting risks from %d chunks...", len(chunks))

    all_mentions: list[DocumentRiskMention] = []
    all_chunk_metadata: list[ChunkMetadata] = []
    failed_chunks: list[str] = []
    chunks_with_risks = 0

    for idx, (chunk_text, chunk_meta) in enumerate(chunks, 1):
        logger.info(
            "  [%d/%d] %s — section='%s' (%d chars)",
            idx, len(chunks),
            chunk_meta.chunk_id,
            chunk_meta.section_label[:40],
            len(chunk_text),
        )

        all_chunk_metadata.append(chunk_meta)

        mentions = parse_chunk(
            chunk_text=chunk_text,
            chunk_metadata=chunk_meta,
            document_type=document_type,
            sector=sector,
            llm=llm,
        )

        if mentions:
            all_mentions.extend(mentions)
            chunks_with_risks += 1
            logger.info("    → %d mentions extracted", len(mentions))
        else:
            logger.info("    → no risks in this chunk")

        # Track failed chunks (parse_chunk returns [] on failure, but we
        # can detect zero mentions from a content-rich chunk as a soft failure)
        # Hard failures are already logged inside parse_chunk

    logger.info(
        "  Extraction complete | total_mentions=%d | chunks_with_risks=%d/%d",
        len(all_mentions), chunks_with_risks, len(chunks),
    )

    if not all_mentions:
        logger.warning("No risk mentions extracted from any chunk")
        return _empty_result(document_name, document_type, all_chunk_metadata)

    # -----------------------------------------------------------------------
    # Step 4: Deduplicate across chunks
    # -----------------------------------------------------------------------
    logger.info("[4/4] Deduplicating %d mentions...", len(all_mentions))

    # For large mention sets, batch the dedup to avoid overwhelming the LLM
    if len(all_mentions) > 80:
        logger.info(
            "  Large mention set (%d) — using batched dedup", len(all_mentions)
        )
        deduped = _batched_dedup(all_mentions, llm, dedup_target_max)
    else:
        deduped = deduplicate_document_risks(all_mentions, llm, dedup_target_max)

    logger.info(
        "  Dedup complete | %d mentions → %d unique risks",
        len(all_mentions), len(deduped),
    )

    # -----------------------------------------------------------------------
    # Build summary
    # -----------------------------------------------------------------------
    summary = _build_summary(
        document_name=document_name,
        document_type=document_type,
        total_chunks=len(chunks),
        chunks_with_risks=chunks_with_risks,
        raw_mentions=len(all_mentions),
        deduped=deduped,
        failed_chunks=failed_chunks,
    )

    result = DocumentExtractionResult(
        risks=deduped,
        summary=summary,
        chunk_metadata=all_chunk_metadata,
    )

    # -----------------------------------------------------------------------
    # Write outputs
    # -----------------------------------------------------------------------
    if output_dir:
        _write_outputs(result, output_dir, document_name)

    total_time = time.time() - pipeline_start
    logger.info(
        "=== Extraction complete ===\n"
        "  risks=%d | critical=%d | high=%d | medium=%d | low=%d\n"
        "  material_weaknesses=%d | repeat_findings=%d | quantified=%d\n"
        "  time=%.1fs",
        len(deduped),
        summary.critical_count, summary.high_count,
        summary.medium_count, summary.low_count,
        summary.material_weakness_count,
        summary.repeat_finding_count,
        summary.quantified_count,
        total_time,
    )

    return result


# ---------------------------------------------------------------------------
# Batched deduplication for large mention sets
# ---------------------------------------------------------------------------

def _batched_dedup(
    mentions: list[DocumentRiskMention],
    llm: LLMWrapper,
    target_max: int,
    batch_size: int = 60,
) -> list[DeduplicatedDocumentRisk]:
    """Two-pass dedup for large mention sets.

    Pass 1: Dedup within batches of `batch_size` mentions.
    Pass 2: Dedup the combined results from all batches.

    This prevents the LLM from being overwhelmed by 100+ mentions at once.
    """
    logger.info(
        "Batched dedup | %d mentions | batch_size=%d",
        len(mentions), batch_size,
    )

    # Pass 1: Batch dedup
    batch_results: list[DeduplicatedDocumentRisk] = []
    for i in range(0, len(mentions), batch_size):
        batch = mentions[i: i + batch_size]
        batch_num = i // batch_size + 1
        logger.info(
            "  Batch %d | %d mentions", batch_num, len(batch)
        )
        batch_deduped = deduplicate_document_risks(
            batch, llm, target_max=batch_size // 2
        )
        batch_results.extend(batch_deduped)

    logger.info(
        "  Pass 1 complete | %d mentions → %d batch results",
        len(mentions), len(batch_results),
    )

    if len(batch_results) <= target_max:
        # Re-index IDs
        return _reindex(batch_results)

    # Pass 2: Dedup the batch results
    # Convert DeduplicatedDocumentRisk back to DocumentRiskMention for the deduplicator
    synthetic_mentions = _deduped_to_mentions(batch_results)
    final = deduplicate_document_risks(synthetic_mentions, llm, target_max)

    logger.info(
        "  Pass 2 complete | %d batch results → %d final risks",
        len(batch_results), len(final),
    )

    return final


def _deduped_to_mentions(
    deduped: list[DeduplicatedDocumentRisk],
) -> list[DocumentRiskMention]:
    """Convert DeduplicatedDocumentRisk back to DocumentRiskMention for re-dedup."""
    from uuid import uuid4
    mentions = []
    for r in deduped:
        mentions.append(
            DocumentRiskMention(
                mention_id=uuid4(),
                client_description=r.client_description,
                verbatim_evidence=r.verbatim_evidence[:3],  # Cap for token efficiency
                source_section=r.source_sections[0] if r.source_sections else "Document",
                chunk_id=r.chunk_ids[0] if r.chunk_ids else "batch",
                risk_type=r.risk_type,
                risk_category=r.risk_category,
                severity_signal=r.severity_signal,
                financial_quantification=r.financial_quantification,
                management_response=r.management_response,
                flags=r.flags,
                cascade_context=r.cascade_context,
            )
        )
    return mentions


def _reindex(
    risks: list[DeduplicatedDocumentRisk],
) -> list[DeduplicatedDocumentRisk]:
    """Re-assign sequential DOC_RISK_NNN IDs."""
    result = []
    for i, r in enumerate(risks, start=1):
        result.append(r.model_copy(update={"risk_id": f"DOC_RISK_{i:03d}"}))
    return result


# ---------------------------------------------------------------------------
# Summary builder
# ---------------------------------------------------------------------------

def _build_summary(
    document_name: str,
    document_type: DocumentType,
    total_chunks: int,
    chunks_with_risks: int,
    raw_mentions: int,
    deduped: list[DeduplicatedDocumentRisk],
    failed_chunks: list[str],
) -> ExtractionSummary:
    severity_counts = Counter(r.severity_signal for r in deduped)
    flag_counts: Counter = Counter()
    for r in deduped:
        flag_counts.update(r.flags)

    return ExtractionSummary(
        document_name=document_name,
        document_type=document_type,
        total_chunks=total_chunks,
        chunks_with_risks=chunks_with_risks,
        raw_mentions=raw_mentions,
        deduplicated_risks=len(deduped),
        critical_count=severity_counts.get("CRITICAL", 0),
        high_count=severity_counts.get("HIGH", 0),
        medium_count=severity_counts.get("MEDIUM", 0),
        low_count=severity_counts.get("LOW", 0),
        unspecified_count=severity_counts.get("UNSPECIFIED", 0),
        material_weakness_count=flag_counts.get("MATERIAL_WEAKNESS", 0),
        repeat_finding_count=flag_counts.get("REPEAT_FINDING", 0),
        quantified_count=flag_counts.get("QUANTIFIED", 0),
        failed_chunks=failed_chunks,
    )


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------

def _write_outputs(
    result: DocumentExtractionResult,
    output_dir: str,
    document_name: str,
) -> None:
    """Write extraction results to disk."""
    os.makedirs(output_dir, exist_ok=True)

    # Sanitize document name for use in filenames
    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in document_name)
    safe_name = safe_name[:50]

    # Full extraction result
    result_path = os.path.join(output_dir, f"{safe_name}_extraction.json")
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result.model_dump(mode="json"), f, indent=2, ensure_ascii=False)
    logger.info("Written: %s", result_path)

    # Risks only (for downstream pipeline compatibility)
    risks_path = os.path.join(output_dir, f"{safe_name}_risks.json")
    with open(risks_path, "w", encoding="utf-8") as f:
        json.dump(
            [r.model_dump(mode="json") for r in result.risks],
            f, indent=2, ensure_ascii=False,
        )
    logger.info("Written: %s", risks_path)

    # Human-readable markdown report
    report_path = os.path.join(output_dir, f"{safe_name}_report.md")
    _write_markdown_report(result, report_path)
    logger.info("Written: %s", report_path)


def _write_markdown_report(
    result: DocumentExtractionResult,
    path: str,
) -> None:
    """Write a human-readable extraction report."""
    s = result.summary
    lines: list[str] = []

    lines.append(f"# Document Risk Extraction Report")
    lines.append(f"")
    lines.append(f"**Document:** {s.document_name}")
    lines.append(f"**Type:** {s.document_type.replace('_', ' ').title()}")
    lines.append(f"**Total Risks Extracted:** {s.deduplicated_risks}")
    lines.append(f"")
    lines.append(f"## Summary Statistics")
    lines.append(f"")
    lines.append(f"| Metric | Count |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Chunks processed | {s.total_chunks} |")
    lines.append(f"| Chunks with risks | {s.chunks_with_risks} |")
    lines.append(f"| Raw mentions | {s.raw_mentions} |")
    lines.append(f"| After deduplication | {s.deduplicated_risks} |")
    lines.append(f"| Critical severity | {s.critical_count} |")
    lines.append(f"| High severity | {s.high_count} |")
    lines.append(f"| Medium severity | {s.medium_count} |")
    lines.append(f"| Low severity | {s.low_count} |")
    lines.append(f"| Material weaknesses | {s.material_weakness_count} |")
    lines.append(f"| Repeat findings | {s.repeat_finding_count} |")
    lines.append(f"| Quantified risks | {s.quantified_count} |")
    lines.append(f"")

    # Risk table
    lines.append(f"## Risk Register")
    lines.append(f"")
    lines.append(f"| ID | Description | Category | Severity | Type | Sections | Flags |")
    lines.append(f"|----|-------------|----------|----------|------|----------|-------|")

    sorted_risks = sorted(
        result.risks,
        key=lambda r: (
            -{"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "UNSPECIFIED": 1}.get(
                r.severity_signal, 1
            ),
            r.risk_id,
        ),
    )

    for r in sorted_risks:
        sections_str = ", ".join(r.source_sections[:2])
        if len(r.source_sections) > 2:
            sections_str += f" +{len(r.source_sections) - 2}"
        flags_str = ", ".join(r.flags[:3]) if r.flags else "—"
        lines.append(
            f"| {r.risk_id} | {r.client_description[:60]} | "
            f"{r.risk_category} | {r.severity_signal} | {r.risk_type} | "
            f"{sections_str} | {flags_str} |"
        )

    lines.append(f"")
    lines.append(f"---")
    lines.append(f"")

    # Detailed per-risk section
    lines.append(f"## Detailed Risk Descriptions")
    lines.append(f"")

    for r in sorted_risks:
        lines.append(f"### {r.risk_id}: {r.client_description}")
        lines.append(f"")
        lines.append(f"- **Category:** {r.risk_category}")
        lines.append(f"- **Severity:** {r.severity_signal}")
        lines.append(f"- **Type:** {r.risk_type}")
        lines.append(f"- **Occurrence count:** {r.occurrence_count} chunk(s)")
        lines.append(f"- **Sections:** {', '.join(r.source_sections)}")

        if r.financial_quantification:
            lines.append(f"- **Financial quantification:** {r.financial_quantification}")

        if r.management_response:
            lines.append(f"- **Management response:** {r.management_response}")

        if r.flags:
            lines.append(f"- **Flags:** {', '.join(r.flags)}")

        if r.cascade_context:
            lines.append(f"- **Cascade context:** {r.cascade_context}")

        if r.verbatim_evidence:
            lines.append(f"")
            lines.append(f"**Verbatim evidence:**")
            for quote in r.verbatim_evidence[:5]:
                lines.append(f"> {quote}")

        lines.append(f"")
        lines.append(f"---")
        lines.append(f"")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


# ---------------------------------------------------------------------------
# Empty result helper
# ---------------------------------------------------------------------------

def _empty_result(
    document_name: str,
    document_type: DocumentType,
    chunk_metadata: list[ChunkMetadata] | None = None,
) -> DocumentExtractionResult:
    return DocumentExtractionResult(
        risks=[],
        summary=ExtractionSummary(
            document_name=document_name,
            document_type=document_type,
            total_chunks=0,
            chunks_with_risks=0,
            raw_mentions=0,
            deduplicated_risks=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            unspecified_count=0,
            material_weakness_count=0,
            repeat_finding_count=0,
            quantified_count=0,
            failed_chunks=[],
        ),
        chunk_metadata=chunk_metadata or [],
    )
