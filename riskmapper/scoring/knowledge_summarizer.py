"""Knowledge Summarizer Agent — extracts relevant client context per risk.

100% grounded in client-provided questionnaire data. If data is not
available, marks as NOT_PROVIDED — never infers or hallucinates.
"""

from __future__ import annotations

import json
import logging

from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.scoring.schemas import (
    CompanyProfile,
    EvidenceContext,
    KnowledgeContext,
    _LLMKnowledgeContext,
)

logger = logging.getLogger(__name__)


def extract_company_profile(questionnaire: dict) -> CompanyProfile:
    """Extract the core company profile from the questionnaire (once).

    This is called once at pipeline start and reused for all risks.
    Keeps memory compact (~500 tokens) per the architecture critique.
    """
    section_a = questionnaire.get("section_a_company_profile_strategy", {})

    def _answer(key: str) -> str:
        entry = section_a.get(key, {})
        return entry.get("answer", "NOT_PROVIDED")

    # Parse headquarters from A1 — look for "Headquarters: ..." pattern
    a1 = _answer("A1")
    hq = "NOT_PROVIDED"
    if a1 != "NOT_PROVIDED":
        if "Headquarters:" in a1:
            hq = a1.split("Headquarters:")[1].split(".")[0].strip()
        else:
            hq = a1

    # Parse operating geographies from A6 — split on ". " for sentence boundaries
    a6 = _answer("A6")
    geographies: list[str] = []
    if a6 != "NOT_PROVIDED":
        # Keep the structured segments (Manufacturing: ..., R&D: ..., Sales: ...)
        for segment in a6.split(". "):
            segment = segment.strip().rstrip(".")
            if segment:
                geographies.append(segment)

    # Parse strategic priorities from A7 — split on numbered items
    a7 = _answer("A7")
    priorities: list[str] = []
    if a7 != "NOT_PROVIDED":
        import re
        parts = re.split(r'\d+\.\s+', a7)
        for part in parts:
            cleaned = part.strip().rstrip(".")
            if cleaned:
                priorities.append(cleaned)
        if not priorities:
            priorities = [a7[:200]]

    # Parse revenue — take the first sentence for a concise summary
    a3 = _answer("A3")
    revenue = "NOT_PROVIDED"
    if a3 != "NOT_PROVIDED":
        # Take up to the first period that follows a currency/number
        first_sentence = a3.split(". ")[0].strip()
        revenue = first_sentence

    return CompanyProfile(
        sector=questionnaire.get("sector", "NOT_PROVIDED"),
        sub_sector=questionnaire.get("sub_sector", "NOT_PROVIDED"),
        headquarters=hq,
        annual_revenue=revenue,
        employee_count=_answer("A5").split(".")[0].strip() if _answer("A5") != "NOT_PROVIDED" else "NOT_PROVIDED",
        operating_geographies=geographies,
        key_strategic_priorities=priorities,
    )


def summarize_knowledge(
    evidence: EvidenceContext,
    questionnaire: dict,
    company_profile: CompanyProfile,
    llm: LLMWrapper,
) -> KnowledgeContext:
    """Extract risk-relevant context from the questionnaire via LLM.

    The LLM identifies which questionnaire fields are relevant to this
    specific risk and extracts them. It MUST NOT infer or add data
    beyond what the questionnaire contains.

    Args:
        evidence: The assembled evidence context for this risk.
        questionnaire: Full parsed questionnaire dict.
        company_profile: Pre-extracted company profile.
        llm: LLM wrapper instance.

    Returns:
        KnowledgeContext with risk-relevant questionnaire data.
    """
    prompt = _build_knowledge_prompt(evidence, questionnaire)

    result = llm.call(
        prompt=prompt,
        response_model=_LLMKnowledgeContext,
        temperature=0.0,
        step_name=f"knowledge_summarizer_{evidence.risk_id}",
    )

    return KnowledgeContext(
        risk_id=evidence.risk_id,
        company_profile=company_profile,
        risk_relevant_context=result.risk_relevant_context,
        completeness=result.completeness,
    )


def _build_knowledge_prompt(
    evidence: EvidenceContext,
    questionnaire: dict,
) -> str:
    """Build the prompt for the Knowledge Summarizer LLM call.

    Token optimization: only include questionnaire sections likely relevant
    to this risk type, rather than the full 6K-token questionnaire.
    """
    # Select relevant sections based on risk description and flags
    q_text = _flatten_questionnaire_selective(questionnaire, evidence)

    return f"""You are a Knowledge Summarizer Agent for enterprise risk management.

TASK: Extract ONLY the questionnaire data relevant to scoring this risk.

RISK:
- ID: {evidence.risk_id}
- Description: {evidence.client_description}
- Type: {evidence.risk_type}
- Flags: {', '.join(evidence.flags) if evidence.flags else 'None'}
- Key evidence: {'; '.join(evidence.verbatim_quotes[:2])}

QUESTIONNAIRE DATA:
{q_text}

RULES:
1. Extract ONLY data that exists above. If not available, use "NOT_PROVIDED".
2. NEVER infer or hallucinate. Focus on data affecting impact/likelihood scoring.
3. Include: controls, incidents, exposure, financial metrics relevant to THIS risk.

COMPLETENESS: FULL (comprehensive data available) / PARTIAL (some gaps) / MINIMAL (very little).

Return risk_relevant_context as a dict of descriptive keys to questionnaire values."""


def _flatten_questionnaire(questionnaire: dict) -> str:
    """Flatten the nested questionnaire JSON into readable text."""
    lines: list[str] = []

    for section_key, section_data in questionnaire.items():
        if not isinstance(section_data, dict):
            continue
        if section_key in ("client", "sector", "sub_sector", "completed_by", "date_completed"):
            continue

        section_title = section_key.replace("section_", "Section ").replace("_", " ").title()
        lines.append(f"\n--- {section_title} ---")

        for q_key, q_data in section_data.items():
            if isinstance(q_data, dict) and "question" in q_data:
                lines.append(f"{q_key}: {q_data['question']}")
                lines.append(f"  Answer: {q_data.get('answer', 'NOT_PROVIDED')}")

    return "\n".join(lines)


def _flatten_questionnaire_selective(
    questionnaire: dict,
    evidence: EvidenceContext,
) -> str:
    """Flatten only the questionnaire sections relevant to this risk.

    Token optimization: instead of dumping all 75 questions (~6K tokens),
    select 2-3 relevant sections (~2K tokens) based on risk keywords.
    Always includes Section A (company profile) as baseline context.
    """
    desc_lower = evidence.client_description.lower()
    flags = [f.lower() for f in evidence.flags]
    quotes_lower = " ".join(evidence.verbatim_quotes).lower()
    combined = desc_lower + " " + quotes_lower

    # Map keywords to relevant questionnaire sections
    section_relevance = {
        "section_a_company_profile_strategy": 1.0,  # Always include (compact)
        "section_b_operations_supply_chain": _relevance_score(
            combined, ["supply", "chain", "supplier", "logistics", "production",
                       "manufacturing", "plant", "inventory", "disruption",
                       "material", "commodity", "recall", "quality"]
        ),
        "section_c_technology_cyber": _relevance_score(
            combined, ["cyber", "technology", "software", "IT", "OT", "digital",
                       "data", "system", "connected", "vehicle", "hack",
                       "ransomware", "automation"]
        ),
        "section_d_regulatory_compliance": _relevance_score(
            combined, ["regulatory", "compliance", "emission", "regulation",
                       "fine", "penalty", "certification", "ESG", "tariff",
                       "trade", "policy", "euro 7", "CSRD"]
        ),
        "section_e_financial_market": _relevance_score(
            combined, ["financial", "revenue", "cost", "currency", "margin",
                       "capital", "debt", "market share", "customer",
                       "pricing", "liquidity", "capex"]
        ),
        "section_f_people_health_safety": _relevance_score(
            combined, ["workforce", "labour", "union", "talent", "skill",
                       "safety", "strike", "employee", "restructuring",
                       "turnover", "people"]
        ),
        "section_g_reputation_esg": _relevance_score(
            combined, ["reputation", "brand", "media", "ESG", "sustainability",
                       "ethics", "trust", "rating"]
        ),
        "section_h_governance_risk_maturity": _relevance_score(
            combined, ["governance", "control", "risk management", "framework",
                       "crisis", "scenario", "board", "maturity"]
        ),
    }

    # Always include section A + top 2 most relevant sections
    selected_sections = ["section_a_company_profile_strategy"]
    ranked = sorted(
        [(k, v) for k, v in section_relevance.items()
         if k != "section_a_company_profile_strategy"],
        key=lambda x: x[1],
        reverse=True,
    )
    for section_key, score in ranked[:2]:
        if score > 0:
            selected_sections.append(section_key)

    # If UNDERPREPARED flag, always include governance section
    if "underprepared" in " ".join(flags):
        if "section_h_governance_risk_maturity" not in selected_sections:
            selected_sections.append("section_h_governance_risk_maturity")

    # Flatten selected sections
    lines: list[str] = []
    for section_key in selected_sections:
        section_data = questionnaire.get(section_key, {})
        if not isinstance(section_data, dict):
            continue
        section_title = section_key.replace("section_", "").replace("_", " ").title()
        lines.append(f"\n--- {section_title} ---")
        for q_key, q_data in section_data.items():
            if isinstance(q_data, dict) and "question" in q_data:
                lines.append(f"{q_key}: {q_data['question']}")
                lines.append(f"  → {q_data.get('answer', 'NOT_PROVIDED')}")

    return "\n".join(lines)


def _relevance_score(text: str, keywords: list[str]) -> float:
    """Score how relevant a section is based on keyword matches."""
    matches = sum(1 for kw in keywords if kw.lower() in text)
    return matches / len(keywords) if keywords else 0.0
