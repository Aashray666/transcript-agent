"""Pydantic schemas for the Document Risk Extractor agent.

Designed to work with any document type:
- Internal audit reports
- Earnings call / con-call transcripts
- Annual reports (10-K, AR)
- Board presentations
- Management letters
- Regulatory filings

The schemas are intentionally broader than the CRO interview schemas
because these documents don't follow a Q&A structure — risks are embedded
in narrative prose, tables, footnotes, and management commentary.
"""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Document type taxonomy
# ---------------------------------------------------------------------------

DocumentType = Literal[
    "audit_report",
    "con_call_transcript",
    "annual_report",
    "board_presentation",
    "management_letter",
    "regulatory_filing",
    "other",
]

# Maps document type → extraction strategy hint for the LLM
DOCUMENT_TYPE_HINTS: dict[str, str] = {
    "audit_report": (
        "Focus on: audit findings, control deficiencies, management action items, "
        "repeat findings, material weaknesses, significant deficiencies, "
        "observations, recommendations, and management responses."
    ),
    "con_call_transcript": (
        "Focus on: analyst questions about risks, management hedging language, "
        "forward-looking statements with uncertainty, guidance caveats, "
        "competitive pressures mentioned, macro headwinds, and operational challenges."
    ),
    "annual_report": (
        "Focus on: Risk Factors section, MD&A risk commentary, going concern notes, "
        "contingent liabilities, legal proceedings, regulatory disclosures, "
        "and forward-looking statement caveats."
    ),
    "board_presentation": (
        "Focus on: escalated risks, strategic risks, risks requiring board attention, "
        "risk appetite breaches, emerging risks, and scenario analysis."
    ),
    "management_letter": (
        "Focus on: control gaps, process weaknesses, compliance issues, "
        "recommendations, and management commitments."
    ),
    "regulatory_filing": (
        "Focus on: disclosed risk factors, regulatory compliance status, "
        "enforcement actions, pending investigations, and material uncertainties."
    ),
    "other": (
        "Focus on: any language indicating uncertainty, potential loss, "
        "operational challenges, compliance issues, or strategic threats."
    ),
}


# ---------------------------------------------------------------------------
# Chunk metadata — tracks where in the document a chunk came from
# ---------------------------------------------------------------------------

class ChunkMetadata(BaseModel):
    """Provenance metadata for a document chunk."""

    chunk_id: str                          # e.g. "chunk_001"
    document_name: str                     # original filename
    document_type: DocumentType
    section_label: str                     # e.g. "Risk Factors", "Page 12", "Para 3.2"
    char_start: int                        # character offset in original document
    char_end: int
    chunk_index: int                       # 0-based position in chunk list
    total_chunks: int


# ---------------------------------------------------------------------------
# Raw risk mention — extracted from a single chunk
# ---------------------------------------------------------------------------

class DocumentRiskMention(BaseModel):
    """A single risk mention extracted from a document chunk.

    Broader than RawRiskMention (CRO interview) because:
    - source_section replaces question_source (no Q-numbers in documents)
    - severity_signal captures explicit severity language from the document
    - financial_quantification captures any numbers attached to the risk
    - management_response captures what the company says it's doing about it
    """

    mention_id: UUID
    client_description: str               # Risk in clear, concise language
    verbatim_evidence: list[str]          # 1-5 direct quotes from the document
    source_section: str                   # Section/page where found
    chunk_id: str                         # Which chunk this came from
    risk_type: Literal["INHERENT", "EVENT_DRIVEN", "BOTH"]
    risk_category: str                    # High-level category (e.g. "Operational", "Financial")
    severity_signal: Literal[
        "CRITICAL", "HIGH", "MEDIUM", "LOW", "UNSPECIFIED"
    ]                                     # Severity language used in the document
    financial_quantification: str | None  # Any $ / % / number attached to the risk
    management_response: str | None       # What management says they're doing
    flags: list[Literal[
        "REPEAT_FINDING",        # Audit: same finding in prior period
        "MATERIAL_WEAKNESS",     # Audit: material weakness identified
        "SIGNIFICANT_DEFICIENCY",# Audit: significant deficiency
        "UNMITIGATED",           # No controls or response mentioned
        "ESCALATED",             # Explicitly escalated to board/senior mgmt
        "QUANTIFIED",            # Has a financial number attached
        "FORWARD_LOOKING",       # Future risk, not yet materialized
        "ALREADY_MATERIALIZED",  # Risk has already occurred
        "CASCADE_SIGNAL",        # Triggers or is triggered by other risks
    ]]
    cascade_context: str | None           # How this risk connects to others


# ---------------------------------------------------------------------------
# LLM response model for chunk extraction (no UUID — assigned after)
# ---------------------------------------------------------------------------

class _LLMDocumentRiskMention(BaseModel):
    """LLM output for a single risk mention — UUIDs assigned post-extraction."""

    client_description: str
    verbatim_evidence: list[str]
    source_section: str
    risk_type: Literal["INHERENT", "EVENT_DRIVEN", "BOTH"]
    risk_category: str = "Unclassified"          # default — LLM often omits this
    severity_signal: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNSPECIFIED"] = "UNSPECIFIED"
    financial_quantification: str | None = None
    management_response: str | None = None
    flags: list[Literal[
        "REPEAT_FINDING", "MATERIAL_WEAKNESS", "SIGNIFICANT_DEFICIENCY",
        "UNMITIGATED", "ESCALATED", "QUANTIFIED", "FORWARD_LOOKING",
        "ALREADY_MATERIALIZED", "CASCADE_SIGNAL",
    ]] = []
    cascade_context: str | None = None


class _LLMDocumentParseResponse(BaseModel):
    """Wrapper for LLM chunk extraction response."""

    mentions: list[_LLMDocumentRiskMention]


# ---------------------------------------------------------------------------
# Deduplicated document risk — after merging across chunks
# ---------------------------------------------------------------------------

class DeduplicatedDocumentRisk(BaseModel):
    """A merged risk after cross-chunk deduplication.

    Uses DOC_RISK_NNN IDs to distinguish from CRO interview RISK_NNN IDs.
    """

    risk_id: str                          # DOC_RISK_001, DOC_RISK_002, ...
    client_description: str
    verbatim_evidence: list[str]          # Union of all evidence across chunks
    source_sections: list[str]            # All sections where this risk appeared
    chunk_ids: list[str]                  # All chunks that mentioned this risk
    risk_type: Literal["INHERENT", "EVENT_DRIVEN", "BOTH"]
    risk_category: str
    severity_signal: Literal["CRITICAL", "HIGH", "MEDIUM", "LOW", "UNSPECIFIED"]
    financial_quantification: str | None
    management_response: str | None
    flags: list[str]
    cascade_context: str | None
    merged_from: list[str]               # Original mention_ids (UUID strings)
    occurrence_count: int                 # How many chunks mentioned this risk

    @field_validator("risk_id", mode="after")
    @classmethod
    def _validate_risk_id(cls, v: str) -> str:
        if not re.match(r"^DOC_RISK_\d{3}$", v):
            raise ValueError(
                f"Invalid risk_id '{v}': must match DOC_RISK_NNN (e.g. DOC_RISK_001)"
            )
        return v


# ---------------------------------------------------------------------------
# Extraction run summary
# ---------------------------------------------------------------------------

class ExtractionSummary(BaseModel):
    """Summary statistics for a document extraction run."""

    document_name: str
    document_type: DocumentType
    total_chunks: int
    chunks_with_risks: int
    raw_mentions: int
    deduplicated_risks: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    unspecified_count: int
    material_weakness_count: int
    repeat_finding_count: int
    quantified_count: int
    failed_chunks: list[str]             # chunk_ids that failed extraction


# ---------------------------------------------------------------------------
# Full extraction result
# ---------------------------------------------------------------------------

class DocumentExtractionResult(BaseModel):
    """Complete output of a document extraction run."""

    risks: list[DeduplicatedDocumentRisk]
    summary: ExtractionSummary
    chunk_metadata: list[ChunkMetadata]
