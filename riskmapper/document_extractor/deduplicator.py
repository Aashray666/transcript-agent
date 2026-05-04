"""Cross-chunk deduplicator for document risk mentions.

The same risk often appears in multiple chunks (e.g., "supply chain risk"
mentioned in the Risk Factors section, the MD&A, and the footnotes).
This module merges those into a single DeduplicatedDocumentRisk.

Design (same philosophy as riskmapper/deduplicator.py):
- LLM does semantic grouping (understands that "vendor concentration" and
  "single-source supplier dependency" are the same risk)
- Python does the merging (combines evidence, sources, flags)
- Refinement loop: if too many groups, ask LLM to merge further
- Post-validation: warn about bundled descriptions

Key difference from CRO interview dedup:
- No Q-number sources — uses section labels instead
- Occurrence count tracked (how many chunks mentioned this risk)
- Severity signal: take the HIGHEST severity across all mentions
- Financial quantification: take the most specific number
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from riskmapper.document_extractor.schemas import (
    DeduplicatedDocumentRisk,
    DocumentRiskMention,
)
from riskmapper.llm_wrapper import LLMWrapper

logger = logging.getLogger(__name__)

# Severity ranking for "take highest" logic
_SEVERITY_RANK = {
    "CRITICAL": 5,
    "HIGH": 4,
    "MEDIUM": 3,
    "LOW": 2,
    "UNSPECIFIED": 1,
}


# ---------------------------------------------------------------------------
# LLM response models
# ---------------------------------------------------------------------------

class _MergeGroup(BaseModel):
    indices: list[int]
    best_description: str
    risk_type: Literal["INHERENT", "EVENT_DRIVEN", "BOTH"]
    risk_category: str
    cascade_context: str | None = None


class _DeduplicationLLMResponse(BaseModel):
    groups: list[_MergeGroup]


_SYSTEM_PROMPT = """\
You are an ERM deduplication analyst. You receive numbered risk mentions \
extracted from a corporate document. Many describe the SAME underlying risk \
from different sections.

STRICT RULES:
1. Group mentions that refer to the SAME underlying risk.
2. Every mention index must appear in exactly ONE group.
3. A group can have one mention (unique risk, no duplicates).
4. Pick the clearest, most complete description for each group.
5. NEVER bundle unrelated risks. "Cyber risk" and "supply chain risk" are \
   SEPARATE groups even if they appear in the same section.
6. Cascade descriptions (how risks trigger each other) should be merged into \
   the originating risk group, not kept as standalone groups.
7. Aim for 10-25 unique risk groups from a typical document.
8. risk_type for the group: INHERENT if any mention is INHERENT, \
   EVENT_DRIVEN if any is EVENT_DRIVEN, BOTH if mentions span both types.
9. risk_category: Use the most specific category from the mentions \
   (e.g., "Operational", "Financial", "Regulatory", "Technology", "Strategic").
"""


def deduplicate_document_risks(
    mentions: list[DocumentRiskMention],
    llm: LLMWrapper,
    target_max: int = 30,
) -> list[DeduplicatedDocumentRisk]:
    """Merge duplicate risk mentions across document chunks.

    Args:
        mentions: All raw mentions from all chunks.
        llm: LLMWrapper instance.
        target_max: Target maximum number of unique risks.

    Returns:
        List of DeduplicatedDocumentRisk with DOC_RISK_NNN IDs.
    """
    if not mentions:
        return []

    if len(mentions) == 1:
        return [_single_mention_to_deduped(mentions[0], "DOC_RISK_001")]

    # Build compact summary for LLM
    lines = _build_mention_summary(mentions)
    mention_summary = "\n".join(lines)

    prompt = (
        f"Here are {len(mentions)} risk mentions extracted from a corporate document.\n"
        f"Group duplicates — same underlying risk mentioned in different sections.\n"
        f"Target: {min(target_max, len(mentions))} unique groups.\n\n"
        f"{mention_summary}\n\n"
        f"Return merge groups as JSON with a 'groups' key."
    )

    logger.info("Deduplicating %d document risk mentions via LLM", len(mentions))

    try:
        response = llm.call(
            prompt=prompt,
            response_model=_DeduplicationLLMResponse,
            temperature=0.0,
            step_name="doc_deduplication",
            system_prompt=_SYSTEM_PROMPT,
        )
    except Exception as exc:
        logger.error("Deduplication LLM call failed: %s — using fallback", exc)
        return _fallback_dedup(mentions)

    # Build DeduplicatedDocumentRisk objects
    deduped = _build_deduped_risks(mentions, response.groups)

    # Refinement loop: if too many groups, ask LLM to merge further
    deduped = _refine_if_needed(deduped, llm, target_max, max_passes=2)

    # Post-validation: warn about bundled descriptions
    for r in deduped:
        if r.client_description.count(" and ") >= 2:
            logger.warning(
                "Possible bundled risk: %s — %s",
                r.risk_id, r.client_description[:60],
            )

    logger.info(
        "Deduplication complete | raw=%d | deduped=%d",
        len(mentions), len(deduped),
    )

    return deduped


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_mention_summary(mentions: list[DocumentRiskMention]) -> list[str]:
    """Build a compact numbered summary for the LLM."""
    lines = []
    for i, m in enumerate(mentions):
        flags_str = ", ".join(m.flags) if m.flags else "none"
        evidence_preview = m.verbatim_evidence[0][:80] if m.verbatim_evidence else ""
        qty = f" | qty={m.financial_quantification}" if m.financial_quantification else ""
        lines.append(
            f"[{i}] {m.client_description[:100]} "
            f"(section='{m.source_section[:30]}', "
            f"type={m.risk_type}, severity={m.severity_signal}, "
            f"flags={flags_str}{qty})\n"
            f"    \"{evidence_preview}\""
        )
    return lines


def _build_deduped_risks(
    mentions: list[DocumentRiskMention],
    groups: list[_MergeGroup],
) -> list[DeduplicatedDocumentRisk]:
    """Build DeduplicatedDocumentRisk objects from LLM merge groups."""
    deduped: list[DeduplicatedDocumentRisk] = []

    for group_idx, group in enumerate(groups, start=1):
        group_mentions = [
            mentions[i] for i in group.indices
            if 0 <= i < len(mentions)
        ]
        if not group_mentions:
            continue

        # Merge fields
        all_evidence: list[str] = []
        all_sections: list[str] = []
        all_chunk_ids: list[str] = []
        all_flags: list[str] = []
        all_ids: list[str] = []
        best_severity = "UNSPECIFIED"
        best_qty: str | None = None
        best_mgmt_response: str | None = None
        cascade_ctx = group.cascade_context

        for m in group_mentions:
            all_ids.append(str(m.mention_id))
            all_evidence.extend(m.verbatim_evidence)
            if m.source_section not in all_sections:
                all_sections.append(m.source_section)
            if m.chunk_id not in all_chunk_ids:
                all_chunk_ids.append(m.chunk_id)
            all_flags.extend(m.flags)

            # Take highest severity
            if _SEVERITY_RANK.get(m.severity_signal, 1) > _SEVERITY_RANK.get(best_severity, 1):
                best_severity = m.severity_signal

            # Take most specific quantification (prefer non-null)
            if m.financial_quantification and not best_qty:
                best_qty = m.financial_quantification

            # Take first non-null management response
            if m.management_response and not best_mgmt_response:
                best_mgmt_response = m.management_response

            # Cascade context
            if not cascade_ctx and m.cascade_context:
                cascade_ctx = m.cascade_context

        # Deduplicate evidence (exact matches)
        seen: set[str] = set()
        unique_evidence = [e for e in all_evidence if e not in seen and not seen.add(e)]  # type: ignore[func-returns-value]

        unique_flags = sorted(set(all_flags))

        deduped.append(
            DeduplicatedDocumentRisk(
                risk_id=f"DOC_RISK_{group_idx:03d}",
                client_description=group.best_description,
                verbatim_evidence=unique_evidence,
                source_sections=all_sections,
                chunk_ids=all_chunk_ids,
                risk_type=group.risk_type,
                risk_category=group.risk_category,
                severity_signal=best_severity,
                financial_quantification=best_qty,
                management_response=best_mgmt_response,
                flags=unique_flags,
                cascade_context=cascade_ctx,
                merged_from=all_ids,
                occurrence_count=len(group_mentions),
            )
        )

    return deduped


def _refine_if_needed(
    deduped: list[DeduplicatedDocumentRisk],
    llm: LLMWrapper,
    target_max: int,
    max_passes: int,
) -> list[DeduplicatedDocumentRisk]:
    """If too many groups, ask LLM to merge further (up to max_passes)."""
    for pass_num in range(max_passes):
        if len(deduped) <= target_max:
            return deduped

        logger.info(
            "Refinement pass %d | %d groups > target %d — merging further",
            pass_num + 1, len(deduped), target_max,
        )

        lines = [
            f"[{i}] {r.risk_id}: {r.client_description} "
            f"(sections={len(r.source_sections)}, type={r.risk_type}, "
            f"severity={r.severity_signal})"
            for i, r in enumerate(deduped)
        ]

        refine_prompt = (
            f"You produced {len(deduped)} risk groups — too many.\n"
            f"Merge related groups further. Target: {target_max}.\n\n"
            f"{chr(10).join(lines)}\n\n"
            f"Return NEW merge groups (using indices above) as JSON with 'groups' key."
        )

        try:
            resp = llm.call(
                prompt=refine_prompt,
                response_model=_DeduplicationLLMResponse,
                temperature=0.0,
                step_name=f"doc_dedup_refinement_{pass_num + 1}",
                system_prompt=_SYSTEM_PROMPT,
            )

            refined: list[DeduplicatedDocumentRisk] = []
            for g_idx, group in enumerate(resp.groups, start=1):
                group_risks = [deduped[i] for i in group.indices if 0 <= i < len(deduped)]
                if not group_risks:
                    continue

                m_evidence: list[str] = []
                m_sections: list[str] = []
                m_chunks: list[str] = []
                m_flags: list[str] = []
                m_ids: list[str] = []
                m_cascade = group.cascade_context
                best_sev = "UNSPECIFIED"
                best_qty = None
                best_mgmt = None

                for r in group_risks:
                    m_evidence.extend(r.verbatim_evidence)
                    m_sections.extend(r.source_sections)
                    m_chunks.extend(r.chunk_ids)
                    m_flags.extend(r.flags)
                    m_ids.extend(r.merged_from)
                    if not m_cascade and r.cascade_context:
                        m_cascade = r.cascade_context
                    if _SEVERITY_RANK.get(r.severity_signal, 1) > _SEVERITY_RANK.get(best_sev, 1):
                        best_sev = r.severity_signal
                    if r.financial_quantification and not best_qty:
                        best_qty = r.financial_quantification
                    if r.management_response and not best_mgmt:
                        best_mgmt = r.management_response

                seen: set[str] = set()
                uniq_ev = [e for e in m_evidence if e not in seen and not seen.add(e)]  # type: ignore[func-returns-value]

                refined.append(
                    DeduplicatedDocumentRisk(
                        risk_id=f"DOC_RISK_{g_idx:03d}",
                        client_description=group.best_description,
                        verbatim_evidence=uniq_ev,
                        source_sections=sorted(set(m_sections)),
                        chunk_ids=sorted(set(m_chunks)),
                        risk_type=group.risk_type,
                        risk_category=group.risk_category,
                        severity_signal=best_sev,
                        financial_quantification=best_qty,
                        management_response=best_mgmt,
                        flags=sorted(set(m_flags)),
                        cascade_context=m_cascade,
                        merged_from=m_ids,
                        occurrence_count=sum(r.occurrence_count for r in group_risks),
                    )
                )

            logger.info(
                "Refinement pass %d | %d → %d groups",
                pass_num + 1, len(deduped), len(refined),
            )
            deduped = refined

        except Exception as exc:
            logger.warning(
                "Refinement pass %d failed: %s — keeping current",
                pass_num + 1, exc,
            )
            break

    return deduped


def _single_mention_to_deduped(
    m: DocumentRiskMention,
    risk_id: str,
) -> DeduplicatedDocumentRisk:
    """Convert a single mention directly to a DeduplicatedDocumentRisk."""
    return DeduplicatedDocumentRisk(
        risk_id=risk_id,
        client_description=m.client_description,
        verbatim_evidence=m.verbatim_evidence,
        source_sections=[m.source_section],
        chunk_ids=[m.chunk_id],
        risk_type=m.risk_type,
        risk_category=m.risk_category,
        severity_signal=m.severity_signal,
        financial_quantification=m.financial_quantification,
        management_response=m.management_response,
        flags=m.flags,
        cascade_context=m.cascade_context,
        merged_from=[str(m.mention_id)],
        occurrence_count=1,
    )


def _fallback_dedup(
    mentions: list[DocumentRiskMention],
) -> list[DeduplicatedDocumentRisk]:
    """Fallback: treat every mention as a unique risk (no merging)."""
    logger.warning("Using fallback dedup — no merging performed")
    return [
        _single_mention_to_deduped(m, f"DOC_RISK_{i:03d}")
        for i, m in enumerate(mentions, start=1)
    ]
