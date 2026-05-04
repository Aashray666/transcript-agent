"""Post-scoring consistency checker.

Validates scoring consistency across the full risk universe after all
risks are scored. Per critique: this is the post-flight check. In-flight
consistency is handled by the memory store providing prior scores to
the Scoring Agent.

Checks:
1. Related risk coherence — similar risks shouldn't have wildly different scores
2. Cascade coherence — upstream likelihood=5 → downstream should be ≥3
3. Dimension consistency — risks in same dimension should be logically ordered
4. Outlier detection — flag scores that deviate significantly
5. Score distribution — flag if all risks cluster at the same score
"""

from __future__ import annotations

import logging
from collections import Counter

from riskmapper.scoring.schemas import (
    ConsistencyCheckResult,
    ConsistencyFlag,
    ScoredRisk,
)

logger = logging.getLogger(__name__)


def check_consistency(
    scored_risks: list[ScoredRisk],
    cascade_graph: dict[str, list[str]],
) -> ConsistencyCheckResult:
    """Run all consistency checks on the scored risk universe.

    Args:
        scored_risks: All scored risks from the pipeline.
        cascade_graph: Cascade dependency graph from memory store.

    Returns:
        ConsistencyCheckResult with all flags and distribution stats.
    """
    flags: list[ConsistencyFlag] = []

    flags.extend(_check_cascade_coherence(scored_risks, cascade_graph))
    flags.extend(_check_dimension_consistency(scored_risks))
    flags.extend(_check_outliers(scored_risks))
    flags.extend(_check_score_clustering(scored_risks))

    # Score distribution
    rating_counts = Counter(r.risk_rating for r in scored_risks)
    distribution = {
        "Low": rating_counts.get("Low", 0),
        "Medium": rating_counts.get("Medium", 0),
        "High": rating_counts.get("High", 0),
        "Critical": rating_counts.get("Critical", 0),
    }

    # Overall assessment
    n_flags = len(flags)
    high_flags = sum(1 for f in flags if f.severity == "HIGH")
    if high_flags > 0:
        assessment = (
            f"{n_flags} inconsistencies found ({high_flags} high severity). "
            f"Manual review recommended for flagged risks."
        )
    elif n_flags > 0:
        assessment = (
            f"{n_flags} minor inconsistencies found. "
            f"Scores are generally consistent."
        )
    else:
        assessment = "No inconsistencies detected. Scores are consistent."

    logger.info(
        "Consistency check complete: %d flags (%d high) across %d risks",
        n_flags, high_flags, len(scored_risks),
    )

    return ConsistencyCheckResult(
        total_risks_checked=len(scored_risks),
        flags=flags,
        score_distribution=distribution,
        overall_assessment=assessment,
    )


def _check_cascade_coherence(
    scored_risks: list[ScoredRisk],
    cascade_graph: dict[str, list[str]],
) -> list[ConsistencyFlag]:
    """If upstream risk has Likelihood ≥ 4, downstream should have Likelihood ≥ 3."""
    flags: list[ConsistencyFlag] = []
    risk_map = {r.risk_id: r for r in scored_risks}

    for downstream_id, upstream_ids in cascade_graph.items():
        downstream = risk_map.get(downstream_id)
        if not downstream:
            continue

        for upstream_id in upstream_ids:
            upstream = risk_map.get(upstream_id)
            if not upstream:
                continue

            if (
                upstream.likelihood_assessment.score >= 4
                and downstream.likelihood_assessment.score < 3
            ):
                flags.append(ConsistencyFlag(
                    risk_id=downstream_id,
                    flag_type="CASCADE_COHERENCE",
                    description=(
                        f"Upstream {upstream_id} has Likelihood={upstream.likelihood_assessment.score} "
                        f"but downstream {downstream_id} has Likelihood={downstream.likelihood_assessment.score}. "
                        f"Expected ≥3 for cascade coherence."
                    ),
                    related_risk_ids=[upstream_id],
                    recommended_adjustment=(
                        f"Consider increasing {downstream_id} likelihood to at least 3."
                    ),
                    severity="HIGH",
                ))

    return flags


def _check_dimension_consistency(
    scored_risks: list[ScoredRisk],
) -> list[ConsistencyFlag]:
    """Risks in the same impact dimension should have logically ordered scores."""
    flags: list[ConsistencyFlag] = []

    # Group by dimension
    by_dimension: dict[str, list[ScoredRisk]] = {}
    for r in scored_risks:
        dim = r.impact_assessment.dimension
        by_dimension.setdefault(dim, []).append(r)

    for dim, risks in by_dimension.items():
        if len(risks) < 2:
            continue

        # Check for large score gaps within same dimension
        scores = sorted(r.impact_assessment.score for r in risks)
        if scores[-1] - scores[0] > 3:
            risk_ids = [r.risk_id for r in risks]
            flags.append(ConsistencyFlag(
                risk_id=risk_ids[0],
                flag_type="DIMENSION_CONSISTENCY",
                description=(
                    f"Risks in '{dim}' have impact scores ranging from "
                    f"{scores[0]} to {scores[-1]} (gap > 3). Review for consistency."
                ),
                related_risk_ids=risk_ids,
                recommended_adjustment=None,
                severity="MEDIUM",
            ))

    return flags


def _check_outliers(
    scored_risks: list[ScoredRisk],
) -> list[ConsistencyFlag]:
    """Flag risks whose inherent score deviates significantly from the mean."""
    flags: list[ConsistencyFlag] = []

    if len(scored_risks) < 4:
        return flags

    scores = [r.inherent_risk_score for r in scored_risks]
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    std_dev = variance ** 0.5

    if std_dev < 1.0:
        return flags  # Too little variation to detect outliers

    for r in scored_risks:
        deviation = abs(r.inherent_risk_score - mean)
        if deviation > 2 * std_dev:
            flags.append(ConsistencyFlag(
                risk_id=r.risk_id,
                flag_type="OUTLIER",
                description=(
                    f"{r.risk_id} inherent score {r.inherent_risk_score} "
                    f"deviates significantly from mean {mean:.1f} "
                    f"(±{std_dev:.1f}). Review if justified."
                ),
                related_risk_ids=[],
                recommended_adjustment=None,
                severity="LOW",
            ))

    return flags


def _check_score_clustering(
    scored_risks: list[ScoredRisk],
) -> list[ConsistencyFlag]:
    """Flag if all risks cluster at the same rating (suggests lazy scoring)."""
    flags: list[ConsistencyFlag] = []

    if len(scored_risks) < 5:
        return flags

    rating_counts = Counter(r.risk_rating for r in scored_risks)
    most_common_rating, most_common_count = rating_counts.most_common(1)[0]

    # If >75% of risks have the same rating, flag it
    if most_common_count / len(scored_risks) > 0.75:
        flags.append(ConsistencyFlag(
            risk_id="ALL",
            flag_type="SCORE_CLUSTERING",
            description=(
                f"{most_common_count}/{len(scored_risks)} risks rated as "
                f"'{most_common_rating}'. Score distribution may indicate "
                f"insufficient differentiation."
            ),
            related_risk_ids=[r.risk_id for r in scored_risks],
            recommended_adjustment=(
                "Review scoring to ensure each risk is assessed independently "
                "based on its own evidence."
            ),
            severity="MEDIUM",
        ))

    return flags
