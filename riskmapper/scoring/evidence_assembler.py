"""Evidence assembly for risk scoring — NOT a separate LLM agent.

Per architecture critique: the evidence is ALREADY extracted in Phase 1.
This module assembles it into a structured EvidenceContext for the Scoring
Agent. It's a data assembly function, not an intelligent agent.
"""

from __future__ import annotations

import logging
import re

from riskmapper.schemas import MappedRisk
from riskmapper.scoring.schemas import EvidenceContext

logger = logging.getLogger(__name__)


def assemble_evidence(
    risk: MappedRisk,
    transcript_text: str,
    all_risks: list[MappedRisk],
) -> EvidenceContext:
    """Build an EvidenceContext from Phase 1 data for a single risk.

    Args:
        risk: The MappedRisk from Phase 1 output.
        transcript_text: Full interview transcript for surrounding context.
        all_risks: All risks in the universe (for cross-references).

    Returns:
        Structured EvidenceContext ready for the Scoring Agent.
    """
    surrounding = _extract_surrounding_context(
        risk.verbatim_evidence, transcript_text
    )
    cross_refs = _find_cross_risk_references(risk, all_risks)
    strength = _assess_evidence_strength(risk)

    return EvidenceContext(
        risk_id=risk.risk_id,
        client_description=risk.client_description,
        verbatim_quotes=risk.verbatim_evidence,
        question_sources=risk.question_source,
        surrounding_context=surrounding,
        cascade_evidence=risk.cascade_context,
        cross_risk_references=cross_refs,
        evidence_strength=strength,
        risk_type=risk.risk_type,
        flags=risk.flags,
    )


def _extract_surrounding_context(
    verbatim_quotes: list[str],
    transcript_text: str,
    context_sentences: int = 2,
) -> list[str]:
    """For each verbatim quote, extract ±N surrounding sentences.

    This captures nuance that the Phase 1 extraction may have trimmed.
    """
    if not transcript_text or not verbatim_quotes:
        return []

    # Split transcript into sentences (rough but effective)
    sentences = re.split(r'(?<=[.!?])\s+', transcript_text)
    surrounding: list[str] = []

    for quote in verbatim_quotes:
        # Find the sentence that best matches this quote
        best_idx = -1
        best_overlap = 0
        quote_lower = quote.lower().strip()

        for i, sent in enumerate(sentences):
            sent_lower = sent.lower().strip()
            # Check substring containment or significant word overlap
            if quote_lower[:50] in sent_lower or sent_lower in quote_lower:
                best_idx = i
                break
            # Fallback: word overlap
            quote_words = set(quote_lower.split())
            sent_words = set(sent_lower.split())
            overlap = len(quote_words & sent_words)
            if overlap > best_overlap and overlap >= len(quote_words) * 0.5:
                best_overlap = overlap
                best_idx = i

        if best_idx >= 0:
            start = max(0, best_idx - context_sentences)
            end = min(len(sentences), best_idx + context_sentences + 1)
            context_block = " ".join(sentences[start:end]).strip()
            if context_block and context_block not in surrounding:
                surrounding.append(context_block)

    return surrounding


def _find_cross_risk_references(
    risk: MappedRisk,
    all_risks: list[MappedRisk],
) -> list[str]:
    """Find other risks that share themes with this risk.

    Checks for: shared cascade_links, overlapping question_sources,
    and keyword overlap in descriptions.
    """
    refs: list[str] = []

    for other in all_risks:
        if other.risk_id == risk.risk_id:
            continue

        # Shared cascade links
        if risk.cascade_links and other.risk_id in risk.cascade_links:
            if other.risk_id not in refs:
                refs.append(other.risk_id)
            continue

        if other.cascade_links and risk.risk_id in other.cascade_links:
            if other.risk_id not in refs:
                refs.append(other.risk_id)
            continue

        # Overlapping question sources (same interview section)
        shared_qs = set(risk.question_source) & set(other.question_source)
        if len(shared_qs) >= 2:
            if other.risk_id not in refs:
                refs.append(other.risk_id)
            continue

        # Keyword overlap in descriptions
        risk_words = set(risk.client_description.lower().split())
        other_words = set(other.client_description.lower().split())
        # Remove common stop words
        stop = {"and", "the", "of", "in", "to", "a", "is", "for", "risk", "on"}
        risk_words -= stop
        other_words -= stop
        if risk_words and other_words:
            overlap = len(risk_words & other_words)
            if overlap >= 1 and overlap / min(len(risk_words), len(other_words)) >= 0.3:
                if other.risk_id not in refs:
                    refs.append(other.risk_id)

    return refs


def _assess_evidence_strength(risk: MappedRisk) -> str:
    """Rate evidence strength based on quantity and quality.

    STRONG: 3+ verbatim quotes from 2+ questions
    MODERATE: 2+ quotes or 2+ question sources
    WEAK: 1 quote from 1 question
    """
    n_quotes = len(risk.verbatim_evidence)
    n_sources = len(risk.question_source)

    if n_quotes >= 3 and n_sources >= 2:
        return "STRONG"
    elif n_quotes >= 2 or n_sources >= 2:
        return "MODERATE"
    else:
        return "WEAK"
