"""Deduplicator — two-pass merge with cascade filtering.

Pass 1: Filter out cascade-only mentions (Q12/Q13 consequences) and
        attach them as cascade_context on originating risks.
Pass 2: Send remaining mentions to LLM for semantic dedup.
Post:   Validate for bundled risks and split if needed.
"""

from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel

from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.schemas import DeduplicatedRisk, RawRiskMention

logger = logging.getLogger(__name__)


class _MergeGroup(BaseModel):
    indices: list[int]
    best_description: str
    risk_type: Literal["INHERENT", "EVENT_DRIVEN", "BOTH"]
    cascade_context: str | None = None


class _DeduplicationLLMResponse(BaseModel):
    groups: list[_MergeGroup]


_SYSTEM_PROMPT = """\
You are an expert ERM deduplication analyst. You receive a numbered list \
of risk mentions from a CRO interview. Many describe the SAME underlying \
risk from different questions.

Your job — AGGRESSIVE merging:
1. Group mentions that refer to the same underlying risk theme.
2. Merge sub-risks into their parent. Examples:
   - "GDPR enforcement" + "5G regulations" + "spectrum policy" → ONE group: "Regulatory risk"
   - "Currency risk" + "financing risk" + "capital expenditure" → ONE group: "Financial risk"
   - "External cyber attacks" + "insider access risk" + "IoT security" → ONE group: "Cyber and technology risk"
3. Pick the clearest, most concise description for each group.
4. Every index must appear in exactly ONE group.
5. Target: 15-22 unique risk groups. If you have more than 25, merge harder.
6. Do NOT create groups for cascade consequences — those are metadata, not risks.

risk_type: INHERENT if any mention is structural/permanent, EVENT_DRIVEN if \
externally triggered, BOTH if mentions span both.
"""


def deduplicate_risks(
    mentions: list[RawRiskMention],
    llm: LLMWrapper,
) -> list[DeduplicatedRisk]:
    """Two-pass deduplication with cascade filtering.

    Pass 1: Filter cascade-only mentions from Q12/Q13.
    Pass 2: LLM-based semantic dedup on remaining mentions.
    """
    if not mentions:
        return []

    # --- Pass 1: Separate cascade-only mentions ---
    core_mentions, cascade_mentions = _filter_cascade_mentions(mentions)
    logger.info(
        "Pass 1 | core=%d | cascade_only=%d",
        len(core_mentions), len(cascade_mentions),
    )

    # --- Pass 2: LLM dedup on core mentions ---
    lines = []
    for i, m in enumerate(core_mentions):
        flags_str = ", ".join(m.flags) if m.flags else "none"
        evidence_preview = m.verbatim_evidence[0][:80] if m.verbatim_evidence else ""
        lines.append(
            f"[{i}] {m.client_description[:100]} "
            f"(Q: {','.join(m.question_source)}, "
            f"type: {m.risk_type}, flags: {flags_str})\n"
            f"    \"{evidence_preview}\""
        )
    mention_summary = "\n".join(lines)

    prompt = (
        f"Here are {len(core_mentions)} risk mentions from a CRO interview.\n"
        f"Aggressively merge duplicates and related sub-risks.\n"
        f"Target: 15-22 unique groups.\n\n"
        f"{mention_summary}\n\n"
        f"Return merge groups as JSON with a 'groups' key."
    )

    logger.info("Pass 2 | deduplicating %d core mentions via LLM", len(core_mentions))

    response = llm.call(
        prompt=prompt,
        response_model=_DeduplicationLLMResponse,
        temperature=0.0,
        step_name="deduplication",
        system_prompt=_SYSTEM_PROMPT,
    )

    # --- Build DeduplicatedRisk objects ---
    deduped: list[DeduplicatedRisk] = []

    for group_idx, group in enumerate(response.groups, start=1):
        group_mentions_list = [
            core_mentions[i] for i in group.indices
            if 0 <= i < len(core_mentions)
        ]
        if not group_mentions_list:
            continue

        all_evidence: list[str] = []
        all_sources: list[str] = []
        all_flags: list[str] = []
        all_ids: list[str] = []
        cascade_ctx = group.cascade_context

        for m in group_mentions_list:
            all_ids.append(str(m.mention_id))
            all_evidence.extend(m.verbatim_evidence)
            all_sources.extend(m.question_source)
            all_flags.extend(m.flags)
            if not cascade_ctx and m.cascade_context:
                cascade_ctx = m.cascade_context

        # Also attach cascade context from filtered cascade mentions
        cascade_ctx = _attach_cascade_context(
            group.best_description, cascade_mentions, cascade_ctx
        )

        # Deduplicate
        seen_evidence = set()
        unique_evidence = []
        for e in all_evidence:
            if e not in seen_evidence:
                seen_evidence.add(e)
                unique_evidence.append(e)

        unique_sources = sorted(set(all_sources), key=_q_sort)
        unique_flags = sorted(set(all_flags))

        deduped.append(
            DeduplicatedRisk(
                risk_id=f"RISK_{group_idx:03d}",
                client_description=group.best_description,
                verbatim_evidence=unique_evidence,
                question_source=unique_sources,
                risk_type=group.risk_type,
                flags=unique_flags,
                cascade_context=cascade_ctx,
                merged_from=all_ids,
            )
        )

    # --- Feedback Loop 1: Refinement if too many groups ---
    deduped = _refine_if_needed(deduped, llm, target_max=25, max_passes=2)

    # --- Post-validation: warn about bundled risks ---
    for r in deduped:
        if r.client_description.count(" and ") >= 2:
            logger.warning(
                "Possible bundled risk: %s — %s",
                r.risk_id, r.client_description[:60],
            )

    logger.info(
        "Deduplication complete | raw=%d | core=%d | cascade_filtered=%d | output=%d",
        len(mentions), len(core_mentions), len(cascade_mentions), len(deduped),
    )

    return deduped


def _refine_if_needed(
    deduped: list[DeduplicatedRisk],
    llm: LLMWrapper,
    target_max: int = 25,
    max_passes: int = 2,
) -> list[DeduplicatedRisk]:
    """Feedback Loop 1: If dedup produced too many groups, ask LLM to merge further."""
    for pass_num in range(max_passes):
        if len(deduped) <= target_max:
            return deduped

        logger.info(
            "Refinement pass %d | %d groups > target %d — merging further",
            pass_num + 1, len(deduped), target_max,
        )

        lines = []
        for i, r in enumerate(deduped):
            lines.append(
                f"[{i}] {r.risk_id}: {r.client_description} "
                f"(Q: {','.join(r.question_source)}, type: {r.risk_type})"
            )

        refine_prompt = (
            f"You produced {len(deduped)} risk groups — too many.\n"
            f"Merge related groups further. Target: 15-22.\n\n"
            f"{chr(10).join(lines)}\n\n"
            f"Return NEW merge groups (using indices above) as JSON with 'groups' key."
        )

        try:
            resp = llm.call(
                prompt=refine_prompt,
                response_model=_DeduplicationLLMResponse,
                temperature=0.0,
                step_name=f"dedup_refinement_{pass_num + 1}",
                system_prompt=_SYSTEM_PROMPT,
            )

            refined: list[DeduplicatedRisk] = []
            for g_idx, group in enumerate(resp.groups, start=1):
                group_risks = [deduped[i] for i in group.indices if 0 <= i < len(deduped)]
                if not group_risks:
                    continue

                m_evidence: list[str] = []
                m_sources: list[str] = []
                m_flags: list[str] = []
                m_ids: list[str] = []
                m_cascade = group.cascade_context

                for r in group_risks:
                    m_evidence.extend(r.verbatim_evidence)
                    m_sources.extend(r.question_source)
                    m_flags.extend(r.flags)
                    m_ids.extend(r.merged_from)
                    if not m_cascade and r.cascade_context:
                        m_cascade = r.cascade_context

                seen = set()
                uniq_ev = [e for e in m_evidence if e not in seen and not seen.add(e)]

                refined.append(
                    DeduplicatedRisk(
                        risk_id=f"RISK_{g_idx:03d}",
                        client_description=group.best_description,
                        verbatim_evidence=uniq_ev,
                        question_source=sorted(set(m_sources), key=_q_sort),
                        risk_type=group.risk_type,
                        flags=sorted(set(m_flags)),
                        cascade_context=m_cascade,
                        merged_from=m_ids,
                    )
                )

            logger.info("Refinement pass %d | %d → %d groups", pass_num + 1, len(deduped), len(refined))
            deduped = refined

        except Exception as exc:
            logger.warning("Refinement pass %d failed: %s — keeping current", pass_num + 1, exc)
            break

    return deduped


def _filter_cascade_mentions(
    mentions: list[RawRiskMention],
) -> tuple[list[RawRiskMention], list[RawRiskMention]]:
    """Separate cascade-only mentions from core risk mentions.

    A mention is cascade-only if:
    - It comes exclusively from Q12 or Q13
    - Its description reads like a consequence, not a standalone risk
    """
    cascade_keywords = [
        "triggers", "triggered by", "cascade", "pulled in",
        "simultaneously", "which triggers", "which affects",
        "cascades from", "cascading", "chain of",
    ]

    core = []
    cascade_only = []

    for m in mentions:
        sources = set(m.question_source)
        is_q12_q13_only = sources.issubset({"Q12", "Q13"})

        if is_q12_q13_only:
            desc_lower = m.client_description.lower()
            has_cascade_language = any(kw in desc_lower for kw in cascade_keywords)

            if has_cascade_language or "CASCADE_SIGNAL" in m.flags:
                cascade_only.append(m)
                continue

        core.append(m)

    return core, cascade_only


def _attach_cascade_context(
    risk_description: str,
    cascade_mentions: list[RawRiskMention],
    existing_context: str | None,
) -> str | None:
    """Try to match cascade mentions to this risk and build cascade context."""
    if not cascade_mentions:
        return existing_context

    desc_lower = risk_description.lower()
    relevant_cascades = []

    for cm in cascade_mentions:
        cm_lower = cm.client_description.lower()
        # Simple keyword overlap check
        desc_words = set(desc_lower.split())
        cm_words = set(cm_lower.split())
        overlap = desc_words & cm_words - {"risk", "the", "a", "and", "of", "in", "to", "is"}
        if len(overlap) >= 2:
            relevant_cascades.append(cm.cascade_context or cm.client_description)

    if relevant_cascades:
        cascade_text = "; ".join(relevant_cascades[:3])
        if existing_context:
            return f"{existing_context}; {cascade_text}"
        return cascade_text

    return existing_context


def _q_sort(q: str) -> int:
    try:
        return int(q[1:])
    except (ValueError, IndexError):
        return 99
