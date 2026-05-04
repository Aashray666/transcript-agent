"""Test script — score a single risk with dimension classifier to verify fix."""

import json
import logging
import os

from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.schemas import MappedRisk
from riskmapper.scoring.dimension_classifier import classify_dimension
from riskmapper.scoring.evidence_assembler import assemble_evidence
from riskmapper.scoring.external_intelligence import gather_external_intelligence
from riskmapper.scoring.knowledge_summarizer import extract_company_profile, summarize_knowledge
from riskmapper.scoring.likelihood_intelligence import assess_likelihood
from riskmapper.scoring.memory_store import MemoryStore
from riskmapper.scoring.scoring_agent import load_impact_table_text, score_risk

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("test")

OUTPUT_DIR = "output_test"

# ARISK_003: "Stricter regulations to reduce vehicle emissions" — was Financial, should be Regulatory
RISK_INDEX = 2
USE_ASSET_RISKS = True


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Load the right risk universe
    if USE_ASSET_RISKS:
        with open("data/asset_risk_universe.json") as f:
            raw = json.load(f)
        for r in raw:
            for key in list(r.keys()):
                if key.startswith("_"):
                    del r[key]
        all_risks = [MappedRisk.model_validate(r) for r in raw]
    else:
        with open("output_auto/risk_universe.json") as f:
            all_risks = [MappedRisk.model_validate(r) for r in json.load(f)]

    with open("auto_transcript.txt") as f:
        transcript = f.read()
    with open("data/questionnaires/velocityauto_questionnaire.json") as f:
        questionnaire = json.load(f)
    with open("data/likelihood_tables/automotive.json") as f:
        likelihood_table = json.load(f)

    impact_table_text = load_impact_table_text(
        "data/impact_tables/Impact_Assessment_GuidBook_Automotive.xlsx", "Automotive"
    )

    llm = LLMWrapper()
    profile = extract_company_profile(questionnaire)
    memory = MemoryStore(profile)
    risk = all_risks[RISK_INDEX]

    logger.info("=== Testing: %s (%s) ===", risk.risk_id, risk.client_description)

    logger.info("[1/6] Evidence assembly...")
    evidence = assemble_evidence(risk, transcript, all_risks)
    logger.info("  %d quotes, strength=%s", len(evidence.verbatim_quotes), evidence.evidence_strength)

    logger.info("[2/6] Knowledge summarizer...")
    knowledge = summarize_knowledge(evidence, questionnaire, profile, llm)
    logger.info("  completeness=%s, %d fields", knowledge.completeness, len(knowledge.risk_relevant_context))

    logger.info("[3/6] External intelligence...")
    ext_intel = gather_external_intelligence(evidence, knowledge, llm)
    logger.info("  signal=%s, %d sources", ext_intel.external_likelihood_signal, len(ext_intel.sources))

    logger.info("[4/6] Likelihood intelligence...")
    likelihood = assess_likelihood(evidence, knowledge, likelihood_table, memory.get_memory(), llm, external_intel=ext_intel)
    logger.info("  composite=%d/5 (raw=%.2f)", likelihood.composite_rounded, likelihood.composite_score)
    for fs in likelihood.factor_scores:
        logger.info("    %s: %d/5 — %s", fs.factor, fs.score, fs.justification[:80])

    logger.info("[5/6] Dimension classifier...")
    primary_dimension = classify_dimension(evidence, knowledge, llm)
    logger.info("  >>> DIMENSION: %s", primary_dimension)

    logger.info("[6/6] Scoring agent (constrained to %s)...", primary_dimension)
    scored = score_risk(evidence, knowledge, likelihood, impact_table_text, likelihood_table,
                        memory.get_memory(), llm, external_intel=ext_intel, forced_dimension=primary_dimension)

    # Save
    path = os.path.join(OUTPUT_DIR, f"{risk.risk_id}_scored.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(scored.model_dump(mode="json"), f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"{scored.risk_id}: {scored.client_description}")
    print(f"{'='*60}")
    print(f"DIMENSION:  {scored.impact_assessment.dimension} (classifier chose: {primary_dimension})")
    print(f"Impact:     {scored.impact_assessment.score}/5 ({scored.impact_assessment.level})")
    print(f"  Sub-dim:    {scored.impact_assessment.sub_dimension}")
    print(f"  Metric:     {scored.impact_assessment.metric}")
    print(f"  Criteria:   {scored.impact_assessment.table_criteria_matched}")
    print(f"  Why:        {scored.impact_assessment.justification[:200]}")
    print(f"Likelihood: {scored.likelihood_assessment.score}/5 ({scored.likelihood_assessment.level})")
    print(f"  Basis:      {scored.likelihood_assessment.evidence_basis}")
    print(f"Inherent:   {scored.inherent_risk_score} → {scored.risk_rating}")
    print(f"Confidence: {scored.scoring_confidence}")
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
