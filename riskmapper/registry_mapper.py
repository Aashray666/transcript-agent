"""Registry mapper — matches deduplicated risks against the ChromaDB registry.

For each risk, queries ChromaDB for top-3 candidates, then uses the LLM
to evaluate confidence. Marks risks as unmapped when confidence is LOW
and similarity < 0.75.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel

from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.schemas import (
    DeduplicatedRisk,
    LLMCallError,
    MappedRisk,
    RegistryMatch,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# LLM response model for confidence evaluation
# ---------------------------------------------------------------------------

class _CandidateEval(BaseModel):
    """LLM evaluation of a single registry candidate."""
    registry_risk_id: str
    confidence: Literal["HIGH", "MEDIUM", "LOW"]


class _MappingLLMResponse(BaseModel):
    """LLM response for mapping evaluation."""
    evaluations: list[_CandidateEval]


_SYSTEM_PROMPT = """\
You are an expert ERM registry mapping analyst. You will receive a client's \
risk description and 3 candidate matches from a risk registry.

Your job: evaluate how well each candidate matches the client's risk.

Assign confidence:
- HIGH: Clear semantic match — the registry entry describes the same risk.
- MEDIUM: Likely match but some ambiguity — related but not exact.
- LOW: Weak or speculative match — different risk or very tangential.

RULES:
- Evaluate each candidate independently.
- Consider the sector context when judging matches.
- A risk about "cyber attacks" should match "Increasing cyber attacks" as HIGH.
- A risk about "energy costs" should NOT match "cybersecurity" — that's LOW.
- Return an evaluation for every candidate provided.
"""


def map_risks(
    risks: list[DeduplicatedRisk],
    sector: str,
    chroma_client,
    llm: LLMWrapper,
) -> list[MappedRisk]:
    """Map deduplicated risks to registry entries via ChromaDB + LLM.

    Args:
        risks: Deduplicated risk list.
        sector: Client sector for LLM context.
        chroma_client: ChromaDB client with loaded registry.
        llm: Initialised LLMWrapper.

    Returns:
        List of MappedRisk objects.

    Raises:
        RuntimeError: If the risk_registry collection is empty.
    """
    try:
        collection = chroma_client.get_collection("risk_registry")
    except Exception:
        raise RuntimeError(
            "Risk registry not loaded. Run risk_registry_loader first."
        )

    if collection.count() == 0:
        raise RuntimeError(
            "Risk registry not loaded. Run risk_registry_loader first."
        )

    mapped: list[MappedRisk] = []

    for risk in risks:
        try:
            mapped_risk = _map_single_risk(risk, sector, collection, llm)
            mapped.append(mapped_risk)
        except Exception as exc:
            logger.error(
                "Mapping failed for %s: %s — marking for human review",
                risk.risk_id, exc,
            )
            mapped.append(
                MappedRisk(
                    risk_id=risk.risk_id,
                    client_description=risk.client_description,
                    verbatim_evidence=risk.verbatim_evidence,
                    question_source=risk.question_source,
                    risk_type=risk.risk_type,
                    flags=risk.flags,
                    cascade_context=risk.cascade_context,
                    registry_matches=[],
                    unmapped=True,
                    human_review=True,
                    human_review_reason=f"Mapping pipeline error: {exc}",
                    cascade_links=[],
                )
            )

    logger.info(
        "Registry mapping complete | total=%d | unmapped=%d",
        len(mapped), sum(1 for r in mapped if r.unmapped),
    )

    return mapped


def _map_single_risk(
    risk: DeduplicatedRisk,
    sector: str,
    collection,
    llm: LLMWrapper,
) -> MappedRisk:
    """Map a single risk against the registry collection."""

    # Query ChromaDB for top 3 candidates
    results = collection.query(
        query_texts=[risk.client_description],
        n_results=3,
        include=["documents", "metadatas", "distances"],
    )

    candidates = []
    for i in range(len(results["ids"][0])):
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        # ChromaDB cosine distance → similarity = 1 - distance
        similarity = max(0.0, min(1.0, 1.0 - distance))
        candidates.append({
            "registry_risk_id": meta["registry_risk_id"],
            "risk_name": meta["risk_name"],
            "primary_impact": meta["primary_impact"],
            "document": results["documents"][0][i],
            "similarity_score": round(similarity, 4),
        })

    # Ask LLM to evaluate confidence for each candidate
    candidate_text = "\n".join(
        f"  {c['registry_risk_id']}: {c['document']} (similarity: {c['similarity_score']:.2f})"
        for c in candidates
    )

    prompt = (
        f"SECTOR: {sector}\n\n"
        f"CLIENT RISK: {risk.client_description}\n\n"
        f"REGISTRY CANDIDATES:\n{candidate_text}\n\n"
        f"Evaluate each candidate's match confidence (HIGH/MEDIUM/LOW)."
    )

    eval_response = llm.call(
        prompt=prompt,
        response_model=_MappingLLMResponse,
        temperature=0.0,
        step_name=f"registry_mapping_{risk.risk_id}",
        system_prompt=_SYSTEM_PROMPT,
    )

    # Build RegistryMatch objects
    eval_map = {e.registry_risk_id: e.confidence for e in eval_response.evaluations}

    registry_matches: list[RegistryMatch] = []
    for c in candidates:
        confidence = eval_map.get(c["registry_risk_id"], "LOW")
        registry_matches.append(
            RegistryMatch(
                registry_risk_id=c["registry_risk_id"],
                risk_name=c["risk_name"],
                primary_impact=c["primary_impact"],
                confidence=confidence,
                similarity_score=c["similarity_score"],
            )
        )

    # Determine unmapped status
    best_confidence = _best_confidence(registry_matches)
    best_similarity = max((m.similarity_score for m in registry_matches), default=0.0)
    is_unmapped = best_confidence == "LOW" and best_similarity < 0.75

    return MappedRisk(
        risk_id=risk.risk_id,
        client_description=risk.client_description,
        verbatim_evidence=risk.verbatim_evidence,
        question_source=risk.question_source,
        risk_type=risk.risk_type,
        flags=risk.flags,
        cascade_context=risk.cascade_context,
        registry_matches=registry_matches,
        unmapped=is_unmapped,
        human_review=is_unmapped,
        human_review_reason="No confident registry match found" if is_unmapped else None,
        cascade_links=[],
    )


def _best_confidence(matches: list[RegistryMatch]) -> str:
    """Return the highest confidence level among matches."""
    rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    if not matches:
        return "LOW"
    return max(matches, key=lambda m: rank.get(m.confidence, 0)).confidence
