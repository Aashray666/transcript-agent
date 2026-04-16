"""Property test P7 + unit tests for human_review_queue.py."""

from __future__ import annotations

import json
import os

from hypothesis import given, settings
from hypothesis import strategies as st

from riskmapper.human_review_queue import generate_review_queue
from riskmapper.schemas import MappedRisk
from tests.strategies import mapped_risk


# Feature: riskmapper-agent-system, Property 7: Human review queue filtering
class TestReviewQueueFiltering:
    """Queue contains exactly the risks with human_review=True."""

    @given(st.lists(mapped_risk(), min_size=0, max_size=10))
    @settings(max_examples=100)
    def test_queue_contains_exactly_review_risks(
        self, risks: list[MappedRisk],
    ) -> None:
        import tempfile, os
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "review.json")
            count = generate_review_queue(risks, path)

            expected = [r for r in risks if r.human_review]
            assert count == len(expected)

            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            assert len(data) == len(expected)

            for item, orig in zip(data, expected):
                parsed = MappedRisk.model_validate(item)
                assert parsed.risk_id == orig.risk_id
                assert parsed.human_review is True


class TestReviewQueueUnit:
    """Unit tests for edge cases."""

    def test_empty_input_writes_empty_array(self, tmp_path) -> None:
        path = str(tmp_path / "review.json")
        count = generate_review_queue([], path)
        assert count == 0
        with open(path, encoding="utf-8") as f:
            assert json.load(f) == []

    def test_reason_preserved(self, sample_unmapped_risk, tmp_path) -> None:
        path = str(tmp_path / "review.json")
        generate_review_queue([sample_unmapped_risk], path)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert data[0]["human_review_reason"] == "No confident registry match found"
