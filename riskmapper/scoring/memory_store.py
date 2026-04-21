"""Cross-risk memory store for the scoring pipeline.

Per architecture critique: memory is structured and compact.
- Client profile: ~500 tokens (extracted once)
- Scored risk summary table: ~50 tokens per risk
- Cascade dependency graph: ~200 tokens
- NOT full justifications — those are too verbose for memory.
"""

from __future__ import annotations

import logging

from riskmapper.scoring.schemas import (
    CompanyProfile,
    ScoredRisk,
    ScoredRiskSummary,
    ScoringMemory,
)

logger = logging.getLogger(__name__)


class MemoryStore:
    """In-memory state store for cross-risk context during scoring."""

    def __init__(self, client_profile: CompanyProfile) -> None:
        self._profile = client_profile
        self._scored: list[ScoredRiskSummary] = []
        self._cascade_graph: dict[str, list[str]] = {}

    def get_memory(self) -> ScoringMemory:
        """Return the current compact memory snapshot."""
        return ScoringMemory(
            client_profile=self._profile,
            scored_risks=list(self._scored),
            cascade_graph=dict(self._cascade_graph),
        )

    def record_scored_risk(self, scored: ScoredRisk) -> None:
        """Add a scored risk to memory (compact summary only)."""
        summary = ScoredRiskSummary(
            risk_id=scored.risk_id,
            client_description=scored.client_description,
            impact_score=scored.impact_assessment.score,
            likelihood_score=scored.likelihood_assessment.score,
            inherent_score=scored.inherent_risk_score,
            risk_rating=scored.risk_rating,
            dimension=scored.impact_assessment.dimension,
            flags=scored.flags_for_review,
        )
        self._scored.append(summary)

        # Update cascade graph
        cascade = scored.cascade_scoring_impact
        if cascade.upstream_risks:
            self._cascade_graph[scored.risk_id] = cascade.upstream_risks
        if cascade.downstream_risks:
            for downstream in cascade.downstream_risks:
                if downstream not in self._cascade_graph:
                    self._cascade_graph[downstream] = []
                if scored.risk_id not in self._cascade_graph[downstream]:
                    self._cascade_graph[downstream].append(scored.risk_id)

        logger.debug(
            "Memory updated: %s scored (I=%d L=%d S=%d %s)",
            scored.risk_id,
            summary.impact_score,
            summary.likelihood_score,
            summary.inherent_score,
            summary.risk_rating,
        )

    @property
    def scored_count(self) -> int:
        return len(self._scored)

    @property
    def cascade_graph(self) -> dict[str, list[str]]:
        return dict(self._cascade_graph)
