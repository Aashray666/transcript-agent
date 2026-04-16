"""Property tests P1 and P2 + unit tests for schemas.py."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from pydantic import ValidationError

from riskmapper.schemas import (
    DeduplicatedRisk,
    MappedRisk,
    RawRiskMention,
    RegistryMatch,
)
from tests.strategies import (
    deduplicated_risk,
    mapped_risk,
    raw_risk_mention,
    registry_match,
)


# Feature: riskmapper-agent-system, Property 1: Schema round-trip serialization
class TestSchemaRoundTrip:
    """For any valid instance, serialize → deserialize produces equal object."""

    @given(raw_risk_mention())
    @settings(max_examples=100)
    def test_raw_risk_mention_round_trip(self, mention: RawRiskMention) -> None:
        json_str = mention.model_dump_json()
        restored = RawRiskMention.model_validate_json(json_str)
        assert mention == restored

    @given(deduplicated_risk())
    @settings(max_examples=100)
    def test_deduplicated_risk_round_trip(self, risk: DeduplicatedRisk) -> None:
        json_str = risk.model_dump_json()
        restored = DeduplicatedRisk.model_validate_json(json_str)
        assert risk == restored

    @given(registry_match())
    @settings(max_examples=100)
    def test_registry_match_round_trip(self, match: RegistryMatch) -> None:
        json_str = match.model_dump_json()
        restored = RegistryMatch.model_validate_json(json_str)
        assert match == restored

    @given(mapped_risk())
    @settings(max_examples=100)
    def test_mapped_risk_round_trip(self, risk: MappedRisk) -> None:
        json_str = risk.model_dump_json()
        restored = MappedRisk.model_validate_json(json_str)
        assert risk == restored


# Feature: riskmapper-agent-system, Property 2: Schema validation rejects invalid data
class TestSchemaValidationRejects:
    """Invalid field values must raise ValidationError."""

    def test_similarity_score_above_1(self) -> None:
        with pytest.raises(ValidationError):
            RegistryMatch(
                registry_risk_id="REG_001", risk_name="x",
                primary_impact="x", confidence="HIGH", similarity_score=1.5,
            )

    def test_similarity_score_below_0(self) -> None:
        with pytest.raises(ValidationError):
            RegistryMatch(
                registry_risk_id="REG_001", risk_name="x",
                primary_impact="x", confidence="HIGH", similarity_score=-0.1,
            )

    def test_invalid_risk_id_pattern(self) -> None:
        with pytest.raises(ValidationError):
            DeduplicatedRisk(
                risk_id="BAD_ID", client_description="x",
                verbatim_evidence=["x"], question_source=["Q1"],
                risk_type="INHERENT", flags=[], merged_from=["x"],
            )

    def test_invalid_question_source(self) -> None:
        from uuid import uuid4
        with pytest.raises(ValidationError):
            RawRiskMention(
                mention_id=uuid4(), client_description="x",
                verbatim_evidence=["x"], question_source=["Q99"],
                risk_type="INHERENT", flags=[],
            )

    def test_invalid_risk_type(self) -> None:
        from uuid import uuid4
        with pytest.raises(ValidationError):
            RawRiskMention(
                mention_id=uuid4(), client_description="x",
                verbatim_evidence=["x"], question_source=["Q1"],
                risk_type="UNKNOWN", flags=[],
            )

    def test_invalid_flag(self) -> None:
        from uuid import uuid4
        with pytest.raises(ValidationError):
            RawRiskMention(
                mention_id=uuid4(), client_description="x",
                verbatim_evidence=["x"], question_source=["Q1"],
                risk_type="INHERENT", flags=["INVALID_FLAG"],
            )
