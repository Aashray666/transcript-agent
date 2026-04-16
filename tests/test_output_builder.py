"""Property tests P8, P9 + unit tests for output_builder.py."""

from __future__ import annotations

import json
import os

from hypothesis import given, settings
from hypothesis import strategies as st

from riskmapper.output_builder import build_output
from riskmapper.schemas import MappedRisk
from tests.strategies import mapped_risk


# Feature: riskmapper-agent-system, Property 8: Output file round-trip
class TestOutputRoundTrip:
    """Writing then reading risk_universe.json produces equal objects."""

    @given(st.lists(mapped_risk(), min_size=1, max_size=8))
    @settings(max_examples=100)
    def test_risk_universe_round_trip(
        self, risks: list[MappedRisk],
    ) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            build_output(risks, td)

            with open(os.path.join(td, "risk_universe.json"), "r", encoding="utf-8") as f:
                data = json.load(f)

            restored = [MappedRisk.model_validate(r) for r in data]
            assert len(restored) == len(risks)
            for orig, rest in zip(risks, restored):
                assert orig.risk_id == rest.risk_id
                assert orig.unmapped == rest.unmapped
                assert orig.client_description == rest.client_description


# Feature: riskmapper-agent-system, Property 9: Summary count invariant
class TestSummaryCountInvariant:
    """total_risks == mapped_count + unmapped_count, always."""

    @given(st.lists(mapped_risk(), min_size=0, max_size=10))
    @settings(max_examples=100)
    def test_summary_counts(
        self, risks: list[MappedRisk],
    ) -> None:
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            build_output(risks, td)

            with open(os.path.join(td, "risk_universe_summary.json"), "r", encoding="utf-8") as f:
                summary = json.load(f)

            assert summary["total_risks"] == len(risks)
            assert summary["total_risks"] == summary["mapped_count"] + summary["unmapped_count"]
            assert summary["mapped_count"] == sum(1 for r in risks if not r.unmapped)
            assert summary["unmapped_count"] == sum(1 for r in risks if r.unmapped)
            assert summary["human_review_count"] == sum(1 for r in risks if r.human_review)


class TestOutputBuilderUnit:
    """Unit tests for output builder."""

    def test_creates_directory(self, tmp_path) -> None:
        out_dir = str(tmp_path / "nested" / "deep" / "output")
        build_output([], out_dir)
        assert os.path.isdir(out_dir)
        assert os.path.isfile(os.path.join(out_dir, "risk_universe.json"))
        assert os.path.isfile(os.path.join(out_dir, "risk_universe_summary.json"))

    def test_empty_input(self, tmp_path) -> None:
        out_dir = str(tmp_path / "out")
        build_output([], out_dir)
        with open(os.path.join(out_dir, "risk_universe_summary.json"), encoding="utf-8") as f:
            s = json.load(f)
        assert s["total_risks"] == 0
        assert s["mapped_count"] == 0
        assert s["unmapped_count"] == 0
