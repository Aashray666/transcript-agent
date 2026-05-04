# RiskMapper Agent System

An AI-powered pipeline that processes CRO interview transcripts and produces a structured risk universe mapped against a backend risk registry. Part of a larger Enterprise Risk Management (ERM) intelligence platform.

## What It Does

A risk consultant conducts a guided interview with a client's Chief Risk Officer. The interview is transcribed. RiskMapper takes that transcript and:

1. **Extracts** every distinct risk the client mentioned, preserving their exact language
2. **Deduplicates** overlapping mentions across questions into unique risks
3. **Maps** each risk to a standardized risk registry using semantic search + LLM evaluation
4. **Flags** unmapped or under-assessed risks for human consultant review
5. **Outputs** a structured JSON risk universe for downstream scoring and modeling

## Pipeline Flow

```
Transcript (TXT) + Registry (XLSX) + Sector
                    │
        ┌───────────┴───────────┐
        │  1. Load Registry     │  → ChromaDB vector store
        │  2. Parse Transcript  │  → Raw risk mentions (LLM × N chunks)
        │  3. Deduplicate       │  → Unique risks (LLM × 1-3 calls)
        │  4. Map to Registry   │  → Matched risks (LLM × 1 per risk)
        │  5. Validate          │  → Corrections applied (LLM × 1)
        │  6. Review Queue      │  → human_review_queue.json
        │  7. Build Output      │  → risk_universe.json + summary
        └───────────────────────┘
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set up your API key
cp .env.example .env
# Edit .env and add your Groq API key: GROQ_API_KEY=gsk_...

# 3. Run the pipeline
python run_auto.py
```

## Project Structure

```
riskmapper/
├── schemas.py                 # Pydantic data models + custom exceptions
├── llm_wrapper.py             # Groq REST API wrapper with retry + rate limiting
├── transcript_preprocessor.py # Strips interviewer lines, normalizes Q headers
├── transcript_parser.py       # Chunked transcript → raw risk mentions
├── deduplicator.py            # Two-pass dedup: cascade filter + LLM merge
├── registry_mapper.py         # ChromaDB search + LLM confidence evaluation
├── post_validator.py          # Feedback loop: merges, cascade links, bundle detection
├── human_review_queue.py      # Filters unmapped risks → JSON
├── output_builder.py          # Writes risk_universe.json + summary
└── pipeline.py                # Orchestrates all steps with logging + timing

tests/
├── conftest.py                # Shared fixtures
├── strategies.py              # Hypothesis strategies for property-based tests
├── test_schemas.py            # Property tests P1, P2 + unit tests
├── test_human_review_queue.py # Property test P7 + unit tests
└── test_output_builder.py     # Property tests P8, P9 + unit tests
```

## Configuration

| Variable | Description |
|---|---|
| `GROQ_API_KEY` | Groq API key (get one at https://console.groq.com) |

The pipeline uses `llama-3.3-70b-versatile` on Groq's free tier. Rate limits: 30 RPM, 12K TPM, 100K TPD.

## Input Files

- **Transcript** — UTF-8 text file of the CRO interview. Supports both plain text and markdown formats. Questions labeled Q1-Q18.
- **Risk Registry** — Excel workbook (`.xlsx`) with sector-specific sheets. Each sheet has columns: Risk Name, Primary Impact, Primary Impact Strength, Secondary Impact, etc.
- **Sector** — Must match a sheet name in the registry (e.g., "Automotive", "Telecommunication").

## Output Files

All written to the specified output directory:

| File | Description |
|---|---|
| `risk_universe.json` | Full structured risk universe with all fields |
| `risk_universe_summary.json` | Counts + risk list overview |
| `human_review_queue.json` | Risks needing consultant review |
| `pipeline.log` | Execution log with timing per step |

## Output Schema

Each risk in `risk_universe.json` contains:

- `risk_id` — Sequential ID (RISK_001, RISK_002, ...)
- `client_description` — How the CRO described the risk
- `verbatim_evidence` — Direct quotes from the transcript
- `question_source` — Which interview questions mentioned this risk
- `risk_type` — INHERENT / EVENT_DRIVEN / BOTH
- `flags` — UNREGISTERED, UNDERPREPARED, CASCADE_SIGNAL
- `cascade_context` — How this risk connects to others
- `cascade_links` — Linked RISK_NNN IDs
- `registry_matches` — Top 3 registry matches with confidence scores
- `unmapped` / `human_review` — Whether consultant review is needed

## Supported Sectors

Any sector with a matching sheet in the registry workbook: Automotive, Education, Financial, FMCG, Healthcare, Insurance, Manufacturing, Mining, Oil&Gas, Retail, Telecommunication, Travel.

## Limitations

- Groq free tier rate limits require ~15s between API calls. A full pipeline run takes 5-10 minutes.
- Chunked parsing means the LLM doesn't see the full transcript at once. Cross-question context is handled by the deduplication step.
- See `PIPELINE_LEARNINGS.md` for detailed analysis of v1 vs v2 approaches and improvement roadmap.

## Running Tests

```bash
pytest tests/ -v
```

Property-based tests validate schema round-trips, validation rejection, review queue filtering, output file integrity, and summary count invariants.
