"""Dimension Classifier — mini-agent that picks the primary impact dimension.

Runs BEFORE the Scoring Agent. Single focused LLM call with one job:
given a risk description + evidence, classify which of the 7 impact
dimensions is the PRIMARY channel of impact.

The Scoring Agent then receives this as a constraint and scores
within that dimension only.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.scoring.schemas import EvidenceContext, KnowledgeContext

logger = logging.getLogger(__name__)

# The 7 impact dimensions with clear definitions
_DIMENSIONS = {
    "Financial & Growth Impact": "Revenue decline, margin compression, cost increases, liquidity stress, capex overruns, demand volatility, pricing pressure. Use ONLY when the risk DIRECTLY hits financial metrics — not as a secondary consequence of an operational or regulatory event.",
    "Operating Impact": "Production downtime, equipment failure, capacity drop, supply chain disruption, inventory shortage, logistics disruption, maintenance issues. Use when the risk DISRUPTS operations, production, or supply chain.",
    "Customer & Market Impact": "Order cancellations, customer loss, quality complaints, delivery failures, market share loss, brand trust decline, competitive disadvantage. Use when the risk affects CUSTOMERS, DEMAND, or MARKET POSITION.",
    "Regulatory & Compliance Impact": "Environmental breaches, emissions violations, product safety non-compliance, certification loss, trade violations, labour law violations, H&S citations, regulatory fines. Use when the risk involves REGULATORY ACTION, COMPLIANCE FAILURE, or LEGAL consequences.",
    "Technology & Information Impact": "IT/OT system failures, cyber incidents, data breaches, automation failures, vendor technology failures, disaster recovery breaches. Use when the risk involves TECHNOLOGY SYSTEMS, CYBER SECURITY, or DATA.",
    "People, Health & Safety Impact": "Workplace injuries, skilled labour shortage, occupational illness, contractor incidents, industrial action/strikes, H&S breaches. Use when the risk affects WORKFORCE, LABOUR RELATIONS, or SAFETY.",
    "Reputation & Ethics Impact": "Negative media coverage, product recall reputation damage, customer trust loss, ethical misconduct, ESG rating downgrades, stakeholder trust erosion. Use when the risk primarily damages BRAND, REPUTATION, or STAKEHOLDER TRUST.",
}


class _LLMDimensionChoice(BaseModel):
    """LLM response — just the dimension choice and reasoning."""

    primary_dimension: str
    reasoning: str
    secondary_dimension: str


def classify_dimension(
    evidence: EvidenceContext,
    knowledge: KnowledgeContext,
    llm: LLMWrapper,
) -> str:
    """Classify the primary impact dimension for a risk.

    Args:
        evidence: Assembled evidence context.
        knowledge: Client questionnaire context.
        llm: LLM wrapper instance.

    Returns:
        The primary dimension name (one of the 7 dimensions).
    """
    prompt = _build_prompt(evidence, knowledge)

    try:
        result = llm.call(
            prompt=prompt,
            response_model=_LLMDimensionChoice,
            temperature=0.0,
            step_name=f"dimension_classifier_{evidence.risk_id}",
        )

        chosen = result.primary_dimension

        # Validate it's one of the 7 dimensions
        valid_dims = list(_DIMENSIONS.keys())
        if chosen not in valid_dims:
            # Fuzzy match
            for dim in valid_dims:
                if chosen.lower() in dim.lower() or dim.lower() in chosen.lower():
                    chosen = dim
                    break
            else:
                logger.warning(
                    "%s: Invalid dimension '%s' — defaulting to Financial & Growth",
                    evidence.risk_id, chosen,
                )
                chosen = "Financial & Growth Impact"

        logger.info(
            "%s dimension: %s (secondary: %s) — %s",
            evidence.risk_id, chosen, result.secondary_dimension,
            result.reasoning[:100],
        )
        return chosen

    except Exception as exc:
        logger.warning(
            "%s: Dimension classification failed: %s — defaulting to Financial",
            evidence.risk_id, exc,
        )
        return "Financial & Growth Impact"


def _build_prompt(evidence: EvidenceContext, knowledge: KnowledgeContext) -> str:
    """Build a focused, short prompt for dimension classification."""

    dims_text = "\n".join(
        f"  {i+1}. {name}: {desc}"
        for i, (name, desc) in enumerate(_DIMENSIONS.items())
    )

    # Brief evidence summary
    evidence_brief = "; ".join(evidence.verbatim_quotes[:3]) if evidence.verbatim_quotes else "No transcript evidence"

    return f"""You are an impact dimension classifier for enterprise risk management.

TASK: Choose the PRIMARY impact dimension for this risk. Pick the dimension where
the MOST SEVERE and IMMEDIATE consequence occurs if this risk fully materializes.

RISK: {evidence.client_description}
RISK TYPE: {evidence.risk_type}
KEY EVIDENCE: {evidence_brief[:500]}

THE 7 IMPACT DIMENSIONS:
{dims_text}

CLASSIFICATION RULES:
- "Supply chain disruption" → Operating Impact (NOT Financial, even though it costs money)
- "Cyber attack" → Technology & Information Impact (NOT Financial)
- "Emissions non-compliance" → Regulatory & Compliance Impact (NOT Financial)
- "Workforce strikes" → People, Health & Safety Impact (NOT Financial)
- "Market share loss from competition" → Customer & Market Impact (NOT Financial)
- "Product recall" → Regulatory & Compliance Impact (NOT Financial)
- "Tariffs increasing costs" → Financial & Growth Impact (this one IS Financial)
- "Credit rating downgrade" → Financial & Growth Impact (this one IS Financial)
- "Data privacy breach" → Technology & Information Impact (NOT Regulatory)

IMPORTANT: Almost every risk has financial consequences eventually. But the PRIMARY
dimension is where the FIRST and MOST DIRECT impact occurs. A supply chain halt
causes production downtime FIRST (Operating), then revenue loss SECOND (Financial).
Score the FIRST impact, not the downstream financial consequence.

Choose primary_dimension, secondary_dimension, and a one-sentence reasoning."""
