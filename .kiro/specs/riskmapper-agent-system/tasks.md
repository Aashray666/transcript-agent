# Implementation Plan: RiskMapper Agent System

## Overview

Build a Python-based AI agent pipeline that processes CRO interview transcripts and produces a structured risk universe mapped against a backend risk registry. The implementation follows the module dependency graph: schemas → llm_wrapper → risk_registry_loader → transcript_parser → deduplicator → registry_mapper → human_review_queue → output_builder → pipeline, with property-based and unit tests woven in after each module.

## Tasks

- [x] 1. Set up project structure and dependencies
  - Create `riskmapper/` package directory with `__init__.py`
  - Create `tests/` directory with `__init__.py` and `conftest.py`
  - Create `requirements.txt` with: pydantic>=2.0, requests, chromadb, openpyxl, python-dotenv, pytest, hypothesis, pytest-mock
  - Create `.env.example` with `GEMINI_API_KEY=your-key-here`
  - _Requirements: 11.1, 11.2, 11.3_

- [x] 2. Implement Pydantic schemas and custom exceptions
  - [x] 2.1 Create `riskmapper/schemas.py` with all data models
    - Define `RawRiskMention` with UUID mention_id, client_description, verbatim_evidence, question_source (validated Q1-Q15), risk_type (Literal), flags (Literal list), cascade_context
    - Define `DeduplicatedRisk` with risk_id (validated RISK_NNN pattern), merged_from, and all risk fields
    - Define `RegistryMatch` with registry_risk_id, risk_name, primary_impact, confidence (Literal), similarity_score (0.0-1.0 validated)
    - Define `MappedRisk` with registry_matches, unmapped, human_review, human_review_reason, cascade_links
    - Define wrapper models: `TranscriptParseResponse(mentions: list[RawRiskMention])`, `DeduplicationResponse`
    - Define custom exceptions: `LLMCallError`, `RegistryLoadError`, `PipelineError`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [ ]* 2.2 Write property test for schema round-trip serialization
    - **Property 1: Schema round-trip serialization**
    - Generate random valid instances of all 4 schema types using Hypothesis strategies, serialize via `model_dump_json()`, deserialize via `model_validate_json()`, assert equality
    - Create `tests/strategies.py` with reusable Hypothesis strategies for valid_question_source, valid_risk_type, valid_flags, valid_confidence, valid_similarity
    - **Validates: Requirements 1.6, 12.2**

  - [ ]* 2.3 Write property test for schema validation rejection
    - **Property 2: Schema validation rejects invalid data**
    - Generate invalid field values (similarity_score outside [0,1], risk_id not matching RISK_NNN, question_source not Q1-Q15) and assert `ValidationError` is raised
    - **Validates: Requirements 1.5**

  - [ ]* 2.4 Write unit tests for schemas
    - Test valid construction of each schema type with known data
    - Test specific validation error messages for each constraint violation
    - _Requirements: 12.1_

- [x] 3. Implement LLM wrapper
  - [x] 3.1 Create `riskmapper/llm_wrapper.py`
    - Implement `LLMWrapper` class with `__init__(model, api_key)` loading GEMINI_API_KEY from env via python-dotenv
    - Implement `call(prompt, response_model, temperature, step_name)` using Python `requests` library to POST to Gemini REST API endpoint `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
    - Use `generationConfig.responseMimeType: "application/json"` and `generationConfig.responseSchema` derived from Pydantic model's `.model_json_schema()` for structured output
    - Parse response JSON and validate against Pydantic model using `model_validate()`
    - Extract token counts from `usageMetadata` in Gemini response
    - Implement retry logic: 3 retries with exponential backoff (1s, 2s, 4s) on API connection errors, rate limits, 5xx errors
    - Raise `LLMCallError` on exhausted retries without exposing raw Gemini API details
    - Log each call with model name, input/output token counts, latency, step_name via Python logging module
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [ ]* 3.2 Write unit tests for LLM wrapper
    - Test successful call with mocked Gemini REST API returns validated Pydantic model
    - Test retry behavior: mock 2 failures then success, verify 3 calls made
    - Test `LLMCallError` raised after 3 retries exhausted, verify no raw Gemini API details in message
    - _Requirements: 12.1_

- [x] 4. Implement risk registry loader
  - [x] 4.1 Create `riskmapper/risk_registry_loader.py`
    - Implement `load_registry(xlsx_path, sector, chroma_client, embedding_fn)` function
    - Read XLSX with openpyxl, iterate rows in named sector sheet
    - Generate `registry_risk_id` per row: `REG_{sector_prefix}_{row_index:003d}`
    - Embed text as `"{Primary Impact} - {Risk Name}"` per entry
    - Store in ChromaDB "risk_registry" collection with metadata (registry_risk_id, risk_name, primary_impact)
    - Achieve idempotency by deleting collection if exists then recreating
    - Raise `FileNotFoundError` for missing XLSX, `ValueError` for missing sheet or empty sheet
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [ ]* 4.2 Write property test for registry loader idempotency
    - **Property 3: Registry loader idempotency**
    - Generate random registry data, create test XLSX with openpyxl, call `load_registry` twice with same args using ephemeral ChromaDB client, assert same collection state (count, IDs, metadata)
    - **Validates: Requirements 2.4**

  - [ ]* 4.3 Write unit tests for risk registry loader
    - Test loading from a test XLSX file with known data, verify correct document count and metadata in ChromaDB
    - Test `FileNotFoundError` for missing file, `ValueError` for missing sheet, `ValueError` for empty sheet
    - _Requirements: 12.1, 12.5_

- [x] 5. Checkpoint — Verify foundation modules
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Implement transcript parser
  - [x] 6.1 Create `riskmapper/transcript_parser.py`
    - Implement `parse_transcript(transcript_text, sector, llm)` function
    - Construct prompt with RiskMapper Step 1 instructions, sector context, and transcript text
    - Request structured output via `TranscriptParseResponse` wrapper model
    - Use temperature=0, step_name="transcript_parsing"
    - Raise `ValueError` if zero mentions extracted
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 3.9, 3.10_

  - [ ]* 6.2 Write unit tests for transcript parser
    - Test parse with mocked LLM returning known RawRiskMention list, verify output structure and fields
    - Test `ValueError` raised when LLM returns empty mentions list
    - Test that sector string appears in the prompt passed to LLM
    - _Requirements: 12.1_

- [x] 7. Implement deduplicator
  - [x] 7.1 Create `riskmapper/deduplicator.py`
    - Implement `deduplicate_risks(mentions, llm)` function
    - Send all mentions to LLM with merge instructions, receive groupings
    - For each group: assign sequential RISK_001+ IDs, combine verbatim_evidence and question_source (deduped), merge flags (union), set merged_from
    - Use temperature=0, step_name="deduplication"
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7_

  - [ ]* 7.2 Write property test for deduplication data preservation
    - **Property 4: Deduplication preserves all input data**
    - Generate random RawRiskMention lists, mock LLM to return deterministic merge groups, verify union of merged_from equals set of all input mention_ids, verify combined evidence/sources are supersets
    - **Validates: Requirements 4.3, 4.4**

  - [ ]* 7.3 Write property test for deduplication count invariant
    - **Property 5: Deduplication count invariant**
    - Generate random RawRiskMention lists of varying sizes, mock LLM merge groups, verify output count ≤ input count
    - **Validates: Requirements 4.8, 12.3**

  - [ ]* 7.4 Write unit tests for deduplicator
    - Test merge with mocked LLM, verify sequential RISK_NNN ID assignment
    - Test single-mention passthrough (no merging needed), verify merged_from contains only that mention_id
    - _Requirements: 12.1_

- [x] 8. Implement registry mapper
  - [x] 8.1 Create `riskmapper/registry_mapper.py`
    - Implement `map_risks(risks, sector, chroma_client, embedding_fn, llm)` function
    - For each DeduplicatedRisk: query ChromaDB with client_description (n_results=3), build candidate list, send to LLM for confidence evaluation
    - Construct RegistryMatch objects from LLM response
    - Apply unmapped rule: if best confidence is LOW and best similarity_score < 0.75 → unmapped=True, human_review=True
    - On per-risk failure: catch exception, log, produce MappedRisk with unmapped=True, human_review=True, human_review_reason
    - Raise `RuntimeError` if collection is empty
    - Use temperature=0, step_name="registry_mapping"
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 5.8, 5.9, 5.10_

  - [ ]* 8.2 Write property test for unmapped flag decision rule
    - **Property 6: Unmapped flag decision rule**
    - Generate random RegistryMatch lists with varying confidence/similarity_score combinations, verify unmapped=True iff best confidence is LOW and best similarity < 0.75
    - **Validates: Requirements 5.3**

  - [ ]* 8.3 Write unit tests for registry mapper
    - Test mapping with mocked LLM + ephemeral ChromaDB, verify RegistryMatch construction and confidence assignment
    - Test per-risk failure handling: mock LLM to raise on one risk, verify it's marked unmapped with human_review_reason, other risks processed normally
    - Test `RuntimeError` raised when ChromaDB collection is empty
    - _Requirements: 12.1, 12.5_

- [x] 9. Checkpoint — Verify core processing modules
  - Ensure all tests pass, ask the user if questions arise.

- [x] 10. Implement human review queue generator
  - [x] 10.1 Create `riskmapper/human_review_queue.py`
    - Implement `generate_review_queue(mapped_risks, output_path)` function
    - Filter risks where human_review is True
    - Serialize via Pydantic model_dump(mode="json"), write UTF-8 JSON with indent=2
    - Write empty JSON array if no risks need review
    - Return count of queued risks
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 10.2 Write property test for human review queue filtering
    - **Property 7: Human review queue filtering**
    - Generate random MappedRisk lists with varying human_review flags, verify output contains exactly the risks with human_review=True and no others
    - **Validates: Requirements 6.1**

  - [ ]* 10.3 Write unit tests for human review queue
    - Test filter and write with mixed human_review flags, verify JSON file contents
    - Test empty queue scenario: all risks have human_review=False, verify empty array written
    - _Requirements: 12.1_

- [x] 11. Implement output builder
  - [x] 11.1 Create `riskmapper/output_builder.py`
    - Implement `build_output(mapped_risks, output_dir)` function
    - Create output_dir with os.makedirs(exist_ok=True)
    - Write `risk_universe.json`: full list of MappedRisk serialized via Pydantic
    - Write `risk_universe_summary.json`: total_risks, mapped_count, unmapped_count, human_review_count, risks list with risk_id/client_description/unmapped/registry_match_count
    - Enforce invariant: total_risks == mapped_count + unmapped_count
    - UTF-8 JSON with indent=2
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [ ]* 11.2 Write property test for output file round-trip
    - **Property 8: Output file round-trip**
    - Generate random MappedRisk lists, write via build_output, read back and parse risk_universe.json, verify list of MappedRisk equals original
    - **Validates: Requirements 6.5, 7.5**

  - [ ]* 11.3 Write property test for summary count invariant
    - **Property 9: Summary count invariant**
    - Generate random MappedRisk lists with varying unmapped/human_review flags, write via build_output, read summary, verify total_risks == mapped_count + unmapped_count, total_risks == len(input), human_review_count == count of human_review=True
    - **Validates: Requirements 7.2, 7.6, 12.4**

  - [ ]* 11.4 Write unit tests for output builder
    - Test write files to tmp_path, verify both JSON files exist and are valid
    - Test directory creation when output_dir doesn't exist
    - Test summary computation with known input data
    - _Requirements: 12.1_

- [x] 12. Implement pipeline orchestration
  - [x] 12.1 Create `riskmapper/pipeline.py`
    - Implement `run_pipeline(transcript_path, sector, registry_path, output_dir)` function
    - Validate inputs at startup: check file existence, check GEMINI_API_KEY env var (raise EnvironmentError if missing)
    - Initialize LLMWrapper, ChromaDB persistent client (directory in output_dir), default embedding function
    - Execute steps sequentially: load_registry → parse_transcript → deduplicate_risks → map_risks → generate_review_queue → build_output
    - Time each step and log durations
    - Configure Python logging to write to `{output_dir}/pipeline.log` with timestamps
    - Critical failures (registry loading, transcript parsing) terminate pipeline
    - Non-critical failures (individual risk mapping) logged and processing continues
    - Produce 4 output files: risk_universe.json, risk_universe_summary.json, human_review_queue.json, pipeline.log
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 10.1, 10.2, 10.3, 10.4, 10.5_

  - [ ]* 12.2 Write unit tests for pipeline
    - Test full run with all modules mocked, verify all 4 output files created
    - Test `FileNotFoundError` raised for missing transcript file
    - Test `EnvironmentError` raised when GEMINI_API_KEY not set (use monkeypatch)
    - Test critical step failure (registry loading) terminates pipeline with logged error
    - _Requirements: 12.1, 12.5_

- [x] 13. Wire shared test fixtures and finalize test suite
  - [x] 13.1 Create `tests/conftest.py` with shared fixtures
    - Define fixtures for mock LLMWrapper, sample RawRiskMention/DeduplicatedRisk/MappedRisk instances, ephemeral ChromaDB client, test XLSX workbook creation helper, tmp_path-based output directories, monkeypatched env vars (GEMINI_API_KEY)
    - Import and expose strategies from `tests/strategies.py`
    - _Requirements: 12.1_

  - [x] 13.2 Create `tests/strategies.py` with Hypothesis strategies
    - Define reusable strategies: valid_question_source, valid_risk_type, valid_flags, valid_confidence, valid_similarity_score
    - Define composite strategies for generating full valid instances of RawRiskMention, DeduplicatedRisk, RegistryMatch, MappedRisk
    - _Requirements: 12.1, 12.2_

- [x] 14. Final checkpoint — Full test suite green
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after foundation and core modules
- Property tests validate the 9 correctness properties defined in the design document
- Unit tests cover happy paths, error handling, and edge cases per module
- All LLM calls are mocked in tests — no real API calls during testing
- ChromaDB tests use ephemeral in-memory client for speed
