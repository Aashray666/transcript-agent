"""Pydantic v2 data models and custom exceptions for the RiskMapper pipeline."""

from __future__ import annotations

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------
_QUESTION_SOURCE_RE = re.compile(r"^Q(1[0-9]|[1-9]|20)$")
_RISK_ID_RE = re.compile(r"^RISK_\d{3}$")


# ---------------------------------------------------------------------------
# Core schema models
# ---------------------------------------------------------------------------

class RawRiskMention(BaseModel):
    """A single risk mention extracted from a CRO interview transcript."""

    mention_id: UUID
    client_description: str
    verbatim_evidence: list[str]
    question_source: list[str]
    risk_type: Literal["INHERENT", "EVENT_DRIVEN", "BOTH"]
    flags: list[Literal["UNREGISTERED", "UNDERPREPARED", "CASCADE_SIGNAL"]]
    cascade_context: str | None = None

    @field_validator("question_source", mode="after")
    @classmethod
    def _validate_question_source(cls, v: list[str]) -> list[str]:
        for entry in v:
            if not _QUESTION_SOURCE_RE.match(entry):
                raise ValueError(
                    f"Invalid question_source '{entry}': must match Q1-Q15"
                )
        return v


class DeduplicatedRisk(BaseModel):
    """A merged risk after deduplication, with a sequential RISK_NNN id."""

    risk_id: str
    client_description: str
    verbatim_evidence: list[str]
    question_source: list[str]
    risk_type: Literal["INHERENT", "EVENT_DRIVEN", "BOTH"]
    flags: list[Literal["UNREGISTERED", "UNDERPREPARED", "CASCADE_SIGNAL"]]
    cascade_context: str | None = None
    merged_from: list[str]

    @field_validator("risk_id", mode="after")
    @classmethod
    def _validate_risk_id(cls, v: str) -> str:
        if not _RISK_ID_RE.match(v):
            raise ValueError(
                f"Invalid risk_id '{v}': must match pattern RISK_NNN (e.g. RISK_001)"
            )
        return v

    @field_validator("question_source", mode="after")
    @classmethod
    def _validate_question_source(cls, v: list[str]) -> list[str]:
        for entry in v:
            if not _QUESTION_SOURCE_RE.match(entry):
                raise ValueError(
                    f"Invalid question_source '{entry}': must match Q1-Q15"
                )
        return v


class RegistryMatch(BaseModel):
    """A single candidate match from the vector store."""

    registry_risk_id: str
    risk_name: str
    primary_impact: str
    confidence: Literal["HIGH", "MEDIUM", "LOW"]
    similarity_score: float

    @field_validator("similarity_score", mode="after")
    @classmethod
    def _validate_similarity_score(cls, v: float) -> float:
        if v < 0.0 or v > 1.0:
            raise ValueError(
                f"Invalid similarity_score {v}: must be between 0.0 and 1.0"
            )
        return v


class MappedRisk(BaseModel):
    """A fully processed risk with registry matches and review metadata."""

    risk_id: str
    client_description: str
    verbatim_evidence: list[str]
    question_source: list[str]
    risk_type: Literal["INHERENT", "EVENT_DRIVEN", "BOTH"]
    flags: list[Literal["UNREGISTERED", "UNDERPREPARED", "CASCADE_SIGNAL"]]
    cascade_context: str | None = None
    registry_matches: list[RegistryMatch]
    unmapped: bool
    human_review: bool
    human_review_reason: str | None = None
    cascade_links: list[str]


# ---------------------------------------------------------------------------
# Wrapper / response models
# ---------------------------------------------------------------------------

class TranscriptParseResponse(BaseModel):
    """Wrapper for the LLM transcript parsing response."""

    mentions: list[RawRiskMention]


class _LLMRiskMention(BaseModel):
    """Intermediate model for LLM output — no UUID requirement.

    The transcript parser assigns proper UUIDs after receiving this.
    """

    client_description: str
    verbatim_evidence: list[str]
    question_source: list[str]
    risk_type: Literal["INHERENT", "EVENT_DRIVEN", "BOTH"]
    flags: list[Literal["UNREGISTERED", "UNDERPREPARED", "CASCADE_SIGNAL"]]
    cascade_context: str | None = None


class _LLMTranscriptParseResponse(BaseModel):
    """Wrapper for the raw LLM transcript parsing response."""

    mentions: list[_LLMRiskMention]


class DeduplicationResponse(BaseModel):
    """Wrapper for the LLM deduplication response."""

    risks: list[DeduplicatedRisk]


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class LLMCallError(Exception):
    """Raised when an LLM call fails after all retries.

    Does not expose raw Gemini API details.
    """


class RegistryLoadError(Exception):
    """Raised when registry loading fails due to file or sheet issues."""


class PipelineError(Exception):
    """Raised when a critical pipeline step fails."""
