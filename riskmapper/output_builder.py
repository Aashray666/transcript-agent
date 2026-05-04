"""Output builder — writes the final risk universe JSON files.

Produces risk_universe.json (full data) and risk_universe_summary.json
(counts and risk list).
"""

from __future__ import annotations

import json
import logging
import os

from riskmapper.schemas import MappedRisk

logger = logging.getLogger(__name__)


def build_output(
    mapped_risks: list[MappedRisk],
    output_dir: str,
) -> None:
    """Write risk_universe.json and risk_universe_summary.json.

    Args:
        mapped_risks: Final list of mapped risks.
        output_dir: Directory to write output files into (created if needed).
    """
    os.makedirs(output_dir, exist_ok=True)

    # --- risk_universe.json ---
    universe_path = os.path.join(output_dir, "risk_universe.json")
    serialized = [r.model_dump(mode="json") for r in mapped_risks]
    with open(universe_path, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2, ensure_ascii=False)

    # --- risk_universe_summary.json ---
    total = len(mapped_risks)
    mapped_count = sum(1 for r in mapped_risks if not r.unmapped)
    unmapped_count = sum(1 for r in mapped_risks if r.unmapped)
    review_count = sum(1 for r in mapped_risks if r.human_review)

    assert total == mapped_count + unmapped_count, (
        f"Invariant violated: total({total}) != "
        f"mapped({mapped_count}) + unmapped({unmapped_count})"
    )

    summary = {
        "total_risks": total,
        "mapped_count": mapped_count,
        "unmapped_count": unmapped_count,
        "human_review_count": review_count,
        "risks": [
            {
                "risk_id": r.risk_id,
                "client_description": r.client_description,
                "unmapped": r.unmapped,
                "registry_match_count": len(r.registry_matches),
            }
            for r in mapped_risks
        ],
    }

    summary_path = os.path.join(output_dir, "risk_universe_summary.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    logger.info(
        "Output written | total=%d | mapped=%d | unmapped=%d | review=%d | dir=%s",
        total, mapped_count, unmapped_count, review_count, output_dir,
    )
