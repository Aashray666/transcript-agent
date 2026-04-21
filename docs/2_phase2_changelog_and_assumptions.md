# Phase 2: Scoring Pipeline — Changelog & Assumptions

## Current State

MVP scoring pipeline for VelocityAuto Group (fictional automotive OEM). Produces inherent risk scores (Impact × Likelihood on a 5×5 matrix) with full audit trail, questionnaire grounding, and external market intelligence.

---

## Changelog (Iterative Fixes)

### v1 — Initial Build
- Built 10-module scoring pipeline under `riskmapper/scoring/`
- 3 LLM calls per risk: Knowledge Summarizer → Likelihood Intelligence → Scoring Agent
- Evidence assembled from Phase 1 output (no LLM call)
- Compact memory store across risks (~50 tokens per risk)
- Consistency checker + cascade scorer (likelihood-only, second pass)

**Problems found:**
- Every risk scored Impact=4, Likelihood=4, Score=16 (no differentiation)
- Every impact dimension was "Financial & Growth / Revenue Decline"
- Questionnaire data was sent to LLM but not cited in justifications
- Groq free tier rate limits caused 30% failure rate

### v2 — Dimension Selection Fix
- Added anti-bias prompt with explicit dimension selection rules
- Added examples: supply chain → Operating Impact, cyber → Technology, etc.
- Forced LLM to evaluate 3 dimensions before selecting one
- Added instruction to cite 2+ questionnaire data points in justification

**Result:** Dimensions now correct (Operating, Technology, Regulatory, etc.) but scores still clustered at 4.

### v3 — Likelihood Computation in Code
- Refactored: LLM no longer picks likelihood scores 1-5 directly
- LLM answers factual yes/no questions about evidence
- Python maps answers to scores deterministically via lookup tables
- Weighted composite computed in code: `Round(F1×0.25 + F2×0.25 + F3×0.20 + F4×0.15 + F5×0.15)`

**Mapping rules (code, not LLM):**
- `has_occurred_at_client=false` → F1 capped at 2
- `controls_tested=true, confidence=high` → F2=1
- `controls_tested=false, confidence=low` → F2=4
- `risk_velocity=slow_build` → F3=2
- `risk_velocity=imminent` → F3=5

**Result:** Factor scores now vary (e.g., F1=2, F2=4, F3=4, F4=3, F5=5 for EV transition).

### v4 — External Intelligence Layer
- Built `external_intelligence.py` — real web search via DuckDuckGo
- LLM generates 3 client-grounded search queries per risk
- Queries reference client's geographies, materials, regulatory jurisdictions
- Search results synthesized by LLM into structured intelligence
- Output labeled EXTERNAL_INTELLIGENCE with cited source URLs
- Feeds into Factor 3 (External Environment) and Factor 4 (Sector Base Rate)

### v5 — Validation Error Fix
- Root cause: LLM echoed JSON schema metadata instead of actual data
- Fix: replaced raw JSON schema dump with concrete example objects
- Added recursive example builder for nested Pydantic models
- Added validation retry (up to 3 attempts with correction prompt)

### v6 — Impact Anchoring Fix
- Added `evidence_quantity` and `quantity_source` fields to ImpactAssessment
- Prompt forces quantity-first scoring: extract number → look up table → score
- Code validates score against evidence quantity post-LLM
- Auto-corrects if LLM underscores (e.g., "42 days" scored as 4 → corrected to 5)
- Lookup tables in code for days, hours, and percentage metrics

### v7 — Search Quality Fixes
- Added `timelimit="y"` to DuckDuckGo — last 12 months only, no stale 2023 results
- Prompt explicitly says "do NOT use company/supplier names (fictional, zero results)"
- Queries now use real-world terms: materials, geographies, regulations
- `cascade_likelihood_adjustment` forced to null — only cascade scorer sets this
- Likelihood clamped to ±1 of code-computed composite — LLM cannot override freely

### v8 — Switched to NVIDIA NIM
- Moved from Groq (12K TPM free tier, constant 429s) to NVIDIA NIM
- Model: `meta/llama-3.3-70b-instruct`
- 5s minimum call interval (vs 30s on Groq)
- ~60-90s per risk (vs 80-120s on Groq with retries)

---

## Assumptions

### MVP / Fictional Client Assumptions

| Assumption | Impact | For Real Client |
|-----------|--------|-----------------|
| VelocityAuto is fictional — no real company data exists | Search queries for company/supplier names return irrelevant results | Use real company names, real supplier names. Search results will be directly relevant. |
| Questionnaire is synthetically filled based on transcript | Quantitative data (EUR 78.4B revenue, 124K employees, etc.) is plausible but not verified | Client fills the questionnaire themselves with verified numbers. All data is ground truth. |
| CellTech Energy, VelocityAuto-Dongfeng, LidarVision are fictional entities | Web search cannot find real incidents for these entities | Real supplier names will return actual incident history, financial health data, news. |
| Transcript is a simulated interview | Risk descriptions are realistic but not from a real engagement | Real transcript from actual CRO interview. Evidence is first-hand. |
| Impact table is automotive-generic | Thresholds (e.g., >14 days = Severe) are industry-standard but not client-calibrated | Client provides their own impact assessment table with their specific thresholds and risk appetite. |
| Likelihood table uses standard ERM weights (25/25/20/15/15) | Weights are based on common ERM practice | Weights can be adjusted per client's risk methodology. Some clients weight controls higher. |

### Scoring Methodology Assumptions

| Assumption | Rationale |
|-----------|-----------|
| Impact is scored on the PRIMARY dimension only | Standard ERM practice — score the most severe direct consequence, not secondary downstream effects |
| Likelihood is a weighted composite of 5 factors | Decomposition reduces LLM hallucination — 5 specific factual questions instead of 1 vague "what's the likelihood?" |
| Factor scores are mapped from factual answers in code, not picked by LLM | Prevents anchoring bias — LLM answers "has this occurred?" (yes/no), code maps to 1-5 |
| External intelligence is labeled separately from client data | Scoring agent must weight client-stated evidence higher than external search results |
| Cascade adjustment affects likelihood only, not impact | Standard ERM: if upstream risk triggers downstream, the downstream impact doesn't change — only the probability of it occurring increases |
| Cascade adjustment is +1 to likelihood (capped at 5) | Conservative — only applied when upstream risk has likelihood ≥ 4 |
| Impact quantity validation auto-corrects LLM scores | If evidence says "42 days" and table says ">14 = 5", the code overrides LLM's score of 4 to 5. This only works for quantitative metrics (days, hours, percentages). Qualitative metrics (e.g., "Suspension risk") cannot be auto-validated. |

### Data Source Hierarchy

| Priority | Source | Used For | Trust Level |
|----------|--------|----------|-------------|
| 1 | Client interview transcript | Verbatim evidence, risk descriptions, control statements | Highest — client's own words |
| 2 | Client questionnaire | Quantitative data, financial metrics, operational details | High — client-provided structured data |
| 3 | Impact/likelihood assessment tables | Score thresholds, dimension definitions | High — agreed methodology |
| 4 | External web search (EXTERNAL_INTELLIGENCE) | Peer incidents, regulatory developments, market trends | Medium — labeled separately, sources cited |
| 5 | LLM sector knowledge | Sector base rates, general industry context | Lowest — used only when no other data available |

### Known Limitations

1. **LLM still anchors on some factors** — even with factual questions, the LLM tends to answer "4" for ambiguous cases. The code-computed composite mitigates this but doesn't eliminate it entirely.

2. **Qualitative impact metrics can't be auto-validated** — metrics like "Suspension risk" or "Noticeable disadvantage" don't have numeric thresholds. The LLM picks the score and code can't verify it.

3. **Web search quality depends on query specificity** — fictional entity names return irrelevant results. With real clients, search quality will improve significantly.

4. **No real market research database** — the external intelligence uses free web search (DuckDuckGo). A production system would use paid APIs (Bloomberg, S&P, Moody's) for higher quality data.

5. **Single LLM model** — currently using `meta/llama-3.3-70b-instruct` via NVIDIA NIM. A production system might use different models for different tasks (e.g., GPT-4 for scoring, smaller model for knowledge extraction).

6. **No human-in-the-loop yet** — the pipeline flags risks for review but doesn't have a UI for human reviewers to accept/reject/adjust scores.

---

## For Real Client Deployment

When moving from MVP to a real client engagement:

1. **Replace fictional questionnaire** with client-completed questionnaire
2. **Replace fictional transcript** with actual CRO interview recording/transcript
3. **Use client's own impact table** — they may have different dimensions, thresholds, or risk appetite
4. **Adjust likelihood weights** if client has a different risk methodology
5. **Real supplier/company names** will dramatically improve external intelligence quality
6. **Add paid data sources** (Bloomberg, regulatory databases) for Factor 4
7. **Add human review UI** for flagged scores before final report
8. **Calibrate with client** — run initial scores, review with CRO, adjust methodology if needed
