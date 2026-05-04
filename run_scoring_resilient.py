"""Resilient scoring pipeline — writes each risk immediately, resumes on restart.

Features:
- Writes each scored risk to disk as soon as it completes
- On restart, skips already-scored risks (resume from where it left off)
- Conservative rate limiting (5s between calls) to avoid TPM issues
- Graceful error handling per risk — never crashes the whole pipeline
- Final report generated from all scored risks on disk
"""

import json
import logging
import os
import sys
import time
import traceback

from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.schemas import MappedRisk
from riskmapper.scoring.cascade_scorer import apply_cascade_adjustments
from riskmapper.scoring.consistency_checker import check_consistency
from riskmapper.scoring.evidence_assembler import assemble_evidence
from riskmapper.scoring.external_intelligence import gather_external_intelligence
from riskmapper.scoring.knowledge_summarizer import extract_company_profile, summarize_knowledge
from riskmapper.scoring.likelihood_intelligence import assess_likelihood
from riskmapper.scoring.memory_store import MemoryStore
from riskmapper.scoring.schemas import ScoredRisk, ScoringPipelineSummary, ScoringPipelineResult
from riskmapper.scoring.scoring_agent import load_impact_table_text, score_risk
from riskmapper.scoring.scoring_pipeline import _write_outputs, _build_summary

OUTPUT_DIR = "output_auto_scored_v2"

# Set to True to score asset risks (data/risk_universe_auto.json mapped with client evidence)
# Set to False to score client-extracted risks (output_auto/risk_universe.json)
SCORE_ASSET_RISKS = True

ASSET_RISK_UNIVERSE = "data/asset_risk_universe.json"
CLIENT_RISK_UNIVERSE = "output_auto/risk_universe.json"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("scoring")


def get_already_scored(output_dir: str) -> set[str]:
    """Check which risks have already been scored (for resume)."""
    scored = set()
    if not os.path.isdir(output_dir):
        return scored
    for fname in os.listdir(output_dir):
        if fname.endswith("_scored.json"):
            risk_id = fname.replace("_scored.json", "")
            scored.add(risk_id)
    return scored


def save_risk(scored: ScoredRisk, output_dir: str) -> None:
    """Write a single scored risk to disk immediately."""
    path = os.path.join(output_dir, f"{scored.risk_id}_scored.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scored.model_dump(mode="json"), f, indent=2, ensure_ascii=False)


def load_all_scored(output_dir: str) -> list[ScoredRisk]:
    """Load all previously scored risks from disk."""
    scored = []
    if not os.path.isdir(output_dir):
        return scored
    for fname in sorted(os.listdir(output_dir)):
        if fname.endswith("_scored.json"):
            path = os.path.join(output_dir, fname)
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            scored.append(ScoredRisk.model_validate(data))
    return scored


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load inputs
    logger.info("Loading inputs...")
    risk_universe_path = ASSET_RISK_UNIVERSE if SCORE_ASSET_RISKS else CLIENT_RISK_UNIVERSE
    logger.info("Risk universe: %s", risk_universe_path)
    with open(risk_universe_path, "r", encoding="utf-8") as f:
        raw_risks = json.load(f)
    # Strip extra metadata fields (prefixed with _) for MappedRisk validation
    for r in raw_risks:
        for key in list(r.keys()):
            if key.startswith("_"):
                del r[key]
    all_risks = [MappedRisk.model_validate(r) for r in raw_risks]
    with open("auto_transcript.txt", "r", encoding="utf-8") as f:
        transcript = f.read()
    with open("data/questionnaires/velocityauto_questionnaire.json", "r", encoding="utf-8") as f:
        questionnaire = json.load(f)
    with open("data/likelihood_tables/automotive.json", "r", encoding="utf-8") as f:
        likelihood_table = json.load(f)

    impact_table_text = load_impact_table_text(
        "data/impact_tables/Impact_Assessment_GuidBook_Automotive.xlsx", "Automotive"
    )

    # Check what's already done
    already_scored = get_already_scored(OUTPUT_DIR)
    if already_scored:
        logger.info("Resuming — %d risks already scored: %s", len(already_scored), sorted(already_scored))

    # Initialize LLM
    llm = LLMWrapper()
    company_profile = extract_company_profile(questionnaire)
    memory = MemoryStore(company_profile)

    # Load previously scored risks into memory for consistency
    prev_scored = load_all_scored(OUTPUT_DIR)
    for ps in prev_scored:
        memory.record_scored_risk(ps)

    logger.info("Pipeline ready — %d risks to process, %d already done",
                len(all_risks), len(already_scored))

    # Score each risk
    newly_scored = 0
    failed = []

    for i, risk in enumerate(all_risks, 1):
        if risk.risk_id in already_scored:
            logger.info("[%d/%d] %s — already scored, skipping", i, len(all_risks), risk.risk_id)
            continue

        logger.info("[%d/%d] === %s: %s ===", i, len(all_risks), risk.risk_id, risk.client_description)
        risk_start = time.time()

        try:
            # Step 1: Evidence assembly (no LLM)
            evidence = assemble_evidence(risk, transcript, all_risks)

            # Step 2: Knowledge summarizer (LLM call 1)
            logger.info("  [1/4] Knowledge summarizer...")
            knowledge = summarize_knowledge(evidence, questionnaire, company_profile, llm)
            logger.info("  → completeness=%s, %d fields", knowledge.completeness, len(knowledge.risk_relevant_context))

            # Step 3: External intelligence (web search + LLM call 2)
            logger.info("  [2/4] External intelligence (web search)...")
            ext_intel = gather_external_intelligence(evidence, knowledge, llm)
            logger.info("  → signal=%s, confidence=%s, %d sources",
                        ext_intel.external_likelihood_signal, ext_intel.confidence_in_assessment, len(ext_intel.sources))

            # Step 4: Likelihood intelligence (LLM call 3)
            logger.info("  [3/4] Likelihood intelligence...")
            current_memory = memory.get_memory()
            likelihood = assess_likelihood(evidence, knowledge, likelihood_table, current_memory, llm, external_intel=ext_intel)
            logger.info("  → %d/5 (raw=%.2f), confidence=%s", likelihood.composite_rounded, likelihood.composite_score, likelihood.confidence)

            # Step 5: Dimension classifier (focused LLM call)
            logger.info("  [4/5] Dimension classifier...")
            from riskmapper.scoring.dimension_classifier import classify_dimension
            primary_dimension = classify_dimension(evidence, knowledge, llm)
            logger.info("  → dimension: %s", primary_dimension)

            # Step 6: Scoring agent (LLM call 5)
            logger.info("  [5/5] Scoring agent...")
            scored = score_risk(evidence, knowledge, likelihood, impact_table_text, likelihood_table, current_memory, llm, external_intel=ext_intel, forced_dimension=primary_dimension)

            # Save immediately
            save_risk(scored, OUTPUT_DIR)
            memory.record_scored_risk(scored)
            newly_scored += 1

            elapsed = time.time() - risk_start
            logger.info(
                "  ✓ %s: I=%d (%s / %s) | L=%d (%s) | Score=%d %s | %.0fs",
                scored.risk_id,
                scored.impact_assessment.score, scored.impact_assessment.dimension, scored.impact_assessment.sub_dimension,
                scored.likelihood_assessment.score, scored.likelihood_assessment.level,
                scored.inherent_risk_score, scored.risk_rating, elapsed,
            )

        except Exception as exc:
            elapsed = time.time() - risk_start
            logger.error("  ✗ %s FAILED after %.0fs: %s", risk.risk_id, elapsed, exc)
            failed.append(risk.risk_id)

            # If it's a rate limit issue, wait before continuing
            if "429" in str(exc) or "rate" in str(exc).lower():
                logger.info("  Rate limit detected — waiting 60s before next risk...")
                time.sleep(60)

    # Final assembly
    logger.info("\n=== Scoring complete ===")
    logger.info("Newly scored: %d | Previously scored: %d | Failed: %d",
                newly_scored, len(already_scored), len(failed))

    if failed:
        logger.info("Failed risks: %s", failed)

    # Generate final report from all scored risks on disk
    all_scored = load_all_scored(OUTPUT_DIR)
    if all_scored:
        logger.info("Generating final report from %d scored risks...", len(all_scored))
        summary = _build_summary(all_scored)
        consistency = check_consistency(all_scored, memory.cascade_graph)
        result = ScoringPipelineResult(
            scored_risks=all_scored,
            consistency_check=consistency,
            total_risks=len(all_scored),
            scoring_summary=summary,
        )
        _write_outputs(result, OUTPUT_DIR)

        print(f"\n{'='*60}")
        print(f"SCORING COMPLETE — {len(all_scored)}/{len(all_risks)} risks scored")
        print(f"{'='*60}")
        print(f"  Critical: {summary.critical_count}")
        print(f"  High:     {summary.high_count}")
        print(f"  Medium:   {summary.medium_count}")
        print(f"  Low:      {summary.low_count}")
        print(f"  Failed:   {len(failed)} ({', '.join(failed) if failed else 'none'})")
        print(f"\nOutputs: {OUTPUT_DIR}/")
        print(f"  - scored_risk_universe.json")
        print(f"  - scoring_report.md")
        print(f"  - scoring_summary.json")
        print(f"  - RISK_XXX_scored.json (per-risk files)")
    else:
        print("No risks scored.")


if __name__ == "__main__":
    main()
