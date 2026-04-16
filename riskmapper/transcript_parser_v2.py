"""V2 Transcript parser — per-question chunks with tight prompts.

Splits preprocessed transcript by individual questions. Each Q section
is small enough to fit within Groq's TPM limits. Better prompts prevent
bundling and cascade-as-risk issues.
"""

from __future__ import annotations

import logging
import re
from uuid import uuid4

from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.schemas import RawRiskMention, _LLMTranscriptParseResponse
from riskmapper.transcript_preprocessor import preprocess_transcript

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are an ERM risk extraction analyst. Extract every distinct risk from this \
CRO interview transcript section.

STRICT RULES:
1. ONE risk per entry. Never bundle multiple risks into one entry.
   BAD: "AI governance, electronic waste, and business model disruption"
   GOOD: Three separate entries — one for each.

2. Cascade descriptions (Q12/Q13) are NOT separate risks. Tag CASCADE_SIGNAL \
on the originating risk and describe the pathway in cascade_context.
   BAD: Creating a risk called "cascade of cyber and network outage"
   GOOD: Tag the cyber risk with CASCADE_SIGNAL and cascade_context.

3. risk_type: INHERENT (Q3/permanent), EVENT_DRIVEN (Q4/external), BOTH.
4. Flags: UNREGISTERED (Q2/Q14), UNDERPREPARED (Q15), CASCADE_SIGNAL (Q12/Q13).
5. verbatim_evidence: 1-3 direct quotes the client actually said.
6. Do NOT hallucinate. Every risk must be grounded in what the client said.
"""


def _split_by_question(clean_text: str) -> list[tuple[str, str]]:
    """Split preprocessed transcript into per-question chunks."""
    parts = re.split(r"(?=Q\d+\s*-)", clean_text)
    chunks = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        q_match = re.match(r"(Q\d+)\s*-", part)
        if q_match:
            q_label = q_match.group(1)
            chunks.append((q_label, part))
    return chunks


def parse_transcript_v2(
    transcript_text: str,
    sector: str,
    llm: LLMWrapper,
    preprocess: bool = True,
) -> list[RawRiskMention]:
    """Extract risk mentions using per-question chunks.

    Args:
        transcript_text: Raw or preprocessed transcript.
        sector: Client sector.
        llm: LLMWrapper instance.
        preprocess: If True, strip interviewer lines first.

    Returns:
        List of RawRiskMention with assigned UUIDs.

    Raises:
        ValueError: If zero mentions extracted.
    """
    if preprocess:
        clean = preprocess_transcript(transcript_text)
    else:
        clean = transcript_text

    chunks = _split_by_question(clean)
    logger.info(
        "V2 parsing | sector=%s | questions=%d | clean_chars=%d",
        sector, len(chunks), len(clean),
    )

    all_mentions: list[RawRiskMention] = []

    for idx, (q_label, chunk_text) in enumerate(chunks, 1):
        prompt = (
            f"CLIENT SECTOR: {sector}\n"
            f"QUESTION: {q_label}\n\n"
            f"TRANSCRIPT:\n{chunk_text}\n\n"
            "Extract ALL distinct risk mentions from this question. "
            "Return JSON with 'mentions' key. "
            "If no risks mentioned, return empty list."
        )

        try:
            response = llm.call(
                prompt=prompt,
                response_model=_LLMTranscriptParseResponse,
                temperature=0.0,
                step_name=f"parse_v2_{q_label}",
                system_prompt=_SYSTEM_PROMPT,
            )

            for m in response.mentions:
                all_mentions.append(
                    RawRiskMention(
                        mention_id=uuid4(),
                        client_description=m.client_description,
                        verbatim_evidence=m.verbatim_evidence,
                        question_source=m.question_source,
                        risk_type=m.risk_type,
                        flags=m.flags,
                        cascade_context=m.cascade_context,
                    )
                )

            logger.info(
                "%s | mentions=%d | total=%d",
                q_label, len(response.mentions), len(all_mentions),
            )
        except Exception as exc:
            logger.warning("%s failed: %s — skipping", q_label, exc)

    if len(all_mentions) == 0:
        raise ValueError(
            "No risk mentions extracted from transcript. Check transcript format."
        )

    logger.info("V2 parsed | total=%d | sector=%s", len(all_mentions), sector)
    return all_mentions
