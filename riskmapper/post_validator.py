"""Post-mapping validator — Feedback Loop 2.

Reviews the complete risk universe after mapping and returns corrections:
- Duplicate risks that should be merged
- Bundled risks that should be split
- Cascade-as-risk entries that should become cascade_links
- Missing cascade_links that should be populated

One LLM call over the full risk universe JSON.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.schemas import MappedRisk

logger = logging.getLogger(__name__)


class _Correction(BaseModel):
    """A single correction to apply to the risk universe."""
    action: Literal["merge", "add_cascade_link", "flag_bundle"]
    risk_id: str
    target_risk_id: str | None = None
    reason: str


class _ValidationResponse(BaseModel):
    """LLM response with corrections."""
    corrections: list[_Correction]
    quality_score: int  # 1-10


_SYSTEM_PROMPT = """\
You are a quality reviewer for an ERM risk universe. You receive the \
complete list of mapped risks and check for issues.

Check for:
1. DUPLICATE RISKS: Two risks that describe the same underlying risk. \
   Action: "merge", set risk_id to the one to keep, target_risk_id to remove.

2. CASCADE LINKS: If risk A's cascade_context mentions risk B's topic, \
   they should be linked. Action: "add_cascade_link", risk_id = A, \
   target_risk_id = B.

3. BUNDLED RISKS: A single risk entry that describes 2+ unrelated risks. \
   Action: "flag_bundle", risk_id = the bundled entry.

Also assign a quality_score (1-10) for the overall risk universe:
- 10: Clean, no issues
- 7-9: Minor issues (1-2 missing links)
- 4-6: Moderate issues (duplicates or bundles present)
- 1-3: Major issues (many duplicates, wrong mappings)

Be conservative — only flag clear issues, not borderline cases.
"""


def validate_risk_universe(
    risks: list[MappedRisk],
    llm: LLMWrapper,
) -> list[MappedRisk]:
    """Review and correct the risk universe.

    Args:
        risks: Complete list of mapped risks.
        llm: LLMWrapper instance.

    Returns:
        Corrected list of MappedRisk objects.
    """
    if len(risks) <= 1:
        return risks

    # Build compact summary for the LLM
    lines = []
    for r in risks:
        cascade_str = f" CASCADE: {r.cascade_context[:60]}" if r.cascade_context else ""
        match_str = ""
        if r.registry_matches:
            best = r.registry_matches[0]
            match_str = f" → {best.risk_name[:40]} ({best.confidence})"
        lines.append(
            f"{r.risk_id}: {r.client_description}"
            f" (Q: {','.join(r.question_source)}, {r.risk_type})"
            f"{match_str}{cascade_str}"
        )
    risk_summary = "\n".join(lines)

    prompt = (
        f"Review this risk universe ({len(risks)} risks).\n"
        f"Find duplicates, missing cascade links, and bundled risks.\n\n"
        f"{risk_summary}\n\n"
        f"Return corrections as JSON with 'corrections' and 'quality_score' keys."
    )

    logger.info("Validating risk universe | %d risks", len(risks))

    try:
        response = llm.call(
            prompt=prompt,
            response_model=_ValidationResponse,
            temperature=0.0,
            step_name="post_validation",
            system_prompt=_SYSTEM_PROMPT,
        )
    except Exception as exc:
        logger.warning("Post-validation failed: %s — skipping corrections", exc)
        return risks

    logger.info(
        "Validation complete | quality=%d/10 | corrections=%d",
        response.quality_score, len(response.corrections),
    )

    # Apply corrections
    risks = _apply_corrections(risks, response.corrections)

    return risks


def _apply_corrections(
    risks: list[MappedRisk],
    corrections: list[_Correction],
) -> list[MappedRisk]:
    """Apply corrections to the risk universe."""
    risk_map = {r.risk_id: r for r in risks}
    to_remove: set[str] = set()

    for c in corrections:
        if c.action == "merge" and c.target_risk_id:
            # Merge target into source — keep source, remove target
            source = risk_map.get(c.risk_id)
            target = risk_map.get(c.target_risk_id)
            if source and target and c.target_risk_id not in to_remove:
                logger.info(
                    "Merging %s into %s: %s",
                    c.target_risk_id, c.risk_id, c.reason,
                )
                # Merge evidence and sources from target into source
                merged = source.model_copy(update={
                    "verbatim_evidence": list(set(
                        source.verbatim_evidence + target.verbatim_evidence
                    )),
                    "question_source": sorted(
                        set(source.question_source + target.question_source),
                        key=lambda q: int(q[1:]) if q[1:].isdigit() else 99,
                    ),
                    "flags": sorted(set(source.flags + target.flags)),
                })
                risk_map[c.risk_id] = merged
                to_remove.add(c.target_risk_id)

        elif c.action == "add_cascade_link" and c.target_risk_id:
            source = risk_map.get(c.risk_id)
            if source and c.target_risk_id not in source.cascade_links:
                logger.info(
                    "Adding cascade link %s → %s: %s",
                    c.risk_id, c.target_risk_id, c.reason,
                )
                updated_links = source.cascade_links + [c.target_risk_id]
                risk_map[c.risk_id] = source.model_copy(
                    update={"cascade_links": updated_links}
                )

        elif c.action == "flag_bundle":
            logger.warning(
                "Bundled risk flagged for manual review: %s — %s",
                c.risk_id, c.reason,
            )
            source = risk_map.get(c.risk_id)
            if source:
                risk_map[c.risk_id] = source.model_copy(update={
                    "human_review": True,
                    "human_review_reason": f"Bundled risk: {c.reason}",
                })

    # Remove merged-away risks and re-index
    result = [r for rid, r in risk_map.items() if rid not in to_remove]

    if to_remove:
        logger.info("Removed %d merged risks | final count: %d", len(to_remove), len(result))

    return result
