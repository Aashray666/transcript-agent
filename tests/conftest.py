"""Shared pytest fixtures for the RiskMapper test suite."""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import chromadb
import pytest

from riskmapper.schemas import (
    DeduplicatedRisk,
    MappedRisk,
    RawRiskMention,
    RegistryMatch,
)


# ---------------------------------------------------------------------------
# Sample data fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_raw_mention() -> RawRiskMention:
    """A single valid RawRiskMention for testing."""
    return RawRiskMention(
        mention_id=uuid4(),
        client_description="Cybersecurity attacks on infrastructure",
        verbatim_evidence=["We are seeing significant increase in attacks"],
        question_source=["Q1", "Q3"],
        risk_type="INHERENT",
        flags=["CASCADE_SIGNAL"],
        cascade_context="Triggers network outage and regulatory scrutiny",
    )


@pytest.fixture
def sample_deduped_risk() -> DeduplicatedRisk:
    """A single valid DeduplicatedRisk for testing."""
    return DeduplicatedRisk(
        risk_id="RISK_001",
        client_description="Cybersecurity attacks on infrastructure",
        verbatim_evidence=[
            "We are seeing significant increase in attacks",
            "Cyber is inherent - full stop",
        ],
        question_source=["Q1", "Q3", "Q11"],
        risk_type="INHERENT",
        flags=["CASCADE_SIGNAL"],
        cascade_context="Triggers network outage and regulatory scrutiny",
        merged_from=[str(uuid4()), str(uuid4())],
    )


@pytest.fixture
def sample_registry_match() -> RegistryMatch:
    """A single valid RegistryMatch for testing."""
    return RegistryMatch(
        registry_risk_id="REG_TEL_036",
        risk_name="Increasing cyber attacks and security threats",
        primary_impact="Technology",
        confidence="HIGH",
        similarity_score=0.85,
    )


@pytest.fixture
def sample_mapped_risk(sample_registry_match: RegistryMatch) -> MappedRisk:
    """A single valid MappedRisk for testing."""
    return MappedRisk(
        risk_id="RISK_001",
        client_description="Cybersecurity attacks on infrastructure",
        verbatim_evidence=["We are seeing significant increase in attacks"],
        question_source=["Q1", "Q3"],
        risk_type="INHERENT",
        flags=["CASCADE_SIGNAL"],
        cascade_context="Triggers network outage",
        registry_matches=[sample_registry_match],
        unmapped=False,
        human_review=False,
        human_review_reason=None,
        cascade_links=["RISK_002", "RISK_003"],
    )


@pytest.fixture
def sample_unmapped_risk() -> MappedRisk:
    """A MappedRisk that is unmapped and needs human review."""
    return MappedRisk(
        risk_id="RISK_002",
        client_description="Free-to-use connectivity disruption",
        verbatim_evidence=["connectivity is bundled or subsidized by platforms"],
        question_source=["Q2", "Q14"],
        risk_type="EVENT_DRIVEN",
        flags=["UNREGISTERED"],
        registry_matches=[],
        unmapped=True,
        human_review=True,
        human_review_reason="No confident registry match found",
        cascade_links=[],
    )


# ---------------------------------------------------------------------------
# Infrastructure fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ephemeral_chroma() -> chromadb.ClientAPI:
    """An ephemeral (in-memory) ChromaDB client for testing."""
    return chromadb.EphemeralClient()


@pytest.fixture
def mock_llm() -> MagicMock:
    """A mocked LLMWrapper for testing without API calls."""
    mock = MagicMock()
    mock.model = "llama-3.3-70b-versatile"
    mock.api_key = "test-key"
    return mock


# ---------------------------------------------------------------------------
# Environment fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def set_groq_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set a fake GROQ_API_KEY in the environment."""
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key-12345")


@pytest.fixture
def unset_groq_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove GROQ_API_KEY from the environment."""
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
