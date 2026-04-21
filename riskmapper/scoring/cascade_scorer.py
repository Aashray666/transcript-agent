"""Two-pass cascade scoring — adjusts LIKELIHOOD only, not impact.

Per architecture critique: if an upstream risk materializes and triggers
a downstream risk, the IMPACT of the downstream risk doesn't change —
it's the same regardless of cause. But the LIKELIHOOD increases because
there's an additional trigger pathway.

Pass 1: All risks scored independently (done by scoring_agent).
Pass 2: This module adjusts likelihood for cascade dependencies using
         topological ordering to avoid circular adjustments.
"""

from __future__ import annotations

import logging
from collections import deque

from riskmapper.scoring.schemas import ScoredRisk

logger = logging.getLogger(__name__)

# Per the likelihood table: cascade adjustment is +0.5 to composite
# before rounding, capped at 5
_CASCADE_LIKELIHOOD_BOOST = 1
_MAX_LIKELIHOOD = 5
_UPSTREAM_THRESHOLD = 4  # upstream must have likelihood ≥ 4 to trigger boost


def apply_cascade_adjustments(
    scored_risks: list[ScoredRisk],
    cascade_graph: dict[str, list[str]],
) -> list[ScoredRisk]:
    """Apply second-pass cascade likelihood adjustments.

    Uses topological ordering of the cascade graph to process risks
    in dependency order, avoiding circular adjustments.

    Args:
        scored_risks: All risks after first-pass independent scoring.
        cascade_graph: Maps downstream_risk_id → [upstream_risk_ids].

    Returns:
        Updated list of ScoredRisk with cascade adjustments applied.
    """
    if not cascade_graph:
        logger.info("No cascade dependencies — skipping cascade pass.")
        return scored_risks

    risk_map = {r.risk_id: r for r in scored_risks}
    order = _topological_sort(cascade_graph, set(risk_map.keys()))
    adjustments_made = 0

    for risk_id in order:
        risk = risk_map.get(risk_id)
        if not risk:
            continue

        upstream_ids = cascade_graph.get(risk_id, [])
        if not upstream_ids:
            continue

        # Check if any upstream risk has high likelihood
        high_upstream = [
            uid for uid in upstream_ids
            if uid in risk_map
            and risk_map[uid].likelihood_assessment.score >= _UPSTREAM_THRESHOLD
        ]

        if not high_upstream:
            continue

        current_likelihood = risk.likelihood_assessment.score
        new_likelihood = min(
            current_likelihood + _CASCADE_LIKELIHOOD_BOOST,
            _MAX_LIKELIHOOD,
        )

        if new_likelihood == current_likelihood:
            continue

        # Apply adjustment — create updated risk
        old_inherent = risk.inherent_risk_score
        new_inherent = risk.impact_assessment.score * new_likelihood
        new_rating = _get_rating(new_inherent)

        logger.info(
            "Cascade adjustment: %s likelihood %d→%d (upstream: %s), "
            "inherent %d→%d (%s→%s)",
            risk_id, current_likelihood, new_likelihood,
            ", ".join(high_upstream),
            old_inherent, new_inherent,
            risk.risk_rating, new_rating,
        )

        # Update the risk in place
        risk.likelihood_assessment.score = new_likelihood
        risk.likelihood_assessment.level = _get_likelihood_level(new_likelihood)
        risk.likelihood_assessment.justification += (
            f" [CASCADE ADJUSTMENT: +{_CASCADE_LIKELIHOOD_BOOST} due to "
            f"upstream risks {', '.join(high_upstream)} having likelihood ≥ "
            f"{_UPSTREAM_THRESHOLD}]"
        )
        risk.inherent_risk_score = new_inherent
        risk.risk_rating = new_rating
        risk.cascade_scoring_impact.cascade_likelihood_adjustment = float(
            _CASCADE_LIKELIHOOD_BOOST
        )
        adjustments_made += 1

    logger.info(
        "Cascade pass complete: %d adjustments across %d risks.",
        adjustments_made, len(scored_risks),
    )
    return scored_risks


def _topological_sort(
    graph: dict[str, list[str]],
    all_nodes: set[str],
) -> list[str]:
    """Topological sort of the cascade graph.

    Processes upstream risks before downstream risks so cascade
    adjustments propagate correctly. Falls back to arbitrary order
    if cycles are detected (shouldn't happen with proper cascade data).
    """
    # Build adjacency: upstream → downstream
    forward: dict[str, list[str]] = {}
    in_degree: dict[str, int] = {node: 0 for node in all_nodes}

    for downstream, upstreams in graph.items():
        for upstream in upstreams:
            forward.setdefault(upstream, []).append(downstream)
            if downstream in in_degree:
                in_degree[downstream] += 1

    # Kahn's algorithm
    queue: deque[str] = deque(
        node for node, deg in in_degree.items() if deg == 0
    )
    result: list[str] = []

    while queue:
        node = queue.popleft()
        result.append(node)
        for neighbor in forward.get(node, []):
            if neighbor in in_degree:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

    # If cycle detected, append remaining nodes
    remaining = all_nodes - set(result)
    if remaining:
        logger.warning(
            "Cycle detected in cascade graph — %d nodes in cycle: %s",
            len(remaining), remaining,
        )
        result.extend(sorted(remaining))

    return result


def _get_rating(score: int) -> str:
    """Map inherent risk score to rating band."""
    if score <= 4:
        return "Low"
    elif score <= 9:
        return "Medium"
    elif score <= 15:
        return "High"
    else:
        return "Critical"


def _get_likelihood_level(score: int) -> str:
    """Map likelihood score to level name."""
    levels = {1: "Rare", 2: "Unlikely", 3: "Possible", 4: "Likely", 5: "Almost Certain"}
    return levels.get(score, "Unknown")
