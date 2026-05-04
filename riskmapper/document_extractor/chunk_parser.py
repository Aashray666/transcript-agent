"""Chunk parser — extracts risk mentions from a single document chunk via LLM.

This is the core extraction agent. It is document-type-aware:
- Audit reports: looks for findings, deficiencies, observations
- Con-call transcripts: looks for hedging language, guidance caveats
- Annual reports: looks for risk factors, MD&A commentary
- etc.

Design principles (same as transcript_parser_v2.py):
1. ONE risk per entry — never bundle
2. Verbatim evidence required — no hallucination
3. Structured flags — REPEAT_FINDING, MATERIAL_WEAKNESS, etc.
4. Graceful failure — if a chunk fails, log and continue
5. Validation retry — if LLM returns bad format, retry with correction prompt
"""

from __future__ import annotations

import logging
from uuid import uuid4

from riskmapper.document_extractor.schemas import (
    DOCUMENT_TYPE_HINTS,
    ChunkMetadata,
    DocumentRiskMention,
    DocumentType,
    _LLMDocumentParseResponse,
    _LLMDocumentRiskMention,
)
from riskmapper.llm_wrapper import LLMWrapper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — document-type-agnostic base
# ---------------------------------------------------------------------------

_BASE_SYSTEM_PROMPT = """\
You are an expert Enterprise Risk Management (ERM) analyst specializing in \
extracting risks from corporate documents.

Your job: read the document chunk and extract EVERY distinct risk mentioned, \
implied, or evidenced in the text.

STRICT EXTRACTION RULES:
1. ONE risk per entry. NEVER bundle multiple risks into one entry.
   BAD: "Supply chain disruption, currency risk, and regulatory non-compliance"
   GOOD: Three separate entries — one for each distinct risk.

2. verbatim_evidence: Copy 1-5 EXACT quotes from the text that evidence this risk.
   Do NOT paraphrase. Do NOT invent quotes. If no direct quote exists, use the
   closest sentence that implies the risk.

3. client_description: Write the risk in clear, concise language (1-2 sentences).
   Use the company's own terminology where possible.

4. risk_type:
   - INHERENT: Structural/permanent risk inherent to the business model
   - EVENT_DRIVEN: Triggered by an external event or specific scenario
   - BOTH: Has both structural and event-driven dimensions

5. severity_signal: Use the document's OWN language:
   - CRITICAL: "material weakness", "critical", "severe", "existential"
   - HIGH: "significant", "high", "major", "substantial"
   - MEDIUM: "moderate", "medium", "notable", "meaningful"
   - LOW: "minor", "low", "limited", "immaterial"
   - UNSPECIFIED: No severity language used

6. flags — assign ALL that apply:
   - REPEAT_FINDING: "prior year", "previously reported", "recurring", "again"
   - MATERIAL_WEAKNESS: "material weakness" explicitly stated
   - SIGNIFICANT_DEFICIENCY: "significant deficiency" explicitly stated
   - UNMITIGATED: No controls, no management response, no remediation mentioned
   - ESCALATED: "board", "audit committee", "senior management" attention mentioned
   - QUANTIFIED: A specific $ / % / number is attached to this risk
   - FORWARD_LOOKING: "may", "could", "potential", "future", "expected to"
   - ALREADY_MATERIALIZED: "has occurred", "resulted in", "led to", "caused"
   - CASCADE_SIGNAL: This risk triggers or is triggered by another risk

7. financial_quantification: Extract the EXACT number if present.
   Examples: "USD 45M provision", "15% revenue decline", "EUR 2.3B exposure"
   If none, set to null.

8. management_response: What is management doing about this risk?
   Extract from the text. If nothing mentioned, set to null.

9. Do NOT hallucinate. Every risk must be grounded in the text provided.
10. Do NOT extract the same risk twice from the same chunk.
11. If the chunk contains NO risks, return an empty mentions list.
"""


def parse_chunk(
    chunk_text: str,
    chunk_metadata: ChunkMetadata,
    document_type: DocumentType,
    sector: str,
    llm: LLMWrapper,
) -> list[DocumentRiskMention]:
    """Extract risk mentions from a single document chunk.

    Args:
        chunk_text: The text content of this chunk.
        chunk_metadata: Provenance metadata for this chunk.
        document_type: Type of document (affects extraction focus).
        sector: Client sector (e.g. "Automotive").
        llm: LLMWrapper instance.

    Returns:
        List of DocumentRiskMention objects with assigned UUIDs.
        Returns empty list if extraction fails (never raises).
    """
    # Build document-type-specific hint
    doc_hint = DOCUMENT_TYPE_HINTS.get(document_type, DOCUMENT_TYPE_HINTS["other"])

    prompt = _build_extraction_prompt(
        chunk_text=chunk_text,
        chunk_metadata=chunk_metadata,
        document_type=document_type,
        doc_hint=doc_hint,
        sector=sector,
    )

    try:
        response = llm.call(
            prompt=prompt,
            response_model=_LLMDocumentParseResponse,
            temperature=0.0,
            step_name=f"doc_parse_{chunk_metadata.chunk_id}",
            system_prompt=_BASE_SYSTEM_PROMPT,
        )

        mentions = _build_mentions(response.mentions, chunk_metadata)

        logger.info(
            "%s | section='%s' | mentions=%d",
            chunk_metadata.chunk_id,
            chunk_metadata.section_label[:40],
            len(mentions),
        )
        return mentions

    except Exception as exc:
        logger.warning(
            "%s FAILED: %s — returning empty",
            chunk_metadata.chunk_id, exc,
        )
        return []


def _build_extraction_prompt(
    chunk_text: str,
    chunk_metadata: ChunkMetadata,
    document_type: DocumentType,
    doc_hint: str,
    sector: str,
) -> str:
    """Build the per-chunk extraction prompt."""
    return f"""DOCUMENT TYPE: {document_type.replace("_", " ").title()}
CLIENT SECTOR: {sector}
SECTION: {chunk_metadata.section_label}
CHUNK: {chunk_metadata.chunk_id} of {chunk_metadata.total_chunks}

EXTRACTION FOCUS FOR THIS DOCUMENT TYPE:
{doc_hint}

DOCUMENT TEXT:
{chunk_text}

Extract ALL distinct risks from the text above.
Return JSON with a 'mentions' key containing a list of risk objects.
If no risks are present in this chunk, return an empty list: {{"mentions": []}}

REMINDER:
- ONE risk per entry (never bundle)
- verbatim_evidence must be EXACT quotes from the text above
- Set source_section to: "{chunk_metadata.section_label}"
- Set financial_quantification to null if no number is present
- Set management_response to null if no response is mentioned"""


def _build_mentions(
    llm_mentions: list[_LLMDocumentRiskMention],
    chunk_metadata: ChunkMetadata,
) -> list[DocumentRiskMention]:
    """Convert LLM output to DocumentRiskMention objects with UUIDs."""
    mentions: list[DocumentRiskMention] = []

    for m in llm_mentions:
        # Skip empty descriptions
        if not m.client_description or not m.client_description.strip():
            continue

        # Ensure source_section is set
        source_section = m.source_section or chunk_metadata.section_label

        mentions.append(
            DocumentRiskMention(
                mention_id=uuid4(),
                client_description=m.client_description.strip(),
                verbatim_evidence=m.verbatim_evidence,
                source_section=source_section,
                chunk_id=chunk_metadata.chunk_id,
                risk_type=m.risk_type,
                risk_category=m.risk_category or "Unclassified",
                severity_signal=m.severity_signal,
                financial_quantification=m.financial_quantification,
                management_response=m.management_response,
                flags=m.flags,
                cascade_context=m.cascade_context,
            )
        )

    return mentions
