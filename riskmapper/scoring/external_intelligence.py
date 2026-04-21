"""External Intelligence Agent — real web search for likelihood enrichment.

Phase 2c: Performs targeted web searches per risk to gather:
- Recent incidents in the sector (has this risk materialized for peers?)
- Regulatory developments (new laws, enforcement actions)
- Market trends (pricing pressure, technology shifts)
- Geopolitical factors (if relevant)

All output is labeled EXTERNAL_INTELLIGENCE with sources cited.
The scoring agent weights this differently from client-stated facts.
"""

from __future__ import annotations

import logging
import time
from typing import Literal

from pydantic import BaseModel

from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.scoring.schemas import EvidenceContext, KnowledgeContext

logger = logging.getLogger(__name__)

# Rate limit for search calls (be respectful to DuckDuckGo)
_SEARCH_DELAY = 2.0


class ExternalIntelligence(BaseModel):
    """Structured external intelligence for a single risk."""

    risk_id: str
    search_queries_used: list[str]
    recent_incidents: list[str]
    regulatory_developments: list[str]
    market_trends: list[str]
    geopolitical_factors: list[str]
    external_likelihood_signal: Literal["INCREASING", "STABLE", "DECREASING"]
    confidence_in_assessment: Literal["HIGH", "MEDIUM", "LOW"]
    sources: list[str]
    data_freshness: str
    label: Literal["EXTERNAL_INTELLIGENCE"] = "EXTERNAL_INTELLIGENCE"


class _LLMSearchQueries(BaseModel):
    """LLM generates targeted search queries for a risk."""

    queries: list[str]


class _LLMIntelligenceSynthesis(BaseModel):
    """LLM synthesizes search results into structured intelligence."""

    recent_incidents: list[str]
    regulatory_developments: list[str]
    market_trends: list[str]
    geopolitical_factors: list[str]
    external_likelihood_signal: Literal["INCREASING", "STABLE", "DECREASING"]
    confidence_in_assessment: Literal["HIGH", "MEDIUM", "LOW"]


def gather_external_intelligence(
    evidence: EvidenceContext,
    knowledge: KnowledgeContext,
    llm: LLMWrapper,
) -> ExternalIntelligence:
    """Gather external intelligence for a single risk via web search.

    Flow:
    1. LLM generates 3 targeted search queries for this risk + sector
    2. Execute searches via DuckDuckGo (free, no API key needed)
    3. LLM synthesizes search results into structured intelligence
    4. Return labeled EXTERNAL_INTELLIGENCE with sources

    Args:
        evidence: Assembled evidence context for this risk.
        knowledge: Client questionnaire context.
        llm: LLM wrapper instance.

    Returns:
        ExternalIntelligence with search-grounded data and sources.
    """
    sector = knowledge.company_profile.sector
    sub_sector = knowledge.company_profile.sub_sector

    # Step 1: Generate CLIENT-SPECIFIC search queries grounded in questionnaire
    queries = _generate_search_queries(
        evidence, sector, sub_sector, llm,
        knowledge_context=knowledge.risk_relevant_context,
    )
    logger.info(
        "  [EI] %s: generated %d search queries", evidence.risk_id, len(queries)
    )

    # Step 2: Execute searches
    all_results: list[dict] = []
    all_sources: list[str] = []
    for query in queries[:3]:  # Max 3 queries per risk
        results = _execute_search(query)
        all_results.extend(results)
        for r in results:
            src = r.get("href", r.get("link", ""))
            if src and src not in all_sources:
                all_sources.append(src)
        time.sleep(_SEARCH_DELAY)

    logger.info(
        "  [EI] %s: found %d search results from %d sources",
        evidence.risk_id, len(all_results), len(all_sources),
    )

    # Step 3: Synthesize results
    if all_results:
        synthesis = _synthesize_results(
            evidence, sector, all_results, llm
        )
    else:
        # No search results — return empty intelligence
        logger.warning("  [EI] %s: no search results found", evidence.risk_id)
        synthesis = _LLMIntelligenceSynthesis(
            recent_incidents=["No recent incidents found via search"],
            regulatory_developments=["No regulatory developments found via search"],
            market_trends=["No market trends found via search"],
            geopolitical_factors=[],
            external_likelihood_signal="STABLE",
            confidence_in_assessment="LOW",
        )

    return ExternalIntelligence(
        risk_id=evidence.risk_id,
        search_queries_used=queries[:3],
        recent_incidents=synthesis.recent_incidents,
        regulatory_developments=synthesis.regulatory_developments,
        market_trends=synthesis.market_trends,
        geopolitical_factors=synthesis.geopolitical_factors,
        external_likelihood_signal=synthesis.external_likelihood_signal,
        confidence_in_assessment=synthesis.confidence_in_assessment,
        sources=all_sources[:10],  # Cap at 10 sources
        data_freshness="2026-04",
    )


def _generate_search_queries(
    evidence: EvidenceContext,
    sector: str,
    sub_sector: str,
    llm: LLMWrapper,
    knowledge_context: dict | None = None,
) -> list[str]:
    """Have the LLM generate CLIENT-SPECIFIC search queries grounded in questionnaire data.

    Queries must reference the client's actual geographies, suppliers, materials,
    and regulatory jurisdictions — not generic industry searches.
    """
    # Build client context from knowledge for grounded queries
    client_context = ""
    if knowledge_context:
        client_context = "\n".join(f"  - {k}: {v}" for k, v in knowledge_context.items())

    prompt = f"""Generate exactly 3 web search queries to research the CURRENT state of this risk
as it specifically affects THIS client. The year is 2026.

CLIENT SECTOR: {sector} ({sub_sector})
RISK: {evidence.client_description}
KEY EVIDENCE FROM CLIENT: {'; '.join(evidence.verbatim_quotes[:3])}

CLIENT-SPECIFIC CONTEXT (from questionnaire — use this to make queries specific):
{client_context}

RULES FOR QUERY GENERATION:
1. Queries MUST reference the client's SPECIFIC geographies, materials, or regulations — NOT company names or supplier names (they are fictional/confidential and won't return real results).
2. Queries MUST target 2025-2026 data.
3. Focus on the RISK TYPE + GEOGRAPHY + MATERIAL/SECTOR combination.
4. Use real-world terms that will return actual news results.

EXAMPLES OF GOOD vs BAD QUERIES:
- BAD: "CellTech Energy supply chain" (fictional company name — zero results)
- GOOD: "lithium battery supply chain disruption Europe 2025 2026"
- BAD: "VelocityAuto cyber risk" (confidential company name)
- GOOD: "automotive OEM connected vehicle cybersecurity incidents 2025"
- BAD: "automotive supply chain disruption 2023" (old date)
- GOOD: "automotive semiconductor shortage Europe 2025 2026"
- GOOD: "Euro 7 emissions regulation automotive compliance 2026"
- GOOD: "automotive battery raw material cobalt lithium shortage 2025"

Generate 3 short, specific queries (8-12 words each) using REAL-WORLD terms only."""

    try:
        result = llm.call(
            prompt=prompt,
            response_model=_LLMSearchQueries,
            temperature=0.0,
            step_name=f"search_queries_{evidence.risk_id}",
        )
        return result.queries[:3]
    except Exception as exc:
        logger.warning("  [EI] Query generation failed: %s. Using fallback.", exc)
        # Fallback: construct client-specific queries from knowledge context
        desc = evidence.client_description
        return [
            f"{sector} {desc} 2025 2026",
            f"{desc} {sector} latest news",
            f"{desc} risk trends 2026",
        ]


def _execute_search(query: str, max_results: int = 5) -> list[dict]:
    """Execute a web search via DuckDuckGo, restricted to last 12 months."""
    try:
        from ddgs import DDGS

        with DDGS() as ddgs:
            results = list(ddgs.text(
                query,
                max_results=max_results,
                timelimit="y",  # Last year only — no stale 2023 results
            ))
        return results
    except Exception as exc:
        logger.warning("  [EI] Search failed for '%s': %s", query[:50], exc)
        return []


def _synthesize_results(
    evidence: EvidenceContext,
    sector: str,
    search_results: list[dict],
    llm: LLMWrapper,
) -> _LLMIntelligenceSynthesis:
    """Have the LLM synthesize search results into structured intelligence."""

    # Format search results into readable text
    results_text = _format_search_results(search_results)

    prompt = f"""You are an External Intelligence Agent for enterprise risk management.

TASK: Synthesize the following web search results into structured intelligence
about this risk AS IT AFFECTS THIS SPECIFIC CLIENT in the {sector} industry.

RISK BEING RESEARCHED: {evidence.client_description}

CLIENT CONTEXT: This client operates in {sector}, with specific exposure to the
geographies, suppliers, and regulatory jurisdictions mentioned in the search queries.

SEARCH RESULTS:
{results_text}

RULES:
- ONLY include findings that are RELEVANT to this client's specific situation.
- Discard generic industry news that doesn't relate to the client's geographies,
  suppliers, materials, or regulatory environment.
- If a finding is from 2023 or earlier, only include it if it represents an ongoing trend.
- Prefer 2025-2026 data over older data.

Extract and categorize:

1. RECENT INCIDENTS: Real events at peer companies in the client's markets/regions.
   Only include events that actually happened. If none found, say so.

2. REGULATORY DEVELOPMENTS: New laws, standards, enforcement in the client's jurisdictions.

3. MARKET TRENDS: Trends affecting this risk in the client's specific markets.

4. GEOPOLITICAL FACTORS: Only if relevant to the client's operating geographies.

5. EXTERNAL LIKELIHOOD SIGNAL:
   - INCREASING: Evidence suggests this risk is becoming MORE likely for this client
   - STABLE: No clear trend
   - DECREASING: Evidence suggests this risk is becoming LESS likely

6. CONFIDENCE: HIGH if multiple corroborating recent sources, MEDIUM if limited, LOW if sparse."""

    try:
        return llm.call(
            prompt=prompt,
            response_model=_LLMIntelligenceSynthesis,
            temperature=0.0,
            step_name=f"intelligence_synthesis_{evidence.risk_id}",
        )
    except Exception as exc:
        logger.warning("  [EI] Synthesis failed: %s. Returning empty.", exc)
        return _LLMIntelligenceSynthesis(
            recent_incidents=["Synthesis failed — no data"],
            regulatory_developments=[],
            market_trends=[],
            geopolitical_factors=[],
            external_likelihood_signal="STABLE",
            confidence_in_assessment="LOW",
        )


def _format_search_results(results: list[dict]) -> str:
    """Format search results into readable text for the LLM."""
    lines: list[str] = []
    for i, r in enumerate(results[:15], 1):  # Cap at 15 results
        title = r.get("title", "No title")
        body = r.get("body", r.get("snippet", "No description"))
        href = r.get("href", r.get("link", ""))
        lines.append(f"[{i}] {title}")
        lines.append(f"    {body[:300]}")
        if href:
            lines.append(f"    Source: {href}")
        lines.append("")
    return "\n".join(lines) if lines else "(no search results)"
