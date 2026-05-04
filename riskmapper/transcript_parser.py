"""Transcript parser — extracts structured risk mentions from a CRO interview.

Uses the LLM to parse a transcript and produce a list of RawRiskMention
objects, each tagged with question source, risk type, flags, and verbatim
evidence. Splits the transcript into question-based chunks to stay within
LLM context limits.
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
You are an expert ERM (Enterprise Risk Management) analyst. Your job is to \
process a guided interview transcript between a risk advisory consultant and \
a client's Chief Risk Officer and extract every distinct risk the client \
mentions.

RULES:
1. Extract each risk as a SEPARATE item — do not bundle multiple risks.
2. For each risk, preserve the client's own language in client_description.
3. Tag question_source with every Q number (Q1-Q15) where the risk appeared.
4. Classify risk_type:
   - INHERENT if mentioned in Q3 or described as permanent/structural
   - EVENT_DRIVEN if mentioned in Q4 or described as externally triggered
   - BOTH if it appears in both contexts
5. Assign flags:
   - UNREGISTERED if the client said it's not on their formal register (Q2, Q14)
   - UNDERPREPARED if the client said they are underprepared for it (Q15)
   - CASCADE_SIGNAL if the client described it triggering or being triggered \
by other risks (Q12, Q13)
6. Include 1-3 verbatim quotes from the transcript as evidence.
7. If the risk has cascade context, describe the cascade pathway.
8. Do NOT hallucinate — every risk must be grounded in what the client said.
9. Do NOT summarize — extract discrete risks, not themes.
"""


def _split_transcript_into_chunks(transcript_text: str) -> list[str]:
    """Split transcript into chunks by question sections.

    Groups questions into manageable chunks to stay within LLM limits.
    Works with preprocessed transcripts (normalized Q headers).
    """
    # Split on normalized Q-number headers (from preprocessor)
    pattern = r"(\nQ\d+\s*-)"
    parts = re.split(pattern, transcript_text)

    # Reassemble: first part is preamble, then pairs of (header, body)
    chunks: list[str] = []
    current_chunk = parts[0]  # preamble

    for i in range(1, len(parts), 2):
        header = parts[i] if i < len(parts) else ""
        body = parts[i + 1] if i + 1 < len(parts) else ""
        section = header + body

        # If adding this section would make the chunk too large, flush
        if len(current_chunk) + len(section) > 2000:
            if current_chunk.strip():
                chunks.append(current_chunk)
            current_chunk = section
        else:
            current_chunk += section

    if current_chunk.strip():
        chunks.append(current_chunk)

    return chunks


def parse_transcript(
    transcript_text: str,
    sector: str,
    llm: LLMWrapper,
) -> list[RawRiskMention]:
    """Extract risk mentions from a transcript using the LLM.

    Splits the transcript into chunks and processes each separately,
    then combines all mentions.

    Args:
        transcript_text: The full interview transcript as plain text.
        sector: The client's industry sector (e.g. "Telecommunication").
        llm: An initialised LLMWrapper instance.

    Returns:
        A list of RawRiskMention objects with assigned UUIDs.

    Raises:
        ValueError: If zero risk mentions are extracted.
    """
    logger.info(
        "Parsing transcript | sector=%s | length=%d chars",
        sector, len(transcript_text),
    )

    # Preprocess: strip interviewer lines, normalize Q headers
    clean_text = preprocess_transcript(transcript_text)

    chunks = _split_transcript_into_chunks(clean_text)
    logger.info("Split transcript into %d chunks", len(chunks))

    all_mentions: list[RawRiskMention] = []

    for chunk_idx, chunk in enumerate(chunks, 1):
        prompt = (
            f"CLIENT SECTOR: {sector}\n\n"
            f"TRANSCRIPT SECTION (part {chunk_idx} of {len(chunks)}):\n"
            f"{chunk}\n\n"
            "Extract ALL distinct risk mentions from this transcript section. "
            "Return them as a JSON object with a 'mentions' key containing "
            "a list of risk mention objects. If no risks are mentioned in "
            "this section, return an empty list."
        )

        try:
            response = llm.call(
                prompt=prompt,
                response_model=_LLMTranscriptParseResponse,
                temperature=0.0,
                step_name=f"transcript_parsing_chunk_{chunk_idx}",
                system_prompt=_SYSTEM_PROMPT,
            )
        except Exception as exc:
            logger.warning(
                "Chunk %d/%d failed: %s — skipping",
                chunk_idx, len(chunks), exc,
            )
            continue

        for llm_mention in response.mentions:
            all_mentions.append(
                RawRiskMention(
                    mention_id=uuid4(),
                    client_description=llm_mention.client_description,
                    verbatim_evidence=llm_mention.verbatim_evidence,
                    question_source=llm_mention.question_source,
                    risk_type=llm_mention.risk_type,
                    flags=llm_mention.flags,
                    cascade_context=llm_mention.cascade_context,
                )
            )

        logger.info(
            "Chunk %d/%d parsed | mentions_in_chunk=%d | total_so_far=%d",
            chunk_idx, len(chunks), len(response.mentions), len(all_mentions),
        )

    if len(all_mentions) == 0:
        raise ValueError(
            "No risk mentions extracted from transcript. "
            "Check transcript format."
        )

    logger.info(
        "Transcript parsed | total_mentions=%d | sector=%s",
        len(all_mentions), sector,
    )

    return all_mentions
