"""Transcript preprocessor — strips interviewer lines and structural noise.

Handles multiple transcript formats:
- Plain text (Priya:, Rajiv:)
- Markdown bold (**Priya:**, **Sanjay:**)
- Q-number headers in various formats (Q1 -, **Q1., Q1:)
"""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

# Patterns for interviewer names (add more as needed)
_INTERVIEWER_PATTERNS = [
    re.compile(r"^\*{0,2}Priya\*{0,2}\s*:"),
    re.compile(r"^Priya\s*:"),
]

# Pattern for Q-number headers in any format
_Q_HEADER_RE = re.compile(r"^\*{0,2}Q(\d+)[\.\s\-]")

# Patterns for structural noise
_NOISE_PATTERNS = [
    re.compile(r"^={3,}$"),           # === dividers
    re.compile(r"^-{3,}$"),           # --- dividers
    re.compile(r"^\*{3,}$"),          # *** dividers
    re.compile(r"^#{1,3}\s"),         # ### headers
    re.compile(r"^END OF TRANSCRIPT", re.IGNORECASE),
    re.compile(r"^TRANSCRIPT$", re.IGNORECASE),
]


def preprocess_transcript(raw_text: str) -> str:
    """Strip interviewer lines, headers, and structural noise.

    Keeps CRO responses with Q-number section markers intact.
    Works with both plain text and markdown-formatted transcripts.

    Args:
        raw_text: The full raw transcript text.

    Returns:
        Cleaned transcript with only CRO responses and Q headers.
    """
    # Strip markdown bold markers globally for cleaner processing
    text = raw_text.replace("**", "")

    lines = text.split("\n")
    output_lines: list[str] = []
    in_preamble = True

    for line in lines:
        stripped = line.strip()

        if not stripped:
            continue

        # Skip structural noise
        if any(p.match(stripped) for p in _NOISE_PATTERNS):
            continue

        # Detect Q-number headers
        q_match = _Q_HEADER_RE.match(stripped)

        # Skip preamble (everything before Q1)
        if in_preamble:
            if q_match:
                in_preamble = False
                output_lines.append("")
                # Normalize header format
                q_num = q_match.group(1)
                output_lines.append(f"Q{q_num} - {stripped[q_match.end():]}")
            continue

        # Keep Q-number headers (normalized)
        if q_match:
            q_num = q_match.group(1)
            output_lines.append("")
            output_lines.append(f"Q{q_num} - {stripped[q_match.end():]}")
            continue

        # Skip interviewer lines
        if any(p.match(stripped) for p in _INTERVIEWER_PATTERNS):
            continue

        # Strip CRO name prefix if present (any name followed by colon)
        cro_match = re.match(r"^[A-Z][a-z]+\s*:\s*", stripped)
        if cro_match:
            output_lines.append(stripped[cro_match.end():])
            continue

        # Keep continuation lines
        output_lines.append(stripped)

    result = "\n".join(output_lines).strip()

    logger.info(
        "Transcript preprocessed | raw_chars=%d | clean_chars=%d | reduction=%.0f%%",
        len(raw_text), len(result),
        (1 - len(result) / len(raw_text)) * 100 if raw_text else 0,
    )

    return result
