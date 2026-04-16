"""Human review queue generator — filters unmapped risks for consultant review.

Writes risks that need human review to a JSON file with all context
needed for a consultant to evaluate them.
"""

from __future__ import annotations

import json
import logging
import os

from riskmapper.schemas import MappedRisk

logger = logging.getLogger(__name__)


def generate_review_queue(
    mapped_risks: list[MappedRisk],
    output_path: str,
) -> int:
    """Filter risks where human_review=True and write to JSON file.

    Args:
        mapped_risks: Full list of mapped risks from the registry mapper.
        output_path: File path for the output JSON.

    Returns:
        Count of risks in the review queue.
    """
    review_risks = [r for r in mapped_risks if r.human_review]

    # Ensure output directory exists
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    serialized = [r.model_dump(mode="json") for r in review_risks]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(serialized, f, indent=2, ensure_ascii=False)

    logger.info(
        "Human review queue written | count=%d | path=%s",
        len(review_risks), output_path,
    )

    return len(review_risks)
