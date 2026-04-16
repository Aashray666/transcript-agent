"""Hypothesis custom strategies for generating valid RiskMapper schema instances."""

from __future__ import annotations

from uuid import uuid4

from hypothesis import strategies as st

from riskmapper.schemas import (
    DeduplicatedRisk,
    MappedRisk,
    RawRiskMention,
    RegistryMatch,
)

# ---------------------------------------------------------------------------
# Atomic strategies
# ---------------------------------------------------------------------------

valid_question_source = st.sampled_from([f"Q{i}" for i in range(1, 16)])
valid_risk_type = st.sampled_from(["INHERENT", "EVENT_DRIVEN", "BOTH"])
valid_flag = st.sampled_from(["UNREGISTERED", "UNDERPREPARED", "CASCADE_SIGNAL"])
valid_flags = st.lists(valid_flag, max_size=3, unique=True)
valid_confidence = st.sampled_from(["HIGH", "MEDIUM", "LOW"])
valid_similarity = st.floats(
    min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False
)
valid_risk_id = st.integers(min_value=1, max_value=999).map(
    lambda n: f"RISK_{n:03d}"
)
valid_registry_risk_id = st.integers(min_value=1, max_value=999).map(
    lambda n: f"REG_TEL_{n:03d}"
)

# ---------------------------------------------------------------------------
# Composite strategies
# ---------------------------------------------------------------------------


@st.composite
def raw_risk_mention(draw: st.DrawFn) -> RawRiskMention:
    """Generate a valid RawRiskMention instance."""
    return RawRiskMention(
        mention_id=uuid4(),
        client_description=draw(st.text(min_size=1, max_size=100)),
        verbatim_evidence=draw(
            st.lists(st.text(min_size=1, max_size=80), min_size=1, max_size=3)
        ),
        question_source=draw(
            st.lists(valid_question_source, min_size=1, max_size=4, unique=True)
        ),
        risk_type=draw(valid_risk_type),
        flags=draw(valid_flags),
        cascade_context=draw(st.one_of(st.none(), st.text(min_size=1, max_size=80))),
    )


@st.composite
def registry_match(draw: st.DrawFn) -> RegistryMatch:
    """Generate a valid RegistryMatch instance."""
    return RegistryMatch(
        registry_risk_id=draw(valid_registry_risk_id),
        risk_name=draw(st.text(min_size=1, max_size=60)),
        primary_impact=draw(st.text(min_size=1, max_size=40)),
        confidence=draw(valid_confidence),
        similarity_score=draw(valid_similarity),
    )


@st.composite
def deduplicated_risk(draw: st.DrawFn) -> DeduplicatedRisk:
    """Generate a valid DeduplicatedRisk instance."""
    return DeduplicatedRisk(
        risk_id=draw(valid_risk_id),
        client_description=draw(st.text(min_size=1, max_size=100)),
        verbatim_evidence=draw(
            st.lists(st.text(min_size=1, max_size=80), min_size=1, max_size=5)
        ),
        question_source=draw(
            st.lists(valid_question_source, min_size=1, max_size=6, unique=True)
        ),
        risk_type=draw(valid_risk_type),
        flags=draw(valid_flags),
        cascade_context=draw(st.one_of(st.none(), st.text(min_size=1, max_size=80))),
        merged_from=draw(
            st.lists(st.uuids().map(str), min_size=1, max_size=4)
        ),
    )


@st.composite
def mapped_risk(draw: st.DrawFn) -> MappedRisk:
    """Generate a valid MappedRisk instance."""
    matches = draw(st.lists(registry_match(), min_size=0, max_size=3))
    is_unmapped = draw(st.booleans())
    is_review = is_unmapped or draw(st.booleans())

    return MappedRisk(
        risk_id=draw(valid_risk_id),
        client_description=draw(st.text(min_size=1, max_size=100)),
        verbatim_evidence=draw(
            st.lists(st.text(min_size=1, max_size=80), min_size=1, max_size=5)
        ),
        question_source=draw(
            st.lists(valid_question_source, min_size=1, max_size=6, unique=True)
        ),
        risk_type=draw(valid_risk_type),
        flags=draw(valid_flags),
        cascade_context=draw(st.one_of(st.none(), st.text(min_size=1, max_size=80))),
        registry_matches=matches,
        unmapped=is_unmapped,
        human_review=is_review,
        human_review_reason="Test reason" if is_review else None,
        cascade_links=draw(
            st.lists(valid_risk_id, max_size=3, unique=True)
        ),
    )
