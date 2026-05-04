"""Likelihood Intelligence Agent — evidence-based likelihood scoring.

Instead of asking the LLM to pick scores 1-5 (which it anchors at 4),
this module asks the LLM specific factual questions about the evidence,
then maps the answers to scores deterministically in Python.

INHERENT risk likelihood uses 4 factors (controls excluded):
  F1: Historical Frequency (30%)
  F3: External Environment / Velocity (30%)
  F4: Sector Base Rate (20%)
  F5: Client-Specific Exposure (20%)

F2 (Control Effectiveness) is captured for future RESIDUAL risk
calculation but NOT included in the inherent likelihood composite.
Inherent risk = risk BEFORE controls. Controls reduce residual risk.
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

# Weights for INHERENT risk likelihood (no controls — controls are for residual)
# F2 (Control Effectiveness) is captured but NOT included in the composite.
# It's stored for future residual risk calculation.
_WEIGHTS = {
    "historical_frequency": 0.30,
    "external_environment": 0.30,
    "sector_base_rate": 0.20,
    "client_specific_exposure": 0.20,
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
    # F1: Historical Frequency — binary questions disambiguate the middle
    f1 = _RECENCY_MAP.get(result.how_recently, 3)
    if not result.has_occurred_at_client and f1 > 2:
        f1 = 2  # Cap at 2 if never occurred at client
    if result.has_occurred_at_client_recently and f1 < 4:
        f1 = 4  # Boost if occurred in last 2 years
    if result.has_occurred_multiple_times and f1 < 4:
        f1 = max(f1, 4)  # Multiple occurrences = at least 4

    # F2: Control Effectiveness — binary questions override the middle
    if not result.controls_exist:
        f2 = 5
    elif result.client_explicitly_said_strong and result.controls_tested:
        f2 = 1  # Client said "strong" AND tested = 1
    elif result.client_explicitly_said_strong:
        f2 = 2  # Client said "strong" but not tested = 2
    elif result.client_acknowledged_gaps:
        f2 = 4  # Client acknowledged gaps = 4
    elif result.controls_tested:
        f2 = 2  # Tested but no strong/gap signal = 2
    else:
        f2 = 3  # Controls exist, not tested, no strong signal = 3

    # F3: External Environment — binary questions push away from middle
    f3 = _VELOCITY_MAP.get(result.risk_velocity, 3)
    if result.client_called_it_overnight_risk and f3 < 5:
        f3 = 5  # "Overnight risk" = imminent
    elif result.client_called_it_slow_build and f3 > 2:
        f3 = 2  # "Slow build" = not acute
    if not result.external_drivers_present and f3 > 2:
        f3 = 2

    f4 = _SECTOR_MAP.get(result.common_in_sector, 3)

    # F5: Client Exposure — concentration risk pushes up
    f5 = _EXPOSURE_MAP.get(result.client_exposure_vs_peers, 3)
    if result.client_has_concentration_risk and f5 < 4:
        f5 = 4  # Concentration risk = at least significantly above average

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
            factor="Control Effectiveness (NOT in inherent — for residual use)",
            score=factors["control_effectiveness"],
            justification=f"Controls {'exist' if result.controls_exist else 'do not exist'}, {'tested' if result.controls_tested else 'untested'}. Strong={result.client_explicitly_said_strong}, Gaps={result.client_acknowledged_gaps}. {result.control_details}. NOTE: This factor is captured for residual risk calculation but EXCLUDED from the inherent likelihood composite.",
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
- has_occurred_at_client_recently: Did it happen within the last 2 years? (true/false)
- has_occurred_multiple_times: Has it happened more than once? (true/false)
- how_recently: When? Choose ONE: "never", "over_5_years_ago", "3_to_5_years", "1_to_2_years", "currently_occurring"
- occurrence_details: One sentence citing the specific evidence.

QUESTION 2 — CONTROL EFFECTIVENESS:
- controls_exist: Does the client have controls for this risk? (true/false)
- controls_tested: Have those controls been tested under real conditions? (true/false)
- client_explicitly_said_strong: Did the client use words like "strong", "mature", "confident", "tested constantly" about controls for THIS risk? (true/false — must be explicitly stated, not inferred)
- client_acknowledged_gaps: Did the client say "gap", "weak", "untested", "underprepared", "not where it needs to be" about THIS risk? (true/false — must be explicitly stated)
- control_details: One sentence citing what the client said about controls.

QUESTION 3 — EXTERNAL ENVIRONMENT:
- external_drivers_present: Are there active external factors driving this risk? (true/false)
- client_called_it_overnight_risk: Did the client describe this as an "overnight risk", "24-48 hours", "crisis", or "immediate"? (true/false)
- client_called_it_slow_build: Did the client describe this as "slow-build", "gradual", "erode over time", "quarter by quarter"? (true/false)
- risk_velocity: Choose ONE: "stable", "slow_build", "moderate", "rapid", "imminent"
- external_details: One sentence citing external factors.

QUESTION 4 — SECTOR BASE RATE:
- common_in_sector: Choose ONE: "extremely_rare", "uncommon", "periodic", "common", "systemic"
- sector_details: One sentence explaining why.

QUESTION 5 — CLIENT-SPECIFIC EXPOSURE:
- client_has_concentration_risk: Does the client have concentration risk for this (single supplier, single geography, single customer, etc.)? (true/false)
- client_exposure_vs_peers: Choose ONE: "below_average", "average", "above_average", "significantly_above", "extreme"
- exposure_details: One sentence citing specific client data.

CONFIDENCE: "HIGH", "MEDIUM", or "LOW".

IMPORTANT: The boolean questions MUST be answered based on EXPLICIT evidence only.
- client_explicitly_said_strong = true ONLY if the client literally said "strong controls" or "tested constantly" for THIS risk.
- client_acknowledged_gaps = true ONLY if the client literally said "gap", "weak", "untested", or "underprepared" for THIS risk.
- client_called_it_overnight_risk = true ONLY if the client literally said "overnight", "24-48 hours", or "crisis" for THIS risk.
- Do NOT set these to true based on inference. If the evidence doesn't contain these exact words, set to false."""


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
