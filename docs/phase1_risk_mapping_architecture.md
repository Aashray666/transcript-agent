# Phase 1: Risk Mapping Pipeline — Architecture

## Overview

Phase 1 takes a CRO interview transcript and produces a structured **risk universe** — a deduplicated, registry-mapped list of all risks the client mentioned, with verbatim evidence, risk classification, and flags for human review.

```
Interview Transcript ──→ Risk Universe (JSON)
     + Risk Registry        with registry matches,
                            evidence, and flags
```

---

## Pipeline Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INPUTS                                      │
│                                                                     │
│  auto_transcript.txt ──── CRO interview transcript (~20K chars)     │
│  risk.xlsx ────────────── Backend risk registry (sector-specific)    │
│  sector: "Automotive" ─── Determines which registry sheet to load   │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 1: RISK REGISTRY LOADER                       [No LLM call]  │
│  Module: risk_registry_loader.py                                    │
│                                                                     │
│  Input:  risk.xlsx (sector sheet) + ChromaDB client                 │
│  Does:   • Reads XLSX with openpyxl, iterates sector sheet rows     │
│          • Generates registry_risk_id per row (REG_AUT_001, etc.)   │
│          • Embeds text as "{Primary Impact} - {Risk Name}"          │
│          • Stores in ChromaDB "risk_registry" collection            │
│          • Idempotent: deletes + recreates collection each run      │
│  Output: ChromaDB collection with 73 registry entries (Automotive)  │
│                                                                     │
│  Purpose: Creates the vector store that risks will be matched       │
│  against in Step 4. The registry is the "known risk universe"       │
│  from industry standards — client risks are mapped against it.      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 2: TRANSCRIPT PARSER                          [LLM calls]     │
│  Module: transcript_parser.py + transcript_preprocessor.py          │
│                                                                     │
│  Input:  Raw transcript text + sector                               │
│  Does:   2a. PREPROCESS (no LLM):                                   │
│              • Strip interviewer lines (keep CRO responses only)    │
│              • Normalize question headers (Q1, Q2, ... Q18)         │
│              • Clean whitespace, reduce transcript by ~13%          │
│                                                                     │
│          2b. CHUNK by question sections:                            │
│              • Split on Q-number headers                            │
│              • Group into chunks of ~2000 chars each                │
│              • Produces 15 chunks for VelocityAuto transcript       │
│                                                                     │
│          2c. PARSE each chunk via LLM:                              │
│              • System prompt: ERM analyst extraction rules          │
│              • Per chunk: extract all distinct risk mentions         │
│              • Each mention gets:                                   │
│                - client_description (client's own language)         │
│                - verbatim_evidence (1-3 direct quotes)              │
│                - question_source (Q1-Q18 where mentioned)           │
│                - risk_type (INHERENT / EVENT_DRIVEN / BOTH)         │
│                - flags (UNREGISTERED / UNDERPREPARED / CASCADE)     │
│                - cascade_context (if CASCADE_SIGNAL flagged)        │
│              • UUID assigned to each mention                        │
│                                                                     │
│  Output: ~84 RawRiskMention objects (many duplicates across chunks) │
│                                                                     │
│  LLM calls: 15 (one per chunk)                                     │
│                                                                     │
│  Risk Classification Rules:                                         │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ INHERENT:      Mentioned in Q3 or described as permanent │       │
│  │ EVENT_DRIVEN:  Mentioned in Q4 or externally triggered   │       │
│  │ BOTH:          Appears in both contexts                  │       │
│  │ UNREGISTERED:  Client says not on formal register (Q2)   │       │
│  │ UNDERPREPARED: Client says underprepared for it (Q15)    │       │
│  │ CASCADE_SIGNAL: Triggers or triggered by other risks     │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 3: DEDUPLICATOR                               [LLM call]     │
│  Module: deduplicator.py                                            │
│                                                                     │
│  Input:  ~84 RawRiskMention objects                                 │
│  Does:   • Sends all mentions to LLM with merge instructions       │
│          • LLM groups semantically identical risks                  │
│          • For each group:                                          │
│            - Assigns sequential RISK_001, RISK_002, ... IDs        │
│            - Combines verbatim_evidence (union of all quotes)       │
│            - Merges question_source (deduplicated)                  │
│            - Merges flags (union)                                   │
│            - Sets merged_from (list of original mention UUIDs)      │
│          • Preserves all evidence — nothing is lost                 │
│                                                                     │
│  Output: 16 DeduplicatedRisk objects (from 84 mentions = 81% reduction) │
│                                                                     │
│  LLM calls: 1                                                      │
│                                                                     │
│  Invariants (validated):                                            │
│  • output count ≤ input count                                      │
│  • union of merged_from = set of all input mention_ids             │
│  • combined evidence is superset of individual evidence            │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 4: REGISTRY MAPPER                            [LLM calls]    │
│  Module: registry_mapper.py                                         │
│                                                                     │
│  Input:  16 DeduplicatedRisk + ChromaDB collection                  │
│  Does:   For each risk:                                             │
│          4a. VECTOR SEARCH: Query ChromaDB with client_description  │
│              → top 3 candidates by cosine similarity                │
│                                                                     │
│          4b. LLM CONFIDENCE EVAL: Send risk + 3 candidates to LLM  │
│              → LLM assigns HIGH / MEDIUM / LOW per candidate        │
│                                                                     │
│          4c. UNMAPPED RULE: If best confidence = LOW AND             │
│              best similarity < 0.75 → mark as unmapped              │
│              → flag for human review                                │
│                                                                     │
│          4d. ERROR HANDLING: If per-risk mapping fails,             │
│              mark as unmapped with human_review_reason               │
│                                                                     │
│  Output: 16 MappedRisk objects with registry_matches                │
│          (14 mapped, 2 unmapped for VelocityAuto)                   │
│                                                                     │
│  LLM calls: 16 (one per risk)                                      │
│                                                                     │
│  ChromaDB Query Flow:                                               │
│  ┌──────────────────────────────────────────────────────────┐       │
│  │ "Supply chain risk"                                      │       │
│  │        │                                                 │       │
│  │        ▼ cosine similarity search                        │       │
│  │ ┌────────────────────────────────────────────────┐       │       │
│  │ │ REG_AUT_033: "Potential increased tariffs..."  │ 0.85  │       │
│  │ │ REG_AUT_041: "Supply chain disruption..."      │ 0.82  │       │
│  │ │ REG_AUT_019: "Raw material shortage..."        │ 0.78  │       │
│  │ └────────────────────────────────────────────────┘       │       │
│  │        │                                                 │       │
│  │        ▼ LLM evaluates confidence                        │       │
│  │ REG_AUT_033: HIGH, REG_AUT_041: HIGH, REG_AUT_019: MED  │       │
│  └──────────────────────────────────────────────────────────┘       │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 5: POST VALIDATOR                             [LLM call]     │
│  Module: post_validator.py                                          │
│                                                                     │
│  Input:  16 MappedRisk objects                                      │
│  Does:   • Reviews the full risk universe for completeness          │
│          • Checks for missing risks that should have been caught    │
│          • Validates consistency of flags and classifications       │
│  Output: Validated list of MappedRisk (may add/remove risks)        │
│                                                                     │
│  LLM calls: 1                                                      │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 6: HUMAN REVIEW QUEUE                         [No LLM call]  │
│  Module: human_review_queue.py                                      │
│                                                                     │
│  Input:  MappedRisk list                                            │
│  Does:   • Filters risks where human_review = True                  │
│          • Writes to human_review_queue.json (UTF-8, indent=2)      │
│          • Empty array if no risks need review                      │
│  Output: human_review_queue.json                                    │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│  STEP 7: OUTPUT BUILDER                             [No LLM call]  │
│  Module: output_builder.py                                          │
│                                                                     │
│  Input:  MappedRisk list + output directory                         │
│  Does:   • risk_universe.json: Full MappedRisk list                 │
│          • risk_universe_summary.json: Aggregate stats              │
│            - total_risks, mapped_count, unmapped_count              │
│            - human_review_count                                     │
│            - per-risk: risk_id, description, unmapped, match_count  │
│          • Enforces: total = mapped + unmapped                      │
│  Output: 2 JSON files + pipeline.log                                │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Data Models (Schema Flow)

```
Transcript Text
      │
      ▼
RawRiskMention (per chunk extraction)
  ├── mention_id: UUID
  ├── client_description: str
  ├── verbatim_evidence: list[str]
  ├── question_source: list[str]  (Q1-Q18)
  ├── risk_type: INHERENT | EVENT_DRIVEN | BOTH
  ├── flags: [UNREGISTERED, UNDERPREPARED, CASCADE_SIGNAL]
  └── cascade_context: str | None
      │
      ▼ (deduplication)
DeduplicatedRisk
  ├── risk_id: str  (RISK_001, RISK_002, ...)
  ├── merged_from: list[str]  (original mention UUIDs)
  ├── [all RawRiskMention fields, merged]
      │
      ▼ (registry mapping)
MappedRisk
  ├── [all DeduplicatedRisk fields]
  ├── registry_matches: list[RegistryMatch]
  │     ├── registry_risk_id: str
  │     ├── risk_name: str
  │     ├── primary_impact: str
  │     ├── confidence: HIGH | MEDIUM | LOW
  │     └── similarity_score: 0.0-1.0
  ├── unmapped: bool
  ├── human_review: bool
  ├── human_review_reason: str | None
  └── cascade_links: list[str]
```

---

## LLM Call Summary

| Step | Module | Calls | Purpose |
|------|--------|-------|---------|
| 1 | risk_registry_loader | 0 | XLSX → ChromaDB (no LLM) |
| 2 | transcript_parser | 15 | Extract risk mentions per chunk |
| 3 | deduplicator | 1 | Merge duplicate mentions |
| 4 | registry_mapper | 16 | Evaluate registry match confidence |
| 5 | post_validator | 1 | Validate completeness |
| 6 | human_review_queue | 0 | Filter + write JSON |
| 7 | output_builder | 0 | Write output files |
| **Total** | | **33** | |

---

## Output Files

```
output_auto/
├── risk_universe.json          # Full MappedRisk list (16 risks)
├── risk_universe_summary.json  # Aggregate stats
├── human_review_queue.json     # Risks flagged for review (2 risks)
└── pipeline.log                # Full execution log with timing
```

---

## Key Design Decisions

1. **Chunk-per-question parsing** — transcript split by Q-number headers, not arbitrary character limits. Ensures each chunk has complete context for a question section.

2. **Aggressive deduplication** — 84 mentions → 16 risks (81% reduction). The CRO mentions the same risk across multiple questions (e.g., "supply chain" appears in Q1, Q4, Q5, Q9, Q10, Q17, Q18). Dedup merges these into one risk with all evidence combined.

3. **Vector search + LLM confidence** — ChromaDB finds candidates by semantic similarity, then LLM evaluates whether the match is actually correct. This two-stage approach catches false positives from vector search.

4. **Unmapped rule** — if best confidence is LOW AND best similarity < 0.75, the risk is marked unmapped. This catches genuinely novel risks that don't exist in the standard registry.

5. **Flags as metadata** — UNREGISTERED, UNDERPREPARED, CASCADE_SIGNAL are extracted during parsing and preserved through dedup and mapping. Phase 2 scoring uses these flags to adjust likelihood.

6. **Per-risk error handling** — if one risk fails during mapping, it's marked for human review and processing continues. The pipeline never crashes on a single risk failure.

---

## Phase 1 → Phase 2 Handoff

Phase 1 output (`risk_universe.json`) is the input to Phase 2 scoring:

```
Phase 1 Output                    Phase 2 Uses
─────────────                     ──────────────
client_description ──────────────→ Scoring Agent (what to score)
verbatim_evidence ───────────────→ Evidence Assembler (transcript quotes)
question_source ─────────────────→ Evidence Assembler (which Q sections)
risk_type ───────────────────────→ Likelihood Intelligence (inherent vs event-driven)
flags ───────────────────────────→ Likelihood Intelligence (UNDERPREPARED → +1 likelihood)
cascade_context ─────────────────→ Cascade Scorer (dependency graph)
cascade_links ───────────────────→ Cascade Scorer (upstream/downstream)
registry_matches ────────────────→ Scoring Agent (sector context)
unmapped ────────────────────────→ Scoring Agent (flag for review if unmapped)
```
