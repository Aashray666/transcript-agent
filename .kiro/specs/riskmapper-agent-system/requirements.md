# Requirements Document

## Introduction

RiskMapper is an MVP AI agent module within an Enterprise Risk Management (ERM) intelligence platform. It processes transcripts from guided 15-question CRO interviews and produces a structured risk universe that feeds downstream scoring and interconnectedness modeling. The system bridges natural client language to a structured backend risk registry using LLM-powered extraction, deduplication, semantic matching, and human review queuing.

The upstream flow provides: (1) a pre-call structured questionnaire, (2) an impact assessment table, (3) a 15-question guided interview transcript. RiskMapper consumes the transcript and a risk registry (sourced from an Excel workbook with sector-specific sheets) to produce structured JSON outputs.

This is an MVP build — the code should be straightforward, functional, and testable without unnecessary complexity.

## Glossary

- **Pipeline**: The end-to-end orchestration module that executes all processing steps in sequence from transcript ingestion to output generation.
- **Transcript**: A UTF-8 plain text file containing the transcribed recording of a guided 15-question CRO interview.
- **Risk_Registry**: An Excel workbook (XLSX) containing sector-specific sheets, each listing risks with columns: Risk Name, Primary Impact, Primary Impact Strength, Secondary Impact, Secondary Impact Strength, Tertiary Impact, Tertiary Impact Strength. Each sheet name corresponds to a Sector.
- **Risk_Registry_Loader**: The module responsible for loading risk registry entries from the appropriate sector sheet, embedding them, and storing them in the Vector_Store.
- **Transcript_Parser**: The module responsible for extracting structured risk mentions from a raw transcript using the LLM.
- **Deduplicator**: The module responsible for identifying and merging duplicate risk mentions using the LLM.
- **Registry_Mapper**: The module responsible for semantically matching deduplicated risks against the Vector_Store and producing confidence-scored mappings using the LLM.
- **Human_Review_Queue_Generator**: The module responsible for filtering unmapped risks and writing them to a review queue file.
- **Output_Builder**: The module responsible for assembling final risk universe JSON outputs from mapped risks.
- **Vector_Store**: A ChromaDB local persistent collection named "risk_registry" that stores embedded risk registry entries using cosine distance.
- **LLM**: Groq API (OpenAI-compatible) with model `llama-3.3-70b-versatile`, accessed via HTTP REST calls using the `requests` library, abstracted behind a provider-swappable wrapper. Authentication is via `Authorization: Bearer` header with `GROQ_API_KEY`.
- **Embedding_Model**: ChromaDB default embedding function (Sentence Transformers, local) used to generate vector embeddings for semantic search. No external embedding API calls required for MVP.
- **RawRiskMention**: A Pydantic v2 schema representing a single risk mention extracted from the transcript, including mention_id, client_description, verbatim_evidence, question_source, risk_type, flags, and cascade_context.
- **DeduplicatedRisk**: A Pydantic v2 schema representing a merged risk after deduplication, including a sequential risk_id (RISK_001 format), merged_from list, and all fields from RawRiskMention.
- **RegistryMatch**: A Pydantic v2 schema representing a single candidate match from the Vector_Store, including registry_risk_id, risk_name, primary_impact (category), confidence level, and similarity_score.
- **MappedRisk**: A Pydantic v2 schema representing a fully processed risk with registry matches, unmapped status, human_review flag, human_review_reason, and cascade_links.
- **Sector**: A string identifier matching a sheet name in the Risk_Registry workbook (e.g., "Telecommunication"), used as context in all LLM prompts and for selecting the correct registry sheet.
- **Confidence_Level**: A categorical rating (HIGH, MEDIUM, LOW) assigned by the LLM to each registry match indicating mapping certainty.
- **Similarity_Score**: A float value between 0.0 and 1.0 representing the cosine similarity between a risk mention embedding and a registry entry embedding.

## Requirements

### Requirement 1: Pydantic Schema Definitions

**User Story:** As a developer, I want all data structures defined as Pydantic v2 schemas in a single module, so that data validation is consistent and centralized across the entire pipeline.

#### Acceptance Criteria

1. THE Schemas module SHALL define RawRiskMention with fields: mention_id (UUID), client_description (str), verbatim_evidence (List[str]), question_source (List[str] matching Q1-Q15), risk_type (Literal["INHERENT", "EVENT_DRIVEN", "BOTH"]), flags (List[Literal["UNREGISTERED", "UNDERPREPARED", "CASCADE_SIGNAL"]]), and cascade_context (Optional[str]).
2. THE Schemas module SHALL define DeduplicatedRisk with fields: risk_id (str matching pattern RISK_NNN), client_description (str), verbatim_evidence (List[str]), question_source (List[str]), risk_type (Literal["INHERENT", "EVENT_DRIVEN", "BOTH"]), flags (List[Literal["UNREGISTERED", "UNDERPREPARED", "CASCADE_SIGNAL"]]), cascade_context (Optional[str]), and merged_from (List[str] of mention_ids).
3. THE Schemas module SHALL define RegistryMatch with fields: registry_risk_id (str), risk_name (str), primary_impact (str), confidence (Literal["HIGH", "MEDIUM", "LOW"]), and similarity_score (float between 0.0 and 1.0).
4. THE Schemas module SHALL define MappedRisk with fields: risk_id (str), client_description (str), verbatim_evidence (List[str]), question_source (List[str]), risk_type (Literal), flags (List[Literal]), cascade_context (Optional[str]), registry_matches (List[RegistryMatch]), unmapped (bool), human_review (bool), human_review_reason (Optional[str]), and cascade_links (List[str]).
5. WHEN invalid data is provided to any schema, THE Schemas module SHALL raise a Pydantic ValidationError with a descriptive message identifying the invalid field.
6. FOR ALL valid schema instances, serializing to JSON then deserializing back SHALL produce an equivalent schema instance (round-trip property).

### Requirement 2: Risk Registry Loading and Embedding

**User Story:** As a risk consultant, I want the risk registry loaded from the correct sector sheet and embedded into a vector store, so that semantic matching can be performed against client risk mentions.

#### Acceptance Criteria

1. WHEN a valid Risk_Registry XLSX file path and a Sector name are provided, THE Risk_Registry_Loader SHALL read the matching sheet from the workbook and store each risk entry as an embedded document in the Vector_Store "risk_registry" collection.
2. THE Risk_Registry_Loader SHALL store documents with the text format "{Primary Impact} - {Risk Name}" for each registry entry. ChromaDB's default embedding function (Sentence Transformers, local) SHALL be used for embedding generation.
3. THE Risk_Registry_Loader SHALL store metadata per document including a generated registry_risk_id, risk_name, and primary_impact.
4. THE Risk_Registry_Loader SHALL be idempotent: calling load_registry with the same file path and Sector multiple times SHALL produce the same Vector_Store state as calling it once.
5. WHEN the Risk_Registry XLSX file does not exist or the specified Sector sheet is not found, THE Risk_Registry_Loader SHALL raise a descriptive error indicating the file path and the missing sheet name.
6. WHEN the specified Sector sheet contains zero risk entries, THE Risk_Registry_Loader SHALL raise a ValueError indicating that the registry sheet is empty.

### Requirement 3: Transcript Parsing and Risk Extraction

**User Story:** As a risk consultant, I want structured risk mentions extracted from a CRO interview transcript, so that I can work with formalized risk data instead of raw text.

#### Acceptance Criteria

1. WHEN a valid transcript text and Sector are provided, THE Transcript_Parser SHALL extract a list of RawRiskMention objects from the transcript using the LLM.
2. THE Transcript_Parser SHALL tag each RawRiskMention with the question_source (Q1-Q15) identifying which interview question triggered the mention.
3. THE Transcript_Parser SHALL classify each RawRiskMention with a risk_type of INHERENT, EVENT_DRIVEN, or BOTH.
4. THE Transcript_Parser SHALL assign flags (UNREGISTERED, UNDERPREPARED, CASCADE_SIGNAL) to each RawRiskMention based on the transcript context.
5. THE Transcript_Parser SHALL include the client Sector in the LLM prompt as contextual information for extraction.
6. THE Transcript_Parser SHALL use temperature 0 for the LLM call and request structured output conforming to the RawRiskMention schema.
7. WHEN the LLM extracts zero risk mentions from the transcript, THE Transcript_Parser SHALL raise a ValueError indicating that no risk mentions were found.
8. THE Transcript_Parser SHALL include verbatim_evidence as direct quotes from the transcript for each extracted risk mention.
9. IF the LLM API call fails, THEN THE Transcript_Parser SHALL retry up to 3 times with exponential backoff before raising an error.
10. THE Transcript_Parser SHALL log each LLM call with model name, input token count, output token count, latency, and step name "transcript_parsing".

### Requirement 4: Risk Mention Deduplication

**User Story:** As a risk consultant, I want duplicate risk mentions merged into single entries, so that the risk universe is clean and non-redundant.

#### Acceptance Criteria

1. WHEN a list of RawRiskMention objects is provided, THE Deduplicator SHALL identify semantically duplicate mentions and merge them into DeduplicatedRisk objects using the LLM.
2. THE Deduplicator SHALL assign sequential risk_id values in the format RISK_001, RISK_002, etc., to each DeduplicatedRisk.
3. THE Deduplicator SHALL populate the merged_from field with the mention_id values of all RawRiskMention objects that were merged into each DeduplicatedRisk.
4. THE Deduplicator SHALL combine verbatim_evidence and question_source lists from merged mentions without losing any entries.
5. THE Deduplicator SHALL use temperature 0 for the LLM call and request structured output.
6. IF the LLM API call fails, THEN THE Deduplicator SHALL retry up to 3 times with exponential backoff before raising an error.
7. THE Deduplicator SHALL log each LLM call with model name, input token count, output token count, latency, and step name "deduplication".
8. THE Deduplicator SHALL produce a number of DeduplicatedRisk objects less than or equal to the number of input RawRiskMention objects (metamorphic property).

### Requirement 5: Semantic Registry Mapping

**User Story:** As a risk consultant, I want each deduplicated risk matched against the risk registry with confidence scores, so that I can see how client-described risks align with known risk categories.

#### Acceptance Criteria

1. WHEN a list of DeduplicatedRisk objects and a Sector are provided, THE Registry_Mapper SHALL query the Vector_Store for the top 3 candidate matches for each risk using cosine similarity.
2. THE Registry_Mapper SHALL use the LLM to evaluate each candidate match and assign a Confidence_Level of HIGH, MEDIUM, or LOW.
3. WHEN a DeduplicatedRisk has a highest Confidence_Level of LOW and a highest Similarity_Score below 0.75, THE Registry_Mapper SHALL mark the resulting MappedRisk as unmapped with unmapped set to true.
4. THE Registry_Mapper SHALL support multi-mapping, allowing a single DeduplicatedRisk to match multiple registry entries in the registry_matches list.
5. THE Registry_Mapper SHALL include the client Sector in the LLM prompt as contextual information for mapping evaluation.
6. THE Registry_Mapper SHALL use temperature 0 for the LLM call and request structured output.
7. IF the Vector_Store "risk_registry" collection is empty, THEN THE Registry_Mapper SHALL raise a RuntimeError indicating that the registry has not been loaded.
8. IF processing a single DeduplicatedRisk fails, THEN THE Registry_Mapper SHALL log the error, mark the resulting MappedRisk as unmapped with human_review set to true and human_review_reason describing the failure, and continue processing remaining risks.
9. IF the LLM API call fails, THEN THE Registry_Mapper SHALL retry up to 3 times with exponential backoff before treating the risk as a processing failure.
10. THE Registry_Mapper SHALL log each LLM call with model name, input token count, output token count, latency, and step name "registry_mapping".

### Requirement 6: Human Review Queue Generation

**User Story:** As a risk consultant, I want unmapped and flagged risks collected into a review queue file, so that I can manually review risks that the system could not confidently map.

#### Acceptance Criteria

1. WHEN a list of MappedRisk objects is provided, THE Human_Review_Queue_Generator SHALL filter risks where human_review is true and write them to the specified output path as a JSON file.
2. THE Human_Review_Queue_Generator SHALL include the human_review_reason for each risk in the output file.
3. WHEN no risks require human review, THE Human_Review_Queue_Generator SHALL write an empty JSON array to the output file.
4. THE Human_Review_Queue_Generator SHALL write valid UTF-8 encoded JSON to the output file.
5. FOR ALL generated human review queue files, parsing the JSON output SHALL produce a valid list of MappedRisk objects (round-trip property).

### Requirement 7: Output Building

**User Story:** As a risk consultant, I want the final risk universe written to structured JSON files, so that downstream scoring and interconnectedness modeling can consume the results.

#### Acceptance Criteria

1. WHEN a list of MappedRisk objects and an output directory are provided, THE Output_Builder SHALL write a risk_universe.json file containing the full list of MappedRisk objects serialized as JSON.
2. THE Output_Builder SHALL write a risk_universe_summary.json file containing a summary with total_risks count, mapped_count, unmapped_count, human_review_count, and a list of risk summaries (risk_id, client_description, unmapped status, number of registry matches).
3. THE Output_Builder SHALL create the output directory if the directory does not exist.
4. THE Output_Builder SHALL write valid UTF-8 encoded JSON to all output files.
5. FOR ALL generated risk_universe.json files, parsing the JSON output SHALL produce a valid list of MappedRisk objects (round-trip property).
6. THE Output_Builder SHALL ensure that total_risks in the summary equals the sum of mapped_count and unmapped_count.

### Requirement 8: End-to-End Pipeline Orchestration

**User Story:** As a risk consultant, I want a single command to run the full risk extraction pipeline, so that I can process a transcript without manually invoking each step.

#### Acceptance Criteria

1. WHEN a transcript file path, Sector, Risk_Registry XLSX file path, and output directory are provided, THE Pipeline SHALL execute all processing steps in sequence: registry loading, transcript parsing, deduplication, registry mapping, human review queue generation, and output building.
2. THE Pipeline SHALL record and log the execution time for each processing step and the total pipeline duration.
3. IF a single MappedRisk fails during registry mapping, THEN THE Pipeline SHALL log the failure and continue processing remaining risks without terminating.
4. THE Pipeline SHALL write structured logs to a pipeline.log file in the output directory including timestamps, step names, and error details.
5. WHEN the transcript file does not exist or is not readable, THE Pipeline SHALL raise a descriptive error before beginning processing.
6. THE Pipeline SHALL produce four output files: risk_universe.json, risk_universe_summary.json, human_review_queue.json, and pipeline.log in the specified output directory.
7. IF any critical step (registry loading, transcript parsing) fails, THEN THE Pipeline SHALL terminate with a descriptive error and log the failure.

### Requirement 9: LLM Wrapper and Calling Conventions

**User Story:** As a developer, I want LLM calls abstracted behind a provider-swappable wrapper, so that the system can switch LLM providers without modifying business logic modules.

#### Acceptance Criteria

1. THE LLM wrapper SHALL provide a call interface that accepts a prompt, a Pydantic model for structured output, and a temperature parameter.
2. THE LLM wrapper SHALL default to Groq API with model `llama-3.3-70b-versatile` via the OpenAI-compatible REST endpoint (`https://api.groq.com/openai/v1/chat/completions`) using the `requests` library.
3. THE LLM wrapper SHALL use JSON mode with `response_format: {"type": "json_object"}` and include the Pydantic model's JSON schema in the prompt. The response JSON SHALL be validated against the Pydantic model after receipt.
4. THE LLM wrapper SHALL implement retry logic with 3 retries and exponential backoff on API errors.
5. THE LLM wrapper SHALL log each call with model name, input token count, output token count, latency, and step name.
6. IF all retries are exhausted, THEN THE LLM wrapper SHALL raise a descriptive error without exposing raw Groq API error details to the caller.
7. THE LLM wrapper SHALL load the Groq API key from the GROQ_API_KEY environment variable using python-dotenv.

### Requirement 10: Logging and Observability

**User Story:** As a developer, I want structured logging throughout the pipeline, so that I can diagnose issues and monitor system performance.

#### Acceptance Criteria

1. THE Pipeline SHALL use the Python standard logging module for all log output.
2. THE Pipeline SHALL write log entries to a pipeline.log file in the output directory.
3. THE Pipeline SHALL log each LLM call with model name, input token count, output token count, latency, and step name.
4. THE Pipeline SHALL log the start and completion of each processing step with timestamps.
5. IF an error occurs during any processing step, THEN THE Pipeline SHALL log the error with full context including step name, risk_id (if applicable), and error description.

### Requirement 11: Configuration and Environment

**User Story:** As a developer, I want secrets and configuration managed through environment variables, so that sensitive credentials are not hardcoded in source files.

#### Acceptance Criteria

1. THE Pipeline SHALL load the Groq API key from the GROQ_API_KEY environment variable using python-dotenv.
2. IF the GROQ_API_KEY environment variable is not set, THEN THE Pipeline SHALL raise a descriptive error at startup before beginning processing.
3. THE Pipeline SHALL use python-dotenv to load a .env file from the project root when present.

### Requirement 12: Testing

**User Story:** As a developer, I want comprehensive unit tests for each module, so that I can verify correctness and catch regressions.

#### Acceptance Criteria

1. THE test suite SHALL include at least 2 pytest unit tests per module for each of the 8 modules (schemas, risk_registry_loader, transcript_parser, deduplicator, registry_mapper, human_review_queue, output_builder, pipeline).
2. THE test suite SHALL verify schema round-trip serialization for all Pydantic models (serialize to JSON then deserialize produces equivalent object).
3. THE test suite SHALL verify that the Deduplicator produces a number of DeduplicatedRisk objects less than or equal to the number of input RawRiskMention objects.
4. THE test suite SHALL verify that the Output_Builder summary total_risks equals mapped_count plus unmapped_count.
5. THE test suite SHALL verify error handling paths including missing files, empty registries, and zero extracted mentions.
