# Phase 2: Intelligent Risk Scoring Agent System

## Overview

Phase 2 extends the RiskMapper pipeline with an intelligent multi-agent system that takes the identified risk universe (output of Phase 1) and produces **inherent risk scores** on a 5×5 impact/likelihood matrix. The system mimics how a senior risk consultant would think — gathering evidence, enriching context, and making grounded scoring decisions.

The agent processes each risk through a structured reasoning chain:
1. Retrieve evidence from the interview transcript
2. Pull relevant context from the client questionnaire (grounded, no hallucination)
3. Enrich with external market intelligence (clearly labeled as external)
4. Score impact and likelihood using the client's own assessment tables
5. Calculate inherent risk score with full justification

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │       RISK SCORING ORCHESTRATOR      │
                    │  (iterates over risk_universe.json)  │
                    │  (manages memory across all risks)   │
                    └──────────────┬──────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                     ▼
     ┌─────────────────┐  ┌────────────────┐  ┌──────────────────┐
     │   EVIDENCE       │  │  KNOWLEDGE     │  │  MARKET RESEARCH │
     │   RETRIEVER      │  │  SUMMARIZER    │  │  AGENT           │
     │   AGENT          │  │  AGENT         │  │                  │
     │                  │  │                │  │  - Web search     │
     │  - Transcript    │  │  - Questionnaire│  │  - Industry data │
     │    context       │  │    extraction  │  │  - Regulatory    │
     │  - Verbatim      │  │  - Company     │  │    landscape     │
     │    evidence      │  │    profile     │  │  - Market trends │
     │  - Cascade       │  │  - 100% grounded│  │                  │
     │    context       │  │    in client   │  │  OUTPUT LABELED:  │
     │                  │  │    data ONLY   │  │  "external intel" │
     └────────┬────────┘  └───────┬────────┘  └────────┬─────────┘
              │                   │                     │
              └───────────────────┼─────────────────────┘
                                  ▼
                    ┌─────────────────────────────┐
                    │       SCORING AGENT          │
                    │                              │
                    │  Inputs:                     │
                    │  - Evidence context           │
                    │  - Client profile summary     │
                    │  - Market intelligence         │
                    │  - Impact Assessment Table     │
                    │  - Likelihood Assessment Table │
                    │  - Memory (prior risk scores)  │
                    │                              │
                    │  Outputs:                     │
                    │  - Impact score (1-5)          │
                    │  - Impact justification        │
                    │  - Impact dimension matched    │
                    │  - Likelihood score (1-5)      │
                    │  - Likelihood justification    │
                    │  - Inherent risk score (I×L)   │
                    │  - Confidence level             │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │    CONSISTENCY CHECKER       │
                    │                              │
                    │  Post-scoring validation:     │
                    │  - Cross-risk consistency     │
                    │  - Cascade coherence          │
                    │  - Flag anomalies             │
                    └──────────────┬──────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │    MEMORY / STATE STORE      │
                    │                              │
                    │  - All scored risks so far    │
                    │  - Client profile (persistent)│
                    │  - Scoring rationale history   │
                    │  - Cascade dependency graph    │
                    └─────────────────────────────┘
```

---

## Agent Specifications

### 1. Evidence Retriever Agent

**Purpose:** Extract and organize all available evidence for a given risk from client-provided data.

**Inputs:**
- `risk_id` and `client_description` from risk_universe.json
- `verbatim_evidence` array (already extracted in Phase 1)
- `cascade_context` (if CASCADE_SIGNAL flagged)
- `question_source` (which interview questions mentioned this risk)
- Full interview transcript (for surrounding context)

**Process:**
1. Take the verbatim_evidence sentences already extracted
2. For each evidence sentence, retrieve surrounding context from the transcript (±2 sentences) to capture nuance
3. If CASCADE_SIGNAL is flagged, pull the full cascade chain context
4. Pull any cross-references from other risks that mention related themes

**Output:**
```json
{
  "risk_id": "RISK_026",
  "evidence_summary": "...",
  "verbatim_quotes": ["..."],
  "surrounding_context": ["..."],
  "cascade_evidence": "...",
  "cross_risk_references": ["RISK_003", "RISK_049"],
  "evidence_strength": "STRONG | MODERATE | WEAK"
}
```

**Grounding Rule:** 100% grounded in transcript. No external data. No inference beyond what the client said.

---

### 2. Knowledge Summarizer Agent

**Purpose:** Extract relevant client profile information from the questionnaire to contextualize the risk.

**Inputs:**
- The risk being scored (description, type, flags)
- Client questionnaire data (pre-call structured questionnaire)
- Any previously extracted client profile data (from memory)

**Process:**
1. Parse the risk description to identify what contextual information is needed
   - For "Regulatory risk due to spectrum policy" → pull: operating geographies, regulatory bodies, spectrum holdings, license obligations
   - For "Energy Cost Risk" → pull: energy consumption data, sustainability commitments, cost structure breakdown
2. Query the questionnaire data for ONLY relevant fields
3. Build a structured client context summary for this specific risk

**Output:**
```json
{
  "risk_id": "RISK_026",
  "company_profile": {
    "sector": "Telecommunication",
    "operating_geographies": ["..."],
    "company_size": "...",
    "revenue_range": "..."
  },
  "risk_relevant_context": {
    "regulatory_bodies": ["..."],
    "spectrum_holdings": "...",
    "upcoming_auctions": "...",
    "capital_commitments": "..."
  },
  "data_source": "client_questionnaire",
  "completeness": "FULL | PARTIAL | MINIMAL"
}
```

**Grounding Rule:** 100% grounded in client-provided questionnaire data. If data is not available in the questionnaire, mark as "NOT_PROVIDED" — never infer or hallucinate.

---

### 3. Market Research Agent

**Purpose:** Provide external market intelligence to inform likelihood assessment.

**Inputs:**
- Risk description and type
- Client sector and operating geographies
- Client profile summary (from Knowledge Summarizer)

**Process:**
1. For the given risk, research current market conditions:
   - Recent incidents in the sector (has this risk materialized for peers?)
   - Regulatory developments (new laws, enforcement actions)
   - Market trends (pricing pressure, technology shifts)
   - Geopolitical factors (if relevant)
2. Assess the external environment's contribution to risk likelihood

**Output:**
```json
{
  "risk_id": "RISK_026",
  "market_intelligence": {
    "recent_incidents": ["..."],
    "regulatory_developments": ["..."],
    "market_trends": ["..."],
    "geopolitical_factors": ["..."]
  },
  "external_likelihood_signal": "INCREASING | STABLE | DECREASING",
  "confidence_in_assessment": "HIGH | MEDIUM | LOW",
  "sources": ["..."],
  "data_freshness": "2026-04",
  "label": "EXTERNAL_INTELLIGENCE"
}
```

**Grounding Rule:** This agent CAN use external knowledge and web search. All outputs MUST be labeled as "EXTERNAL_INTELLIGENCE" and sources cited. The scoring agent must weight this differently from client-stated facts.

---

### 4. Scoring Agent

**Purpose:** Produce the final impact and likelihood scores grounded in the client's assessment tables.

**Inputs:**
- Evidence context (from Evidence Retriever)
- Client profile summary (from Knowledge Summarizer)
- Market intelligence (from Market Research Agent)
- Impact Assessment Table (sector-specific, see below)
- Likelihood Assessment Table (sector-specific, see below)
- Memory: all previously scored risks (for consistency)

**Process:**
1. Determine which Impact Dimension(s) are most relevant for this risk
2. Within that dimension, identify the most applicable Sub-Dimension and Metric
3. Based on evidence + context, estimate where on the 5-level scale the impact falls
4. Quote the specific table criteria that justify the score
5. For likelihood, combine:
   - Client's own assessment (from transcript — "it's getting worse", "we've seen it happen")
   - Historical evidence (from Q5 — past incidents)
   - Market research signal (external likelihood indicator)
   - Frequency/probability indicators from the likelihood table
6. Calculate Inherent Risk Score = Impact × Likelihood
7. Check against memory for consistency with related risks

**Output:**
```json
{
  "risk_id": "RISK_026",
  "impact_assessment": {
    "score": 4,
    "level": "High",
    "dimension": "Regulatory & Compliance Impact",
    "sub_dimension": "Quality Certification",
    "metric": "Loss / Suspension of Certifications",
    "justification": "Client operates across multiple jurisdictions with upcoming spectrum auctions in two key markets. Based on the impact table criteria for 'High' — 'Suspension risk' — the potential loss or suspension of spectrum licenses due to policy changes represents a High impact.",
    "table_criteria_matched": "Suspension risk"
  },
  "likelihood_assessment": {
    "score": 3,
    "level": "Possible",
    "justification": "Client stated spectrum auctions are upcoming in two key markets and regulatory framing will 'significantly affect capital planning.' Market research confirms active spectrum policy debates in EU. Historical precedent: no direct incident but client flags it as event-driven. Assessed as 'Possible' based on likelihood table criteria.",
    "evidence_basis": "CLIENT_STATED + EXTERNAL_INTELLIGENCE",
    "table_criteria_matched": "Event could occur within assessment period"
  },
  "inherent_risk_score": 12,
  "risk_rating": "High",
  "confidence": "MEDIUM",
  "consistency_notes": "Aligned with RISK_003 (Regulatory Risk) scored at Impact 4 / Likelihood 4. This is a sub-component of broader regulatory risk, likelihood slightly lower as spectrum-specific.",
  "flags_for_review": []
}
```

**Grounding Rule:** Every score MUST reference a specific row/criteria from the impact or likelihood table. If the agent cannot map to a specific criterion, it MUST flag for human review rather than guess.

---

### 5. Consistency Checker (Post-Scoring Pass)

**Purpose:** Validate scoring consistency across the full risk universe after all risks are scored.

**Checks:**
1. **Related risk coherence:** If "Cyber Risk" (RISK_002) has Impact=5, then "External cyber attack risk" (RISK_036) should not have Impact=2
2. **Cascade coherence:** If an upstream risk has Likelihood=5, downstream cascade risks should have Likelihood ≥ 3
3. **Dimension consistency:** Risks in the same impact dimension should have logically ordered scores
4. **Outlier detection:** Flag any risk whose score deviates significantly from similar risks
5. **Score distribution:** Flag if all risks cluster at the same score (suggests lazy scoring)

**Output:** List of flagged inconsistencies with recommended adjustments for human review.

---

### 6. Memory / State Store

**Purpose:** Maintain context across all risk scoring iterations.

**Stores:**
- Client profile (extracted once, reused for all risks)
- All scored risks with their justifications
- Cascade dependency graph (which risks trigger which)
- Scoring rationale history (for consistency checking)
- Market research cache (avoid redundant lookups for related risks)

**Implementation:** In-memory dict/JSON during pipeline run, persisted to disk between runs.

---

## Data Inputs Required

### 1. Risk Universe (Phase 1 Output) ✅ Available
- `output_v2/risk_universe.json` — 58 risks with evidence, registry matches, flags

### 2. Interview Transcript ✅ Available
- `TeleNova_ERM_Call_Transcript.txt`

### 3. Client Questionnaire ❌ Needed
- The pre-call structured questionnaire filled by the client
- Contains: company profile, operating details, regulatory context, financial structure
- Format: any parseable format (text, PDF, Excel, JSON)

### 4. Impact Assessment Table ⏳ Structure Known, Content Below
- 5-level scale: No Impact → Low → Moderate → High → Severe/Catastrophic
- Multi-dimensional with sector-specific metrics
- See Automotive-tailored version below

### 5. Likelihood Assessment Table ❌ Needed
- 5-level scale (to be provided by user)
- Criteria for each level

---

## Impact Assessment Table — Automotive Sector

Based on the Impact Assessment GuidBook structure, tailored for Automotive industry.

### Scoring Levels

| Level | Score | Label                |
|-------|-------|----------------------|
| 1     | 1     | No Impact            |
| 2     | 2     | Low                  |
| 3     | 3     | Moderate             |
| 4     | 4     | High                 |
| 5     | 5     | Severe / Catastrophic|

---

### Dimension 1: Financial & Growth Impact

| Sub-Dimension   | Metric                                          | Unit                | No Impact (1) | Low (2)    | Moderate (3) | High (4)   | Severe/Catastrophic (5) |
|-----------------|------------------------------------------------|---------------------|---------------|------------|--------------|------------|--------------------------|
| Revenue         | Revenue Decline                                 | % of total revenue  | <1%           | 1–3%       | 3–6%         | 6–12%      | >12%                     |
| Margins         | EBITDA / Operating Margin Reduction             | % points            | <1%           | 1–3%       | 3–6%         | 6–10%      | >10%                     |
| Cost Structure  | Raw Material & Energy Cost Inflation            | % cost increase     | <2%           | 2–5%       | 5–10%        | 10–20%     | >20%                     |
| Liquidity       | Cash Flow Stress / Liquidity Headroom           | Months              | >18           | 12–18      | 6–12         | 3–6        | <3                       |
| Capital         | Capex Overrun / Project Delays                  | % over budget       | <5%           | 5–10%      | 10–20%       | 20–40%     | >40%                     |
| Growth          | Demand Volatility (Order Book Decline)          | % decline           | <2%           | 2–5%       | 5–10%        | 10–20%     | >20%                     |
|                 | Loss of Key Customers                           | % of revenue        | <5%           | 5–10%      | 10–20%       | 20–30%     | >30%                     |
| Pricing         | Pricing Pressure / Inability to Pass Costs      | % margin erosion    | <1%           | 1–3%       | 3–5%         | 5–8%       | >8%                      |

---

### Dimension 2: Operating Impact

| Sub-Dimension          | Metric                                    | Unit                  | No Impact (1) | Low (2)    | Moderate (3) | High (4)    | Severe/Catastrophic (5) |
|------------------------|-------------------------------------------|-----------------------|---------------|------------|--------------|-------------|--------------------------|
| Production Continuity  | Production Downtime                       | Hours                 | <1            | 1–4        | 4–12         | 12–48       | >48                      |
| Equipment Reliability  | Critical Equipment Failure                | Events / year         | 0             | 1          | 2–3          | 4–6         | >6                       |
| Capacity Utilisation   | Capacity Utilisation Drop                 | % points              | <3%           | 3–5%       | 5–10%        | 10–20%      | >20%                     |
| Quality                | Defect / Rework Rate Increase             | % increase            | <2%           | 2–5%       | 5–10%        | 10–20%      | >20%                     |
| Supply Chain           | Critical Supplier Disruption              | Days                  | <1            | 1–3        | 3–7          | 7–14        | >14                      |
| Inventory              | Inventory Shortage / Excess               | Days of cover         | Within plan   | ±5 days    | ±10 days     | ±20 days    | >±20 days                |
| Maintenance            | Unplanned Maintenance Downtime            | % of operating time   | <1%           | 1–3%       | 3–5%         | 5–10%       | >10%                     |
| Logistics              | Inbound / Outbound Logistics Disruption   | Days                  | <1            | 1–2        | 2–5          | 5–10        | >10                      |

---

### Dimension 3: Customer & Market Impact

| Sub-Dimension          | Metric                                          | Unit                | No Impact (1) | Low (2)    | Moderate (3) | High (4)    | Severe/Catastrophic (5)        |
|------------------------|------------------------------------------------|---------------------|---------------|------------|--------------|-------------|--------------------------------|
| Customer Demand        | Order Cancellation / Reduction                  | % of order book     | <2%           | 2–5%       | 5–10%        | 10–20%      | >20%                           |
| Customer Retention     | Loss of Key Customers                           | % of revenue        | <5%           | 5–10%      | 10–20%       | 20–30%      | >30%                           |
| Quality Perception     | Customer Complaints Due to Quality Issues       | % increase          | <5%           | 5–10%      | 10–25%       | 25–50%      | >50%                           |
| Delivery Performance   | On-Time Delivery Failure                        | % of shipments      | <2%           | 2–5%       | 5–10%        | 10–20%      | >20%                           |
| Contractual Risk       | Penalty / Liquidated Damages Triggered          | % of contracts      | 0             | <5%        | 5–15%        | 15–30%      | >30%                           |
| Market Position        | Market Share Loss                               | % points            | <1%           | 1–2%       | 2–5%         | 5–10%       | >10%                           |
| Brand Trust            | Customer Confidence Decline                     | % survey/NPS drop   | <3%           | 3–5%       | 5–10%        | 10–20%      | >20%                           |
| Pricing & Competitive  | Loss of Competitiveness vs Peers                | Qualitative         | No impact     | Minor erosion | Noticeable disadvantage | Major disadvantage | Loss of preferred supplier status |

---

### Dimension 4: Regulatory & Compliance Impact

| Sub-Dimension            | Metric                                          | Unit                  | No Impact (1)    | Low (2)           | Moderate (3)            | High (4)                        | Severe/Catastrophic (5)              |
|--------------------------|------------------------------------------------|-----------------------|------------------|-------------------|-------------------------|---------------------------------|--------------------------------------|
| Environmental Compliance | Environmental Regulation Breaches               | Count per year        | 0                | 1 minor           | 2–3                     | Repeated breaches               | Plant closure / license suspension   |
|                          | Emissions / Waste Permit Violations             | Severity              | Fully compliant  | Minor deviation   | Notice of violation     | Fines / enforced remediation    | Operating ban / shutdown             |
| Product Safety           | Product Safety Non-Compliance                   | % of products         | <1%              | Minor deviation   | 3–5%                    | 5–10%                           | >10% / recall                        |
| Quality Certification    | Loss / Suspension of Certifications (ISO, IATF) | Status                | No issue         | Observation only  | Conditional compliance  | Suspension risk                 | Certification withdrawn              |
| Trade & Customs          | Trade / Customs Violations                      | Count                 | 0                | 1                 | 2–3                     | Repeated issues                 | Certification withdrawn              |
| Labour Compliance        | Labour Law Violations                           | Count                 | 0                | 1 minor           | 2–3                     | Repeated violations             | Plant restrictions / sanctions       |
| Health & Safety          | Regulatory H&S Citations                        | Count                 | 0                | 1                 | 2–3                     | Significant findings            | Plant shutdown / penalties           |
| Governance               | Regulatory Investigations / Inspections         | Severity              | Routine audit    | Minor findings    | Formal investigation    | Enforcement action              | Stop-work order                      |
| Sanctions                | Regulatory Fines / Penalties                    | % of annual revenue   | <0.1%            | 0.1–0.5%          | 0.5–1%                  | 1–3%                            | >3%                                  |

---

### Dimension 5: Technology & Information Impact

| Sub-Dimension              | Metric                                                | Unit                  | No Impact (1) | Low (2)    | Moderate (3)    | High (4)       | Severe/Catastrophic (5)        |
|----------------------------|------------------------------------------------------|-----------------------|---------------|------------|-----------------|----------------|--------------------------------|
| OT / Production Systems    | Production Control System (PLC / SCADA) Failure       | Hours                 | <0.5          | 0.5–2      | 2–8             | 8–24           | >24                            |
|                            | Manufacturing Execution System (MES) Failure          | Hours                 | <1            | 1–4        | 4–12            | 8–24           | >24                            |
| Industrial Automation      | Automation / Robotics Failure                         | Hours                 | <1            | 1–4        | 4–12            | 8–24           | >24                            |
| Cyber Security             | Industrial Cyber Incident Severity                    | % of lines affected   | <5%           | 5–10%      | 10–25%          | 12–48          | >48                            |
| Data Security              | Intellectual Property / Design Data Breach            | Scope                 | No incident   | Single asset | Multiple assets | 25–50%        | >50%                           |
| Enterprise IT              | ERP / Core IT System Downtime                         | Records affected      | 0             | <100       | 100–1k          | 1k–10k         | Multi-plant / safety impact    |
| Third-Party Technology     | Critical Technology Vendor Failure                    | Hours                 | <1            | 1–4        | 4–12            | 1k–10k         | >10k / sensitive IP            |
| Resilience                 | Disaster Recovery / RTO Breach                        | % above RTO           | No breach     | <2         | 2–6             | 12–24          | >24                            |

---

### Dimension 6: People, Health & Safety Impact

| Sub-Dimension          | Metric                                          | Unit                    | No Impact (1) | Low (2)       | Moderate (3) | High (4)              | Severe/Catastrophic (5)  |
|------------------------|------------------------------------------------|-------------------------|---------------|---------------|--------------|------------------------|--------------------------|
| Workplace Safety       | Lost Time Injury Frequency Rate (LTIFR)         | Rate                    | 0             | <1            | 1–3          | 3–5                    | >5                       |
|                        | Fatalities                                      | Count per year          | 0             | 1 isolated    | 2–3          | Multiple at one site   | Systemic / repeated      |
| Operations Workforce   | Skilled Labour Unavailability                    | % of workforce          | <2%           | 2–5%          | 5–10%        | 10–20%                 | >20%                     |
|                        | Critical Skill Shortage                         | % roles unfilled        | <1%           | 1–3%          | 3–7%         | 10–20%                 | >20%                     |
| Occupational Health    | Occupational Illness Cases                      | % workforce affected    | <0.5%         | 0.5–1%        | 1–3%         | 2–15%                  | >15%                     |
| Contract Labour        | Contractor Safety Incidents                     | Count                   | 0             | 1             | 2–3          | 3–7%                   | >7%                      |
| Labour Relations       | Industrial Action / Strikes                     | Days                    | 0             | <1            | 1–5          | 5–10                   | >6                       |
| Compliance             | H&S Regulatory Breaches                         | Count                   | 0             | 1 minor       | 2–3          | Repeated               | Stop work order          |

---

### Dimension 7: Reputation & Ethics Impact

| Sub-Dimension            | Metric                                          | Unit                | No Impact (1)  | Low (2)          | Moderate (3)          | High (4)                    | Severe/Catastrophic (5)          |
|--------------------------|------------------------------------------------|---------------------|----------------|------------------|-----------------------|-----------------------------|----------------------------------|
| Brand Reputation         | Negative Media Coverage Intensity               | Coverage scope      | Local / negligible | Regional      | National sustained    | International               | Global prolonged                 |
|                          | Media Escalation Velocity                       | Time to peak        | >7 days        | 3–7 days         | 1–3 days              | <24 hours                   | <12 hours                        |
| Product Integrity        | Reputation Impact from Product Recalls          | Count               | 0              | 0.1–0.5%         | 0.5–2%                | 2–5%                        | >5%                              |
| Customer Trust           | Loss of Preferred Supplier Status               | Count               | 0              | Isolated minor   | 2–3                   | Multiple key customers      | Widespread customer exit         |
| Ethical Conduct          | Ethical Misconduct / Fraud Incidents            | Severity            | No incident    | Isolated minor   | Investigated breach   | Regulatory action           | Criminal proceedings             |
| ESG Perception           | ESG / Sustainability Rating Downgrade           | Rating levels       | No change      | Watch / outlook  | 1-level downgrade     | 2-level downgrade           | Exclusion / severe downgrade     |
| Stakeholder Relations    | Community / Regulator Trust Erosion             | Qualitative         | Supportive     | Heightened scrutiny | Adversarial          | License / permit constraints | Loss of license to operate       |

---

## Likelihood Assessment Table (Template — Awaiting Client Input)

The likelihood table follows a similar 5-level structure. Placeholder below — to be replaced with client-provided criteria.

| Level | Score | Label           | Frequency Indicator              | Probability Indicator        |
|-------|-------|-----------------|----------------------------------|------------------------------|
| 1     | 1     | Rare            | Less than once in 10 years       | <5% probability in 12 months |
| 2     | 2     | Unlikely        | Once in 5–10 years               | 5–20% probability            |
| 3     | 3     | Possible        | Once in 2–5 years                | 20–50% probability           |
| 4     | 4     | Likely          | Once in 1–2 years                | 50–80% probability           |
| 5     | 5     | Almost Certain  | Multiple times per year          | >80% probability             |

> **NOTE:** This is a generic template. Replace with the client's actual likelihood assessment table once provided.

---

## 5×5 Risk Matrix

```
                        IMPACT
              1     2     3     4     5
         ┌─────┬─────┬─────┬─────┬─────┐
    5    │  5  │ 10  │ 15  │ 20  │ 25  │  Almost Certain
         ├─────┼─────┼─────┼─────┼─────┤
    4    │  4  │  8  │ 12  │ 16  │ 20  │  Likely
L        ├─────┼─────┼─────┼─────┼─────┤
I   3    │  3  │  6  │  9  │ 12  │ 15  │  Possible
K        ├─────┼─────┼─────┼─────┼─────┤
E   2    │  2  │  4  │  6  │  8  │ 10  │  Unlikely
L        ├─────┼─────┼─────┼─────┼─────┤
I   1    │  1  │  2  │  3  │  4  │  5  │  Rare
H        └─────┴─────┴─────┴─────┴─────┘
O
O
D

Risk Rating Bands:
  1–4   = Low Risk (Green)
  5–9   = Medium Risk (Yellow)
  10–15 = High Risk (Orange)
  16–25 = Critical Risk (Red)
```

---

## Output Schema (Per Risk)

```json
{
  "risk_id": "RISK_001",
  "client_description": "5G Monetization Risk",
  "impact_assessment": {
    "score": 4,
    "level": "High",
    "dimension": "Financial & Growth Impact",
    "sub_dimension": "Revenue",
    "metric": "Revenue Decline",
    "justification": "...",
    "table_criteria_matched": "6-12% of total revenue"
  },
  "likelihood_assessment": {
    "score": 4,
    "level": "Likely",
    "justification": "...",
    "evidence_basis": "CLIENT_STATED | EXTERNAL_INTELLIGENCE | BOTH",
    "table_criteria_matched": "Once in 1-2 years"
  },
  "inherent_risk_score": 16,
  "risk_rating": "Critical",
  "scoring_confidence": "HIGH | MEDIUM | LOW",
  "evidence_summary": "...",
  "client_context_used": "...",
  "market_intelligence_used": "...",
  "consistency_notes": "...",
  "flags_for_review": [],
  "cascade_scoring_impact": {
    "upstream_risks": [],
    "downstream_risks": [],
    "cascade_likelihood_adjustment": null
  }
}
```

---

## Identified Loopholes & Mitigations

### Loophole 1: Questionnaire Parsing Quality
**Risk:** If the questionnaire is unstructured/messy, the Knowledge Summarizer may miss critical context or extract wrong data.
**Mitigation:** Index the questionnaire into a ChromaDB collection (like we did with the risk registry). Use semantic retrieval per-risk rather than dumping the whole questionnaire into the LLM context. Add a "completeness" score to flag when insufficient data was found.

### Loophole 2: Market Research Agent Hallucination
**Risk:** The external research agent could fabricate market data or cite non-existent sources.
**Mitigation:** All market research output is labeled "EXTERNAL_INTELLIGENCE." The scoring agent weights client-stated evidence higher than external intelligence. Sources must be cited. If no credible source is found, the agent returns "INSUFFICIENT_DATA" rather than guessing.

### Loophole 3: LLM Score Anchoring
**Risk:** The LLM may anchor on the first few risks it scores and apply similar scores to all subsequent risks regardless of evidence.
**Mitigation:** The Consistency Checker runs as a post-scoring pass. It checks score distribution, flags clustering, and identifies outliers. Each risk is scored independently with its own context window. Memory provides reference but not anchoring — the prompt explicitly instructs "score this risk independently based on its own evidence."

### Loophole 4: Impact Dimension Selection Bias
**Risk:** The LLM may consistently pick the same impact dimension (e.g., Financial) even when another dimension is more appropriate.
**Mitigation:** The scoring prompt requires the agent to consider ALL 7 impact dimensions and select the PRIMARY one with justification. If multiple dimensions are relevant, the agent scores the highest-impact dimension. The prompt includes: "If this risk primarily affects operations but also has financial consequences, score the operational impact as primary."

### Loophole 5: Cascade Scoring Circularity
**Risk:** Risk A's likelihood depends on Risk B's score, but Risk B's likelihood depends on Risk A.
**Mitigation:** Two-pass scoring. First pass: score all risks independently (no cascade adjustments). Second pass: adjust likelihood scores based on cascade dependencies using the first-pass scores. No circular adjustments — use topological ordering of the cascade graph.

### Loophole 6: Cross-Risk Consistency
**Risk:** "Cyber Risk" gets Impact=5 but "External cyber attack risk" gets Impact=2 — logically inconsistent.
**Mitigation:** The Consistency Checker identifies risk pairs with high semantic similarity (from Phase 1 registry matching) and flags score divergence >2 levels. Human review required for flagged pairs.

### Loophole 7: Thin Evidence = Low Confidence
**Risk:** Some risks have only 1 verbatim evidence sentence. The agent may still assign a confident score.
**Mitigation:** Evidence Retriever outputs an "evidence_strength" rating (STRONG/MODERATE/WEAK). If WEAK, the scoring agent MUST set confidence to LOW and flag for human review. The scoring prompt includes: "If evidence is limited, prefer conservative (middle) scores and flag for review."

### Loophole 8: Table Criteria Ambiguity
**Risk:** Some impact table metrics are quantitative (% of revenue) but the transcript provides qualitative descriptions ("significant hit"). The LLM may struggle to map qualitative to quantitative.
**Mitigation:** The scoring prompt includes explicit guidance: "When the client uses qualitative language, map it to the table as follows: 'minor/small' → Low, 'significant/material' → Moderate-High, 'severe/catastrophic/existential' → High-Severe. Always state your mapping rationale."

---

## Implementation Phases

### Phase 2a: Core Scoring Pipeline
1. Define Pydantic schemas for scoring output
2. Build Evidence Retriever (transcript context extraction)
3. Build Scoring Agent (impact + likelihood with table grounding)
4. Build Orchestrator (iterate over risk universe)
5. Output: scored_risk_universe.json

### Phase 2b: Knowledge Enrichment
6. Build Knowledge Summarizer (questionnaire parsing + ChromaDB indexing)
7. Integrate questionnaire context into scoring pipeline
8. Build Memory/State store

### Phase 2c: External Intelligence
9. Build Market Research Agent (web search + sector intelligence)
10. Integrate external intelligence into scoring pipeline
11. Add source citation and labeling

### Phase 2d: Validation & Consistency
12. Build Consistency Checker (post-scoring validation)
13. Build Cascade Scoring (two-pass with dependency graph)
14. Human review queue for flagged scores

---

## Files & Modules (Proposed Structure)

```
riskmapper/
├── scoring/
│   ├── __init__.py
│   ├── schemas.py                  # Scoring output schemas
│   ├── evidence_retriever.py       # Evidence context extraction
│   ├── knowledge_summarizer.py     # Questionnaire intelligence
│   ├── market_research_agent.py    # External market intelligence
│   ├── scoring_agent.py            # Impact + likelihood scoring
│   ├── consistency_checker.py      # Post-scoring validation
│   ├── cascade_scorer.py           # Two-pass cascade adjustment
│   ├── memory_store.py             # Cross-risk state management
│   └── scoring_pipeline.py         # Orchestrator
├── data/
│   ├── impact_tables/
│   │   ├── automotive.json         # Automotive impact assessment table
│   │   ├── telecom.json            # Telecom impact assessment table
│   │   └── ...
│   └── likelihood_tables/
│       ├── default.json            # Default likelihood table
│       └── ...
```
