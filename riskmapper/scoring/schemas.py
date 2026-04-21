"""Pydantic v2 data models for the Phase 2 risk scoring pipeline.

Defines structured output schemas for each agent in the scoring chain:
evidence context, knowledge summary, likelihood intelligence, scoring,
and consistency checking.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Evidence Context (assembled from Phase 1 data — NOT a separate LLM agent)
# ---------------------------------------------------------------------------

class EvidenceContext(BaseModel):
    """Assembled evidence package for a single risk.

    Built from Phase 1 output — verbatim_evidence, question_source,
    cascade_context, and surrounding transcript context. This is a data
    assembly step, not an LLM agent call (per critique: Evidence Retriever
    merged into Scoring Agent context prep).
    """

    risk_id: str
    client_description: str
    verbatim_quotes: list[str]
    question_sources: list[str]
    surrounding_context: list[str]
    cascade_evidence: str | None = None
    cross_risk_references: list[str]
    evidence_strength: Literal["STRONG", "MODERATE", "WEAK"]
    risk_type: Literal["INHERENT", "EVENT_DRIVEN", "BOTH"]
    flags: list[Literal["UNREGISTERED", "UNDERPREPARED", "CASCADE_SIGNAL"]]


# ---------------------------------------------------------------------------
# Knowledge Summarizer output
# ---------------------------------------------------------------------------

class CompanyProfile(BaseModel):
    """Core company profile extracted once and reused across all risks."""

    sector: str
    sub_sector: str
    headquarters: str
    annual_revenue: str
    employee_count: str
    operating_geographies: list[str]
    key_strategic_priorities: list[str]


class KnowledgeContext(BaseModel):
    """Structured client context from the questionnaire for a specific risk.

    100% grounded in client-provided data. Fields not found in the
    questionnaire are marked NOT_PROVIDED — never inferred.
    """

    risk_id: str
    company_profile: CompanyProfile
    risk_relevant_context: dict[str, str]
    data_source: Literal["client_questionnaire"] = "client_questionnaire"
    completeness: Literal["FULL", "PARTIAL", "MINIMAL"]


class _LLMKnowledgeContext(BaseModel):
    """LLM response model for knowledge summarizer — no risk_id needed."""

    risk_relevant_context: dict[str, str]
    completeness: Literal["FULL", "PARTIAL", "MINIMAL"]


# ---------------------------------------------------------------------------
# Likelihood Intelligence output (renamed from Market Research Agent per
# critique: market research is ONE input, not THE input)
# ---------------------------------------------------------------------------

class LikelihoodFactorScore(BaseModel):
    """Score for a single likelihood factor (1-5) with justification."""

    factor: str
    score: int
    justification: str
    data_sources_used: list[str]

    @field_validator("score", mode="after")
    @classmethod
    def _validate_score(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError(f"Factor score must be 1-5, got {v}")
        return v


class LikelihoodIntelligence(BaseModel):
    """Multi-factor likelihood assessment per the 5-factor methodology.

    Factors (per critique of original architecture):
    1. Historical Frequency (25%) — from transcript + questionnaire
    2. Control Effectiveness (25%) — from transcript + questionnaire
    3. External Environment / Velocity (20%) — market research + transcript
    4. Sector Base Rate (15%) — sector knowledge + registry
    5. Client-Specific Exposure (15%) — questionnaire + transcript
    """

    risk_id: str
    factor_scores: list[LikelihoodFactorScore]
    composite_score: float
    composite_rounded: int
    adjustment_applied: str | None = None
    confidence: Literal["HIGH", "MEDIUM", "LOW"]

    @field_validator("composite_rounded", mode="after")
    @classmethod
    def _validate_composite(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError(f"Composite likelihood must be 1-5, got {v}")
        return v


class _LLMLikelihoodEvidence(BaseModel):
    """LLM answers specific evidence questions — scores computed in code.

    Instead of asking the LLM to pick 1-5 (which it anchors at 4),
    we ask factual yes/no/specific questions and map to scores in code.
    """

    # Factor 1: Historical Frequency
    has_occurred_at_client: bool
    how_recently: str  # "never", "over_5_years_ago", "3_to_5_years", "1_to_2_years", "currently_occurring"
    occurrence_details: str

    # Factor 2: Control Effectiveness
    controls_exist: bool
    controls_tested: bool
    client_control_confidence: str  # "high", "moderate", "low", "none"
    control_details: str

    # Factor 3: External Environment
    external_drivers_present: bool
    risk_velocity: str  # "stable", "slow_build", "moderate", "rapid", "imminent"
    external_details: str

    # Factor 4: Sector Base Rate
    common_in_sector: str  # "extremely_rare", "uncommon", "periodic", "common", "systemic"
    sector_details: str

    # Factor 5: Client-Specific Exposure
    client_exposure_vs_peers: str  # "below_average", "average", "above_average", "significantly_above", "extreme"
    exposure_details: str

    confidence: Literal["HIGH", "MEDIUM", "LOW"]


# ---------------------------------------------------------------------------
# Scoring Agent output
# ---------------------------------------------------------------------------

class ImpactAssessment(BaseModel):
    """Impact score with full table-grounded justification."""

    score: int
    level: str
    dimension: str
    sub_dimension: str
    metric: str
    justification: str
    table_criteria_matched: str
    evidence_quantity: str  # The specific number/quantity from evidence (e.g., "42 days", "EUR 400M", "22%")
    quantity_source: str  # Where the quantity came from: "client_stated", "questionnaire", "calculated", "estimated"

    @field_validator("score", mode="after")
    @classmethod
    def _validate_score(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError(f"Impact score must be 1-5, got {v}")
        return v


class LikelihoodAssessment(BaseModel):
    """Likelihood score with evidence-basis tracking."""

    score: int
    level: str
    justification: str
    evidence_basis: Literal[
        "CLIENT_STATED", "EXTERNAL_INTELLIGENCE", "BOTH", "INSUFFICIENT"
    ]
    table_criteria_matched: str

    @field_validator("score", mode="after")
    @classmethod
    def _validate_score(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError(f"Likelihood score must be 1-5, got {v}")
        return v


class CascadeScoringImpact(BaseModel):
    """Cascade relationship metadata for a scored risk."""

    upstream_risks: list[str]
    downstream_risks: list[str]
    cascade_likelihood_adjustment: float | None = None


class ExternalIntelligenceUsed(BaseModel):
    """External intelligence data that was used in scoring — for audit trail."""

    search_queries: list[str]
    recent_incidents: list[str]
    regulatory_developments: list[str]
    market_trends: list[str]
    external_likelihood_signal: str
    sources: list[str]
    data_freshness: str


class ScoredRisk(BaseModel):
    """Complete scoring output for a single risk.

    Every score references specific table criteria. If the agent cannot
    map to a criterion, it flags for human review rather than guessing.
    """

    risk_id: str
    client_description: str
    impact_assessment: ImpactAssessment
    likelihood_assessment: LikelihoodAssessment
    inherent_risk_score: int
    risk_rating: Literal["Low", "Medium", "High", "Critical"]
    scoring_confidence: Literal["HIGH", "MEDIUM", "LOW"]
    evidence_summary: str
    client_context_used: str
    market_intelligence_used: ExternalIntelligenceUsed | None = None
    consistency_notes: str
    flags_for_review: list[str]
    cascade_scoring_impact: CascadeScoringImpact

    @field_validator("inherent_risk_score", mode="after")
    @classmethod
    def _validate_inherent(cls, v: int) -> int:
        if v < 1 or v > 25:
            raise ValueError(f"Inherent risk score must be 1-25, got {v}")
        return v


class _LLMScoredRisk(BaseModel):
    """LLM response model for the scoring agent."""

    impact_assessment: ImpactAssessment
    likelihood_assessment: LikelihoodAssessment
    inherent_risk_score: int
    risk_rating: Literal["Low", "Medium", "High", "Critical"]
    scoring_confidence: Literal["HIGH", "MEDIUM", "LOW"]
    evidence_summary: str
    client_context_used: str
    consistency_notes: str
    flags_for_review: list[str]
    cascade_scoring_impact: CascadeScoringImpact


# ---------------------------------------------------------------------------
# Consistency Checker output
# ---------------------------------------------------------------------------

class ConsistencyFlag(BaseModel):
    """A single inconsistency flagged by the post-scoring checker."""

    risk_id: str
    flag_type: Literal[
        "RELATED_RISK_COHERENCE",
        "CASCADE_COHERENCE",
        "DIMENSION_CONSISTENCY",
        "OUTLIER",
        "SCORE_CLUSTERING",
    ]
    description: str
    related_risk_ids: list[str]
    recommended_adjustment: str | None = None
    severity: Literal["HIGH", "MEDIUM", "LOW"]


class ConsistencyCheckResult(BaseModel):
    """Full output of the post-scoring consistency check."""

    total_risks_checked: int
    flags: list[ConsistencyFlag]
    score_distribution: dict[str, int]
    overall_assessment: str


# ---------------------------------------------------------------------------
# Compact Memory (per critique: structured and compact, not full
# justifications — ~50 tokens per risk in the summary table)
# ---------------------------------------------------------------------------

class ScoredRiskSummary(BaseModel):
    """Compact summary of a scored risk for memory/context window.

    Kept small (~50 tokens) so all scored risks fit in context without
    blowing the window. Full justifications are NOT included in memory.
    """

    risk_id: str
    client_description: str
    impact_score: int
    likelihood_score: int
    inherent_score: int
    risk_rating: str
    dimension: str
    flags: list[str]


class ScoringMemory(BaseModel):
    """Cross-risk state maintained during scoring pipeline.

    Per critique: memory is structured and compact — client profile
    (~500 tokens), scored risk summary table (~50 tokens per risk),
    and cascade dependency graph (~200 tokens). NOT full justifications.
    """

    client_profile: CompanyProfile
    scored_risks: list[ScoredRiskSummary]
    cascade_graph: dict[str, list[str]]


# ---------------------------------------------------------------------------
# Pipeline-level output
# ---------------------------------------------------------------------------

class ScoringPipelineResult(BaseModel):
    """Final output of the Phase 2 scoring pipeline."""

    scored_risks: list[ScoredRisk]
    consistency_check: ConsistencyCheckResult | None = None
    total_risks: int
    scoring_summary: ScoringPipelineSummary


class ScoringPipelineSummary(BaseModel):
    """Aggregate statistics for the scoring run."""

    total_scored: int
    low_count: int
    medium_count: int
    high_count: int
    critical_count: int
    human_review_count: int
    average_confidence: str
