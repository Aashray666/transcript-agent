# Phase 2: Scoring Architecture Flowchart

## Per-Risk Scoring Chain

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INPUTS (loaded once at pipeline start)            │
│                                                                     │
│  risk_universe.json ─── auto_transcript.txt ─── questionnaire.json  │
│  impact_table.xlsx  ─── likelihood_table.json                       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: EVIDENCE ASSEMBLER                          [No LLM call]  │
│  ─────────────────────────────                                      │
│  Module: evidence_assembler.py                                      │
│                                                                     │
│  Input:  MappedRisk from Phase 1 + transcript + all risks           │
│  Does:   • Pulls verbatim_evidence from Phase 1 output              │
│          • Extracts ±2 surrounding sentences from transcript         │
│          • Finds cross-risk references (shared questions, cascades)  │
│          • Rates evidence strength: STRONG / MODERATE / WEAK         │
│  Output: EvidenceContext                                            │
│                                                                     │
│  WHY NOT AN LLM AGENT: Evidence is already extracted in Phase 1.    │
│  This is data assembly, not judgment. Saves cost and latency.       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: KNOWLEDGE SUMMARIZER                       [LLM Call #1]   │
│  ────────────────────────────                                       │
│  Module: knowledge_summarizer.py                                    │
│                                                                     │
│  Input:  EvidenceContext + questionnaire (selective sections)        │
│  Does:   • Selects 2-3 most relevant questionnaire sections         │
│          • LLM extracts risk-specific data points                   │
│          • Returns structured dict of client facts                  │
│  Output: KnowledgeContext (completeness: FULL/PARTIAL/MINIMAL)      │
│                                                                     │
│  GROUNDING RULE: 100% from questionnaire. If data not available,    │
│  returns "NOT_PROVIDED" — never infers or hallucinates.             │
│                                                                     │
│  Example output for Supply Chain risk:                              │
│    single_sourced_components: "22%"                                 │
│    top_suppliers: "CellTech Energy — 14% of procurement"            │
│    significant_disruptions: "Semiconductor shortage 2023, EUR 400M" │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: EXTERNAL INTELLIGENCE              [Web Search + LLM #2]   │
│  ──────────────────────────────                                     │
│  Module: external_intelligence.py                                   │
│                                                                     │
│  Input:  EvidenceContext + KnowledgeContext                          │
│  Does:   3a. LLM generates 3 client-grounded search queries         │
│              (uses client geographies, materials, regulations)       │
│              NOT company names (fictional → zero results)            │
│          3b. DuckDuckGo search (timelimit=last 12 months)           │
│          3c. LLM synthesizes results into structured intelligence   │
│  Output: ExternalIntelligence                                       │
│          • recent_incidents (real peer events)                      │
│          • regulatory_developments (actual regulatory changes)      │
│          • market_trends (industry trends)                          │
│          • external_likelihood_signal: INCREASING/STABLE/DECREASING │
│          • sources: [list of URLs]                                  │
│          • label: EXTERNAL_INTELLIGENCE                             │
│                                                                     │
│  GROUNDING RULE: All output labeled EXTERNAL_INTELLIGENCE.          │
│  Scoring agent weights client data higher than external data.       │
│  Sources must be cited. If no results, returns INSUFFICIENT_DATA.   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: LIKELIHOOD INTELLIGENCE                    [LLM Call #3]   │
│  ───────────────────────────────                                    │
│  Module: likelihood_intelligence.py                                 │
│                                                                     │
│  Input:  EvidenceContext + KnowledgeContext + ExternalIntelligence   │
│          + likelihood_table + memory (prior scored risks)           │
│                                                                     │
│  Does:   LLM answers FACTUAL QUESTIONS (not "pick a score 1-5"):   │
│          • has_occurred_at_client? (true/false)                     │
│          • how_recently? (never/over_5y/3-5y/1-2y/currently)       │
│          • controls_exist? controls_tested? confidence? (high/low)  │
│          • external_drivers_present? velocity? (stable→imminent)    │
│          • common_in_sector? (rare→systemic)                        │
│          • client_exposure_vs_peers? (below_avg→extreme)            │
│                                                                     │
│  THEN PYTHON COMPUTES (not LLM):                                    │
│          F1 = map(how_recently) × 0.25                              │
│          F2 = map(controls) × 0.25                                  │
│          F3 = map(velocity) × 0.20                                  │
│          F4 = map(sector_rate) × 0.15                               │
│          F5 = map(exposure) × 0.15                                  │
│          Composite = Round(F1 + F2 + F3 + F4 + F5)                 │
│                                                                     │
│  Output: LikelihoodIntelligence (composite + 5 factor breakdowns)   │
│                                                                     │
│  WHY CODE NOT LLM: LLM anchors every score at 4. By asking factual │
│  questions and mapping in code, we get real differentiation.        │
│  controls_tested=true + confidence=high → F2=1 (not 4).            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 5: SCORING AGENT                              [LLM Call #4]   │
│  ─────────────────────────                                          │
│  Module: scoring_agent.py                                           │
│                                                                     │
│  Input:  ALL previous outputs + impact_table + likelihood_table     │
│          + memory (prior scored risks) + external intelligence      │
│                                                                     │
│  Does:   IMPACT (quantity-first approach):                          │
│          1. Evaluate all 7 impact dimensions                        │
│          2. Select PRIMARY dimension (not always Financial)         │
│          3. Extract evidence_quantity ("42 days", "EUR 400M")       │
│          4. Match quantity to table threshold → score               │
│                                                                     │
│          LIKELIHOOD:                                                │
│          • Uses code-computed composite as strong prior              │
│          • Can adjust ±1 only with specific missed evidence cited   │
│          • Code enforces ±1 clamp                                   │
│                                                                     │
│          INHERENT = Impact × Likelihood (computed in code)          │
│          Rating = lookup(inherent) (computed in code)               │
│                                                                     │
│  POST-LLM VALIDATION (in code):                                    │
│          • inherent_score = I × L (auto-corrected if wrong)        │
│          • risk_rating matches score band (auto-corrected)          │
│          • evidence_quantity matches score (auto-corrected)         │
│            e.g., "42 days" + score=4 → corrected to 5 (>14 days)  │
│          • likelihood within ±1 of composite (clamped)             │
│          • cascade_adjustment forced to null (set by cascade pass)  │
│                                                                     │
│  Output: ScoredRisk (saved to disk immediately)                     │
│                                                                     │
│  7 IMPACT DIMENSIONS:                                               │
│  ┌─────────────────────────────────────────────────────────┐        │
│  │ 1. Financial & Growth    (revenue, margins, costs)      │        │
│  │ 2. Operating             (production, supply chain)     │        │
│  │ 3. Customer & Market     (demand, market share, brand)  │        │
│  │ 4. Regulatory & Compliance (emissions, safety, fines)   │        │
│  │ 5. Technology & Information (cyber, IT/OT, data)        │        │
│  │ 6. People, Health & Safety (workforce, H&S, labour)     │        │
│  │ 7. Reputation & Ethics   (media, ESG, trust)            │        │
│  └─────────────────────────────────────────────────────────┘        │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │  MEMORY STORE        │
                    │  memory_store.py     │
                    │                     │
                    │  Records scored risk │
                    │  (compact ~50 tokens)│
                    │  Updates cascade     │
                    │  dependency graph    │
                    └─────────┬───────────┘
                              │
                    ┌─────────▼───────────┐
                    │  NEXT RISK           │
                    │  (repeat steps 1-5)  │
                    └─────────┬───────────┘
                              │
              ┌───────────────▼───────────────┐
              │  ALL RISKS SCORED              │
              └───────────────┬───────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 6: CASCADE SCORER (Second Pass)               [No LLM call]  │
│  ────────────────────────────────────                               │
│  Module: cascade_scorer.py                                          │
│                                                                     │
│  Does:   • Topological sort of cascade dependency graph             │
│          • If upstream risk has Likelihood ≥ 4:                     │
│            downstream risk gets Likelihood +1 (capped at 5)         │
│          • Only adjusts LIKELIHOOD, never Impact                    │
│          • Recalculates inherent score and rating                   │
│                                                                     │
│  WHY LIKELIHOOD ONLY: If Cyber Risk triggers Supply Chain           │
│  Disruption, the supply chain impact is the same regardless of      │
│  cause. But the probability increases (additional trigger pathway). │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 7: CONSISTENCY CHECKER (Post-Scoring)         [No LLM call]  │
│  ──────────────────────────────────────────                         │
│  Module: consistency_checker.py                                     │
│                                                                     │
│  Checks: • Cascade coherence (upstream L≥4 → downstream L≥3)       │
│          • Dimension consistency (same dimension, logical ordering) │
│          • Outlier detection (score deviates >2σ from mean)         │
│          • Score clustering (>75% same rating = lazy scoring)       │
│                                                                     │
│  Output: ConsistencyCheckResult with flags and recommendations      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  OUTPUT FILES                                                       │
│  ────────────                                                       │
│  output_auto_scored/                                                │
│  ├── RISK_001_scored.json      (per-risk, saved as completed)       │
│  ├── RISK_002_scored.json                                           │
│  ├── ...                                                            │
│  ├── scored_risk_universe.json (all risks consolidated)             │
│  ├── scoring_summary.json     (aggregate stats + consistency)       │
│  ├── scoring_review_queue.json (flagged risks)                      │
│  └── scoring_report.md        (human-readable audit report)         │
└─────────────────────────────────────────────────────────────────────┘
```

## Data Flow Summary

```
Transcript ──┐
             ├──→ Evidence Assembler ──→ EvidenceContext
Phase 1 ─────┘                              │
                                            ├──→ Knowledge Summarizer ──→ KnowledgeContext
Questionnaire ──────────────────────────────┘         │
                                                      ├──→ External Intelligence ──→ ExternalIntelligence
                                                      │         │
                                                      │         ├──→ Likelihood Intelligence ──→ LikelihoodIntelligence
Likelihood Table ─────────────────────────────────────┘         │         │
                                                                │         ├──→ Scoring Agent ──→ ScoredRisk
Impact Table ───────────────────────────────────────────────────┘         │
Memory (prior risks) ────────────────────────────────────────────────────┘
```

## LLM Calls Per Risk: 5 (Inherent Scoring)

| Call | Agent | Purpose | Input Tokens | Output Tokens |
|------|-------|---------|-------------|---------------|
| 1 | Knowledge Summarizer | Extract questionnaire data | ~2,500-3,500 | ~200-400 |
| 2 | External Intelligence (queries + synthesis) | Web search + synthesize | ~300 + ~1,700 | ~100 + ~200 |
| 3 | Likelihood Intelligence | Answer factual evidence questions | ~1,500-2,500 | ~300 |
| 4 | Dimension Classifier | Pick primary impact dimension | ~500 | ~100 |
| 5 | Scoring Agent | Impact + likelihood scoring | ~7,000-9,000 | ~500 |
| **Total** | | | **~13,500-17,500** | **~1,400-1,600** |

---

## Residual Risk Scoring (Post-Pipeline)

```
┌─────────────────────────────────────────────────────────────────────┐
│                    INPUTS                                           │
│                                                                     │
│  scored_risk_universe.json ─── VelocityAuto_RCM.xlsx                │
│  asset_risk_universe.json  ─── ERM_RCM_Residual_Risk_Guide.docx    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: PARSE RCM                                  [No LLM call]  │
│  Module: run_residual_scoring.py → parse_rcm()                      │
│                                                                     │
│  Reads VelocityAuto_RCM.xlsx → extracts 16 controls with:          │
│  risk_id, title, control_description, control_owner,                │
│  design_adequacy (1-5), operating_effectiveness (1-5),              │
│  composite_score (D×OE, 1-25), control_rating                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: TWO-STAGE CONTROL MATCHING                 [LLM calls]    │
│                                                                     │
│  For EACH risk (25 risks):                                          │
│                                                                     │
│  Stage 1 — MATCHER (1 LLM call per risk, ~500 tokens):             │
│    "Here is ONE risk. Here are 16 controls.                         │
│     Which ONE control directly addresses this risk? Or NONE?"       │
│                                                                     │
│  Stage 2 — VERIFIER (1 LLM call per matched risk, ~300 tokens):    │
│    "You matched 'Product testing risk' to 'Financial controls'.     │
│     Does this control ACTUALLY reduce this risk? YES or NO?"        │
│                                                                     │
│  If verifier says NO → match rejected → residual = inherent         │
│                                                                     │
│  Three outcomes per risk:                                           │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ DIRECT MATCH:  Control found and verified ✓              │       │
│  │ CROSS-MAPPED:  No direct match, expert agent found one   │       │
│  │ NO CONTROL:    No match → residual = inherent            │       │
│  └──────────────────────────────────────────────────────────┘       │
│                                                                     │
│  LLM calls: ~25 match + ~20 verify + ~5 cross-map = ~50 total      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: CROSS-MAPPING AGENT                        [LLM calls]    │
│                                                                     │
│  For unmatched risks only (~3-5 risks):                             │
│  Expert agent evaluates if ANY RCM control is applicable            │
│  Assigns adjusted D and OE for this specific risk                   │
│  Rejects if adjusted composite < 6 (too weak)                      │
│  Strict rules: "If connection requires >1 logical step → NONE"     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: COMPUTE RESIDUAL SCORES                    [No LLM call]  │
│                                                                     │
│  Formula (from ERM_RCM_Residual_Risk_Guide.docx):                   │
│                                                                     │
│  Composite = Design Adequacy × Operating Effectiveness (1-25)       │
│                                                                     │
│  ┌─────────────┬──────────────┬─────────────────────────────┐       │
│  │ Composite   │ Rating       │ Reduction                   │       │
│  ├─────────────┼──────────────┼─────────────────────────────┤       │
│  │ 20-25       │ Strong       │ Likelihood -2, Impact -2    │       │
│  │ 12-19       │ Satisfactory │ Likelihood -1, Impact -1    │       │
│  │ 6-11        │ Needs Improv │ Likelihood -1, Impact stays │       │
│  │ 1-5         │ Unsatisfact  │ No reduction                │       │
│  │ None        │ No Control   │ Residual = Inherent         │       │
│  └─────────────┴──────────────┴─────────────────────────────┘       │
│                                                                     │
│  All computed deterministically in code — no LLM math.              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  OUTPUT FILES                                                       │
│                                                                     │
│  output_residual/                                                   │
│  ├── residual_risk_universe.json  (all risks with audit trail)      │
│  └── Residual_Risk_Report.xlsx    (4-sheet formatted report)        │
│       ├── Risk Scoring Summary    (ranked, inherent + residual)     │
│       ├── Control Mapping         (D, OE, composite per risk)       │
│       ├── Audit Trail             (match reasoning per risk)        │
│       └── Distribution            (inherent vs residual counts)     │
└─────────────────────────────────────────────────────────────────────┘
```

## Per-Risk Audit Trail (in residual output)

```json
{
  "audit_trail": {
    "inherent_source": "scoring_pipeline",
    "control_source": "RCM (R-01)",
    "match_method": "direct",
    "match_detail": "Matched to R-01 and verified: R-01 directly addresses supply chain risk",
    "formula": "Composite=12 → Satisfactory: L-1, I-1"
  }
}
```

## Full Pipeline Execution Order

```
1. python scripts/build_asset_risk_universe.py    → data/asset_risk_universe.json
2. python run_scoring_resilient.py                → output_auto_scored_v2/ (inherent scores)
3. python run_residual_scoring.py                 → output_residual/ (residual scores)
4. python scripts/generate_residual_excel.py      → output_residual/Residual_Risk_Report.xlsx
```
