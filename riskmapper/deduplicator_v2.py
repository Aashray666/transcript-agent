"""V2 Deduplicator — richer context, stricter rules, post-dedup validation.

Sends full evidence per mention to the LLM. Validates output for bundled
risks and populates cascade_links.
"""

from __future__ import annotations

import logging
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
You are an ERM deduplication analyst. You receive numbered risk mentions \
extracted from a CRO interview. Many describe the SAME underlying risk \
from different questions.

STRICT RULES:
1. Group mentions that refer to the SAME underlying risk.
2. Every mention index must appear in exactly ONE group.
3. A group can have one mention (unique risk, no duplicates).
4. Pick the clearest client_description for each group.
5. NEVER bundle unrelated risks. If a mention covers "AI governance" and \
another covers "electronic waste", they are SEPARATE groups.
6. Cascade descriptions (mentions about how risks trigger each other) should \
be merged into the originating risk group, not kept as standalone groups.
7. Aim for 15-25 unique risk groups from a typical interview.
8. risk_type for the group: INHERENT if any mention is INHERENT, EVENT_DRIVEN \
if any is EVENT_DRIVEN, BOTH if mentions span both types.
"""


def deduplicate_risks_v2(
    mentions: list[RawRiskMention],
    llm: LLMWrapper,
) -> list[DeduplicatedRisk]:
    """Merge duplicate mentions with full evidence context.

    Args:
        mentions: Raw risk mentions from the parser.
        llm: LLMWrapper instance.

    Returns:
        Deduplicated risks with sequential RISK_NNN IDs.
    """
    if not mentions:
        return []

    # Build rich summary with evidence (not just one-liners)
    lines = []
    for i, m in enumerate(mentions):
        flags_str = ", ".join(m.flags) if m.flags else "none"
        evidence_str = " | ".join(e[:80] for e in m.verbatim_evidence[:2])
        cascade_str = f" CASCADE: {m.cascade_context[:60]}" if m.cascade_context else ""
        lines.append(
            f"[{i}] {m.client_description[:100]} "
            f"(Q: {','.join(m.question_source)}, "
            f"type: {m.risk_type}, flags: {flags_str}){cascade_str}\n"
            f"    Evidence: {evidence_str}"
        )
    mention_summary = "\n".join(lines)

    prompt = (
        f"Here are {len(mentions)} risk mentions. Group duplicates.\n\n"
        f"{mention_summary}\n\n"
        f"Return merge groups as JSON with a 'groups' key."
    )

    logger.info("V2 deduplicating %d mentions", len(mentions))

    response = llm.call(
        prompt=prompt,
        response_model=_DeduplicationLLMResponse,
        temperature=0.0,
        step_name="deduplication_v2",
        system_prompt=_SYSTEM_PROMPT,
    )

    # Build DeduplicatedRisk objects
    deduped: list[DeduplicatedRisk] = []

    for group_idx, group in enumerate(response.groups, start=1):
        group_mentions = [mentions[i] for i in group.indices if 0 <= i < len(mentions)]
        if not group_mentions:
            continue

        all_evidence: list[str] = []
        all_sources: list[str] = []
        all_flags: list[str] = []
        all_ids: list[str] = []
        cascade_ctx = group.cascade_context

        for m in group_mentions:
            all_ids.append(str(m.mention_id))
            all_evidence.extend(m.verbatim_evidence)
            all_sources.extend(m.question_source)
            all_flags.extend(m.flags)
            if not cascade_ctx and m.cascade_context:
                cascade_ctx = m.cascade_context

        unique_sources = sorted(set(all_sources), key=_q_sort)
        unique_flags = sorted(set(all_flags))
        # Deduplicate evidence (exact matches only)
        seen = set()
        unique_evidence = []
        for e in all_evidence:
            if e not in seen:
                seen.add(e)
                unique_evidence.append(e)

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

    # Post-dedup validation: check for bundled risks
    deduped = _validate_no_bundles(deduped)

    logger.info(
        "V2 dedup complete | input=%d | output=%d",
        len(mentions), len(deduped),
    )

    return deduped


def _validate_no_bundles(risks: list[DeduplicatedRisk]) -> list[DeduplicatedRisk]:
    """Flag risks whose descriptions contain multiple unrelated concepts."""
    flagged = []
    for r in risks:
        desc = r.client_description.lower()
        # Simple heuristic: if description has " and " joining 3+ concepts
        # or contains commas separating distinct topics, it might be bundled
        if desc.count(" and ") >= 2 or desc.count(", ") >= 2:
            logger.warning(
                "Possible bundled risk detected: %s - %s",
                r.risk_id, r.client_description[:60],
            )
        flagged.append(r)
    return flagged


def _q_sort(q: str) -> int:
    try:
        return int(q[1:])
    except (ValueError, IndexError):
        return 99
