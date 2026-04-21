"""Likelihood Intelligence Agent — evidence-based likelihood scoring.

Instead of asking the LLM to pick scores 1-5 (which it anchors at 4),
this module asks the LLM specific factual questions about the evidence,
then maps the answers to scores deterministically in Python.

Uses 5-factor methodology:
  F1: Historical Frequency (25%)
  F2: Control Effectiveness (25%)
  F3: External Environment / Velocity (20%)
  F4: Sector Base Rate (15%)
  F5: Client-Specific Exposure (15%)
"""

from __future__ import annotations

import json
import logging

from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.scoring.schemas import (
    EvidenceContext,
    KnowledgeContext,
    LikelihoodFactorScore,
    LikelihoodIntelligence,
    ScoringMemory,
    _LLMLikelihoodEvidence,
)
from riskmapper.scoring.external_intelligence import ExternalIntelligence

logger = logging.getLogger(__name__)

# Weights for the 5-factor composite
_WEIGHTS = {
    "historical_frequency": 0.25,
    "control_effectiveness": 0.25,
    "external_environment": 0.20,
    "sector_base_rate": 0.15,
    "client_specific_exposure": 0.15,
}

# Deterministic mappings: LLM answer → score
_RECENCY_MAP = {
    "never": 1,
    "over_5_years_ago": 2,
    "3_to_5_years": 3,
    "1_to_2_years": 4,
    "currently_occurring": 5,
}

_VELOCITY_MAP = {
    "stable": 1,
    "slow_build": 2,
    "moderate": 3,
    "rapid": 4,
    "imminent": 5,
}

_SECTOR_MAP = {
    "extremely_rare": 1,
    "uncommon": 2,
    "periodic": 3,
    "common": 4,
    "systemic": 5,
}

_EXPOSURE_MAP = {
    "below_average": 1,
    "average": 2,
    "above_average": 3,
    "significantly_above": 4,
    "extreme": 5,
}


def _compute_control_score(evidence: _LLMLikelihoodEvidence) -> int:
    """Map control evidence to a score deterministically."""
    if not evidence.controls_exist:
        return 5
    if evidence.client_control_confidence == "none":
        return 5
    if not evidence.controls_tested:
        if evidence.client_control_confidence == "low":
            return 4
        return 3
    if evidence.client_control_confidence == "high":
        return 1
    if evidence.client_control_confidence == "moderate":
        return 2
    return 3


def assess_likelihood(
    evidence: EvidenceContext,
    knowledge: KnowledgeContext,
    likelihood_table: dict,
    memory: ScoringMemory,
    llm: LLMWrapper,
    external_intel: ExternalIntelligence | None = None,
) -> LikelihoodIntelligence:
    """Produce a multi-factor likelihood assessment.

    The LLM answers factual questions. Python maps answers to scores
    and computes the weighted composite. No LLM math or score picking.
    """
    prompt = _build_evidence_prompt(evidence, knowledge, memory, external_intel)

    result = llm.call(
        prompt=prompt,
        response_model=_LLMLikelihoodEvidence,
        temperature=0.0,
        step_name=f"likelihood_intelligence_{evidence.risk_id}",
    )

    # Map LLM answers to scores IN CODE
    f1 = _RECENCY_MAP.get(result.how_recently, 3)
    if not result.has_occurred_at_client and f1 > 2:
        f1 = 2  # Cap at 2 if never occurred at client

    f2 = _compute_control_score(result)

    f3 = _VELOCITY_MAP.get(result.risk_velocity, 3)
    if not result.external_drivers_present and f3 > 2:
        f3 = 2

    f4 = _SECTOR_MAP.get(result.common_in_sector, 3)

    f5 = _EXPOSURE_MAP.get(result.client_exposure_vs_peers, 3)

    # Clamp all to 1-5
    factors = {
        "historical_frequency": max(1, min(5, f1)),
        "control_effectiveness": max(1, min(5, f2)),
        "external_environment": max(1, min(5, f3)),
        "sector_base_rate": max(1, min(5, f4)),
        "client_specific_exposure": max(1, min(5, f5)),
    }

    # Compute weighted composite IN CODE
    composite_raw = sum(
        factors[name] * weight for name, weight in _WEIGHTS.items()
    )

    # Apply adjustment rules
    adjustment = None
    if "UNDERPREPARED" in evidence.flags and any(v == 5 for v in factors.values()):
        if composite_raw < 3.0:
            adjustment = "Floor applied: UNDERPREPARED + factor=5 → minimum 3.0"
            composite_raw = 3.0

    if "CASCADE_SIGNAL" in evidence.flags:
        upstream_high = any(
            sr.likelihood_score >= 4
            for sr in memory.scored_risks
            if sr.risk_id in (evidence.cross_risk_references or [])
        )
        if upstream_high:
            composite_raw += 0.5
            adjustment = (adjustment or "") + " CASCADE boost +0.5"

    composite_rounded = max(1, min(5, round(composite_raw)))

    # Build factor score objects with justifications from LLM
    factor_scores = [
        LikelihoodFactorScore(
            factor="Historical Frequency",
            score=factors["historical_frequency"],
            justification=f"{'Occurred' if result.has_occurred_at_client else 'Not occurred'} at client ({result.how_recently}). {result.occurrence_details}",
            data_sources_used=["transcript", "questionnaire"],
        ),
        LikelihoodFactorScore(
            factor="Control Effectiveness",
            score=factors["control_effectiveness"],
            justification=f"Controls {'exist' if result.controls_exist else 'do not exist'}, {'tested' if result.controls_tested else 'untested'}, confidence={result.client_control_confidence}. {result.control_details}",
            data_sources_used=["transcript", "questionnaire"],
        ),
        LikelihoodFactorScore(
            factor="External Environment",
            score=factors["external_environment"],
            justification=f"External drivers {'present' if result.external_drivers_present else 'not present'}, velocity={result.risk_velocity}. {result.external_details}",
            data_sources_used=["transcript", "external_intelligence"],
        ),
        LikelihoodFactorScore(
            factor="Sector Base Rate",
            score=factors["sector_base_rate"],
            justification=f"Sector frequency: {result.common_in_sector}. {result.sector_details}",
            data_sources_used=["sector_calibration", "external_intelligence"],
        ),
        LikelihoodFactorScore(
            factor="Client-Specific Exposure",
            score=factors["client_specific_exposure"],
            justification=f"Client exposure vs peers: {result.client_exposure_vs_peers}. {result.exposure_details}",
            data_sources_used=["questionnaire", "transcript"],
        ),
    ]

    logger.info(
        "%s likelihood: F1=%d F2=%d F3=%d F4=%d F5=%d → raw=%.2f → rounded=%d",
        evidence.risk_id, *factors.values(), composite_raw, composite_rounded,
    )

    return LikelihoodIntelligence(
        risk_id=evidence.risk_id,
        factor_scores=factor_scores,
        composite_score=composite_raw,
        composite_rounded=composite_rounded,
        adjustment_applied=adjustment,
        confidence=result.confidence,
    )


def _build_evidence_prompt(
    evidence: EvidenceContext,
    knowledge: KnowledgeContext,
    memory: ScoringMemory,
    external_intel: ExternalIntelligence | None = None,
) -> str:
    """Build a prompt that asks factual questions, not score requests."""

    knowledge_text = json.dumps(knowledge.risk_relevant_context, indent=2)
    ext_text = _format_external_intel(external_intel)
    memory_text = _format_memory(memory)

    return f"""You are an evidence analyst for enterprise risk management.

TASK: Answer the following factual questions about this risk based ONLY on the evidence provided.
Do NOT pick scores. Just answer the questions honestly based on what the data shows.

RISK: {evidence.risk_id} — {evidence.client_description}
TYPE: {evidence.risk_type}
FLAGS: {', '.join(evidence.flags) if evidence.flags else 'None'}

VERBATIM EVIDENCE FROM CLIENT:
{_format_quotes(evidence.verbatim_quotes)}

CLIENT QUESTIONNAIRE DATA:
{knowledge_text}

EXTERNAL MARKET INTELLIGENCE:
{ext_text}

PREVIOUSLY SCORED RISKS (for context):
{memory_text}

=== ANSWER THESE QUESTIONS ===

QUESTION 1 — HISTORICAL FREQUENCY:
- has_occurred_at_client: Has this SPECIFIC risk actually materialized at this client? (true/false)
- how_recently: When? Choose ONE: "never", "over_5_years_ago", "3_to_5_years", "1_to_2_years", "currently_occurring"
  - "never" = no evidence it happened at this client
  - "over_5_years_ago" = happened but >5 years ago
  - "3_to_5_years" = happened 3-5 years ago
  - "1_to_2_years" = happened in last 1-2 years
  - "currently_occurring" = happening right now or multiple recent times
- occurrence_details: One sentence citing the specific evidence.

QUESTION 2 — CONTROL EFFECTIVENESS:
- controls_exist: Does the client have controls for this risk? (true/false)
- controls_tested: Have those controls been tested under real conditions? (true/false)
- client_control_confidence: What confidence level did the CLIENT express? Choose ONE: "high", "moderate", "low", "none"
  - "high" = client said "strong controls, tested constantly" or similar
  - "moderate" = client said controls exist but with some gaps
  - "low" = client said controls are weak, untested, or incomplete
  - "none" = client said no controls or explicitly underprepared
- control_details: One sentence citing what the client said about controls.

QUESTION 3 — EXTERNAL ENVIRONMENT:
- external_drivers_present: Are there active external factors driving this risk? (true/false)
- risk_velocity: How fast could this risk materialize? Choose ONE: "stable", "slow_build", "moderate", "rapid", "imminent"
  - "stable" = no change expected
  - "slow_build" = gradual, over months/years
  - "moderate" = could develop over weeks/months
  - "rapid" = could develop in days/weeks
  - "imminent" = could happen within 24-48 hours (client said "overnight risk")
- external_details: One sentence citing external factors from the evidence or market intelligence.

QUESTION 4 — SECTOR BASE RATE:
- common_in_sector: How common is this risk in the automotive sector? Choose ONE: "extremely_rare", "uncommon", "periodic", "common", "systemic"
- sector_details: One sentence explaining why.

QUESTION 5 — CLIENT-SPECIFIC EXPOSURE:
- client_exposure_vs_peers: How exposed is THIS client compared to peers? Choose ONE: "below_average", "average", "above_average", "significantly_above", "extreme"
- exposure_details: One sentence citing specific client data (geography, concentration, dependencies).

CONFIDENCE: Overall confidence in your answers — "HIGH", "MEDIUM", or "LOW".

IMPORTANT: Answer based on EVIDENCE, not assumptions. If the client said "strong controls, tested constantly" for this risk, then controls_tested MUST be true and client_control_confidence MUST be "high". If there is NO evidence of this risk occurring at the client, has_occurred_at_client MUST be false."""


def _format_quotes(quotes: list[str]) -> str:
    if not quotes:
        return "  (none)"
    return "\n".join(f'  - "{q}"' for q in quotes[:6])


def _format_external_intel(ext_intel) -> str:
    if ext_intel is None:
        return "  (no external intelligence available)"
    lines = []
    lines.append(f"  Signal: {ext_intel.external_likelihood_signal}")
    if ext_intel.recent_incidents:
        for inc in ext_intel.recent_incidents[:3]:
            lines.append(f"  - Incident: {inc}")
    if ext_intel.regulatory_developments:
        for reg in ext_intel.regulatory_developments[:3]:
            lines.append(f"  - Regulatory: {reg}")
    if ext_intel.market_trends:
        for trend in ext_intel.market_trends[:3]:
            lines.append(f"  - Trend: {trend}")
    return "\n".join(lines)


def _format_memory(memory: ScoringMemory) -> str:
    if not memory.scored_risks:
        return "  (no risks scored yet)"
    lines = []
    for sr in memory.scored_risks:
        lines.append(
            f"  {sr.risk_id}: {sr.client_description} | "
            f"I={sr.impact_score} L={sr.likelihood_score} ({sr.risk_rating})"
        )
    return "\n".join(lines)
