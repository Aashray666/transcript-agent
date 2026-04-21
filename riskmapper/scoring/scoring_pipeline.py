"""Scoring Pipeline Orchestrator — Phase 2 entry point.

Iterates over the Phase 1 risk universe and produces inherent risk scores
for each risk using the multi-agent scoring chain:

1. Assemble evidence (data assembly, not LLM)
2. Summarize knowledge (LLM — questionnaire extraction)
3. Gather external intelligence (web search + LLM synthesis)
4. Assess likelihood (LLM — 5-factor methodology, informed by external intel)
5. Score risk (LLM — impact + likelihood with table grounding)
6. Check consistency (post-scoring validation)
7. Apply cascade adjustments (likelihood-only, second pass)
"""

from __future__ import annotations

import json
import logging
import os
import time

from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.schemas import MappedRisk, PipelineError
from riskmapper.scoring.cascade_scorer import apply_cascade_adjustments
from riskmapper.scoring.consistency_checker import check_consistency
from riskmapper.scoring.evidence_assembler import assemble_evidence
from riskmapper.scoring.external_intelligence import gather_external_intelligence
from riskmapper.scoring.knowledge_summarizer import (
    extract_company_profile,
    summarize_knowledge,
)
from riskmapper.scoring.likelihood_intelligence import assess_likelihood
from riskmapper.scoring.memory_store import MemoryStore
from riskmapper.scoring.schemas import (
    ScoredRisk,
    ScoringPipelineResult,
    ScoringPipelineSummary,
)
from riskmapper.scoring.scoring_agent import load_impact_table_text, score_risk

logger = logging.getLogger(__name__)


def run_scoring_pipeline(
    risk_universe_path: str,
    transcript_path: str,
    questionnaire_path: str,
    impact_table_path: str,
    likelihood_table_path: str,
    sector: str,
    output_dir: str,
) -> ScoringPipelineResult:
    """Execute the full Phase 2 scoring pipeline.

    Args:
        risk_universe_path: Path to Phase 1 risk_universe.json.
        transcript_path: Path to the interview transcript.
        questionnaire_path: Path to the client questionnaire JSON.
        impact_table_path: Path to the impact assessment XLSX.
        likelihood_table_path: Path to the likelihood table JSON.
        sector: Sector name (must match impact table sheet name).
        output_dir: Directory for scoring output files.

    Returns:
        ScoringPipelineResult with all scored risks and consistency check.

    Raises:
        FileNotFoundError: If any input file is missing.
        EnvironmentError: If GROQ_API_KEY not set.
        PipelineError: If a critical step fails.
    """
    os.makedirs(output_dir, exist_ok=True)
    _setup_scoring_log(output_dir)
    pipeline_start = time.time()

    logger.info("=== Phase 2: Risk Scoring Pipeline Started ===")
    logger.info("Sector: %s", sector)

    # --- Validate inputs ---
    for path, label in [
        (risk_universe_path, "Risk universe"),
        (transcript_path, "Transcript"),
        (questionnaire_path, "Questionnaire"),
        (impact_table_path, "Impact table"),
        (likelihood_table_path, "Likelihood table"),
    ]:
        if not os.path.isfile(path):
            raise FileNotFoundError(f"{label} not found: {path}")

    # --- Load inputs ---
    step_start = time.time()
    logger.info("Loading inputs...")

    with open(risk_universe_path, "r", encoding="utf-8") as f:
        raw_risks = json.load(f)
    all_risks = [MappedRisk.model_validate(r) for r in raw_risks]
    logger.info("Loaded %d risks from Phase 1 output.", len(all_risks))

    with open(transcript_path, "r", encoding="utf-8") as f:
        transcript_text = f.read()

    with open(questionnaire_path, "r", encoding="utf-8") as f:
        questionnaire = json.load(f)

    with open(likelihood_table_path, "r", encoding="utf-8") as f:
        likelihood_table = json.load(f)

    impact_table_text = load_impact_table_text(impact_table_path, sector)
    logger.info("Inputs loaded in %.2fs", time.time() - step_start)

    # --- Initialize components ---
    llm = LLMWrapper()
    company_profile = extract_company_profile(questionnaire)
    memory = MemoryStore(company_profile)

    logger.info(
        "Company: %s (%s / %s)",
        company_profile.headquarters,
        company_profile.sector,
        company_profile.sub_sector,
    )

    # --- Score each risk ---
    scored_risks: list[ScoredRisk] = []

    for i, risk in enumerate(all_risks, 1):
        risk_start = time.time()
        logger.info(
            "--- Scoring risk %d/%d: %s (%s) ---",
            i, len(all_risks), risk.risk_id, risk.client_description,
        )

        try:
            scored = _score_single_risk(
                risk=risk,
                all_risks=all_risks,
                transcript_text=transcript_text,
                questionnaire=questionnaire,
                company_profile=company_profile,
                likelihood_table=likelihood_table,
                impact_table_text=impact_table_text,
                memory=memory,
                llm=llm,
            )
            scored_risks.append(scored)
            memory.record_scored_risk(scored)

            logger.info(
                "%s scored: I=%d L=%d Score=%d (%s) [%.2fs]",
                scored.risk_id,
                scored.impact_assessment.score,
                scored.likelihood_assessment.score,
                scored.inherent_risk_score,
                scored.risk_rating,
                time.time() - risk_start,
            )

        except Exception as exc:
            # Non-critical: log and continue (per Phase 1 pattern)
            logger.error(
                "Failed to score %s: %s. Skipping.", risk.risk_id, exc,
            )

    if not scored_risks:
        raise PipelineError("No risks were successfully scored.")

    # --- Cascade adjustments (second pass, likelihood-only) ---
    step_start = time.time()
    logger.info("=== Cascade Adjustment Pass ===")
    scored_risks = apply_cascade_adjustments(
        scored_risks, memory.cascade_graph,
    )
    logger.info("Cascade pass completed in %.2fs", time.time() - step_start)

    # --- Consistency check ---
    step_start = time.time()
    logger.info("=== Consistency Check ===")
    consistency = check_consistency(scored_risks, memory.cascade_graph)
    logger.info(
        "Consistency check: %s [%.2fs]",
        consistency.overall_assessment,
        time.time() - step_start,
    )

    # --- Build summary ---
    summary = _build_summary(scored_risks)

    result = ScoringPipelineResult(
        scored_risks=scored_risks,
        consistency_check=consistency,
        total_risks=len(scored_risks),
        scoring_summary=summary,
    )

    # --- Write outputs ---
    _write_outputs(result, output_dir)

    total_time = time.time() - pipeline_start
    logger.info(
        "=== Phase 2 Complete === | %d risks scored | %.2fs total",
        len(scored_risks), total_time,
    )

    return result


def _score_single_risk(
    risk: MappedRisk,
    all_risks: list[MappedRisk],
    transcript_text: str,
    questionnaire: dict,
    company_profile,
    likelihood_table: dict,
    impact_table_text: str,
    memory: MemoryStore,
    llm: LLMWrapper,
) -> ScoredRisk:
    """Run the full scoring chain for a single risk.

    Chain: evidence → knowledge → external intelligence → likelihood → scoring.
    """
    # Step 1: Assemble evidence (data assembly, no LLM call)
    evidence = assemble_evidence(risk, transcript_text, all_risks)
    logger.debug(
        "%s evidence: %d quotes, strength=%s",
        risk.risk_id, len(evidence.verbatim_quotes), evidence.evidence_strength,
    )

    # Step 2: Knowledge summarizer (LLM call)
    knowledge = summarize_knowledge(
        evidence, questionnaire, company_profile, llm,
    )
    logger.debug(
        "%s knowledge: completeness=%s, %d context fields",
        risk.risk_id, knowledge.completeness,
        len(knowledge.risk_relevant_context),
    )

    # Step 3: External intelligence (web search + LLM synthesis)
    ext_intel = gather_external_intelligence(evidence, knowledge, llm)
    logger.debug(
        "%s external intel: signal=%s, confidence=%s, %d sources",
        risk.risk_id, ext_intel.external_likelihood_signal,
        ext_intel.confidence_in_assessment, len(ext_intel.sources),
    )

    # Step 4: Likelihood intelligence (LLM call — 5-factor, informed by ext intel)
    current_memory = memory.get_memory()
    likelihood = assess_likelihood(
        evidence, knowledge, likelihood_table, current_memory, llm,
        external_intel=ext_intel,
    )
    logger.debug(
        "%s likelihood: composite=%d (raw=%.2f), confidence=%s",
        risk.risk_id, likelihood.composite_rounded,
        likelihood.composite_score, likelihood.confidence,
    )

    # Step 5: Scoring agent (LLM call — impact + final likelihood)
    scored = score_risk(
        evidence, knowledge, likelihood, impact_table_text,
        likelihood_table, current_memory, llm,
        external_intel=ext_intel,
    )

    return scored


def _build_summary(scored_risks: list[ScoredRisk]) -> ScoringPipelineSummary:
    """Build aggregate statistics for the scoring run."""
    ratings = [r.risk_rating for r in scored_risks]
    confidences = [r.scoring_confidence for r in scored_risks]
    review_count = sum(1 for r in scored_risks if r.flags_for_review)

    # Average confidence: HIGH=3, MEDIUM=2, LOW=1
    conf_map = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
    avg_conf_val = sum(conf_map.get(c, 2) for c in confidences) / max(len(confidences), 1)
    if avg_conf_val >= 2.5:
        avg_conf = "HIGH"
    elif avg_conf_val >= 1.5:
        avg_conf = "MEDIUM"
    else:
        avg_conf = "LOW"

    return ScoringPipelineSummary(
        total_scored=len(scored_risks),
        low_count=ratings.count("Low"),
        medium_count=ratings.count("Medium"),
        high_count=ratings.count("High"),
        critical_count=ratings.count("Critical"),
        human_review_count=review_count,
        average_confidence=avg_conf,
    )


def _write_outputs(result: ScoringPipelineResult, output_dir: str) -> None:
    """Write scoring outputs to disk."""
    # scored_risk_universe.json — full scored risks
    scored_path = os.path.join(output_dir, "scored_risk_universe.json")
    with open(scored_path, "w", encoding="utf-8") as f:
        json.dump(
            [r.model_dump(mode="json") for r in result.scored_risks],
            f, indent=2, ensure_ascii=False,
        )
    logger.info("Written: %s (%d risks)", scored_path, len(result.scored_risks))

    # scoring_summary.json — aggregate stats
    summary_path = os.path.join(output_dir, "scoring_summary.json")
    summary_data = result.scoring_summary.model_dump(mode="json")
    summary_data["consistency_check"] = (
        result.consistency_check.model_dump(mode="json")
        if result.consistency_check else None
    )
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)
    logger.info("Written: %s", summary_path)

    # scoring_review_queue.json — risks flagged for review
    review_path = os.path.join(output_dir, "scoring_review_queue.json")
    flagged = [
        r.model_dump(mode="json")
        for r in result.scored_risks
        if r.flags_for_review
    ]
    with open(review_path, "w", encoding="utf-8") as f:
        json.dump(flagged, f, indent=2, ensure_ascii=False)
    logger.info("Written: %s (%d flagged)", review_path, len(flagged))

    # scoring_report.md — human-readable audit report
    report_path = os.path.join(output_dir, "scoring_report.md")
    _write_audit_report(result, report_path)
    logger.info("Written: %s", report_path)


def _setup_scoring_log(output_dir: str) -> None:
    """Configure logging for the scoring pipeline."""
    log_path = os.path.join(output_dir, "scoring_pipeline.log")

    scoring_logger = logging.getLogger("riskmapper.scoring")
    scoring_logger.setLevel(logging.INFO)

    # Remove existing file handlers
    scoring_logger.handlers = [
        h for h in scoring_logger.handlers
        if not isinstance(h, logging.FileHandler)
    ]

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    )
    scoring_logger.addHandler(file_handler)

    if not any(
        isinstance(h, logging.StreamHandler)
        and not isinstance(h, logging.FileHandler)
        for h in scoring_logger.handlers
    ):
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(logging.Formatter("%(name)s | %(message)s"))
        scoring_logger.addHandler(console)


def _write_audit_report(result: ScoringPipelineResult, path: str) -> None:
    """Write a human-readable audit report with full justifications.

    This is the deliverable a consultant would present to the client —
    each risk with its score, evidence cited, table criteria matched,
    and reasoning chain.
    """
    lines: list[str] = []
    lines.append("# Risk Scoring Audit Report — VelocityAuto Group")
    lines.append("")
    lines.append(f"**Total Risks Scored:** {result.total_risks}")
    lines.append(f"**Distribution:** "
                 f"Critical={result.scoring_summary.critical_count}, "
                 f"High={result.scoring_summary.high_count}, "
                 f"Medium={result.scoring_summary.medium_count}, "
                 f"Low={result.scoring_summary.low_count}")
    lines.append(f"**Average Confidence:** {result.scoring_summary.average_confidence}")
    lines.append("")

    # Risk matrix summary table
    lines.append("## Risk Matrix Summary")
    lines.append("")
    lines.append("| Rank | Risk ID | Description | Impact | Likelihood | Inherent | Rating | Confidence |")
    lines.append("|------|---------|-------------|--------|------------|----------|--------|------------|")

    sorted_risks = sorted(
        result.scored_risks,
        key=lambda r: r.inherent_risk_score,
        reverse=True,
    )
    for i, r in enumerate(sorted_risks, 1):
        lines.append(
            f"| {i} | {r.risk_id} | {r.client_description} | "
            f"{r.impact_assessment.score} ({r.impact_assessment.level}) | "
            f"{r.likelihood_assessment.score} ({r.likelihood_assessment.level}) | "
            f"{r.inherent_risk_score} | {r.risk_rating} | "
            f"{r.scoring_confidence} |"
        )

    lines.append("")
    lines.append("---")
    lines.append("")

    # Detailed per-risk justification
    lines.append("## Detailed Risk Scoring Justifications")
    lines.append("")

    for r in sorted_risks:
        lines.append(f"### {r.risk_id}: {r.client_description}")
        lines.append("")
        lines.append(f"**Inherent Risk Score: {r.inherent_risk_score} ({r.risk_rating})**")
        lines.append("")

        # Impact
        ia = r.impact_assessment
        lines.append(f"#### Impact: {ia.score}/5 ({ia.level})")
        lines.append(f"- **Dimension:** {ia.dimension}")
        lines.append(f"- **Sub-Dimension:** {ia.sub_dimension}")
        lines.append(f"- **Metric:** {ia.metric}")
        lines.append(f"- **Table Criteria Matched:** {ia.table_criteria_matched}")
        lines.append(f"- **Justification:** {ia.justification}")
        lines.append("")

        # Likelihood
        la = r.likelihood_assessment
        lines.append(f"#### Likelihood: {la.score}/5 ({la.level})")
        lines.append(f"- **Evidence Basis:** {la.evidence_basis}")
        lines.append(f"- **Table Criteria Matched:** {la.table_criteria_matched}")
        lines.append(f"- **Justification:** {la.justification}")
        lines.append("")

        # Evidence & Context
        lines.append(f"#### Supporting Evidence")
        lines.append(f"- **Evidence Summary:** {r.evidence_summary}")
        lines.append(f"- **Client Context Used:** {r.client_context_used}")
        lines.append(f"- **Scoring Confidence:** {r.scoring_confidence}")
        lines.append("")

        # External Intelligence (market research)
        if r.market_intelligence_used:
            mi = r.market_intelligence_used
            lines.append(f"#### Market Intelligence (EXTERNAL_INTELLIGENCE)")
            lines.append(f"- **Signal:** {mi.external_likelihood_signal}")
            lines.append(f"- **Data Freshness:** {mi.data_freshness}")
            if mi.recent_incidents:
                lines.append(f"- **Recent Peer Incidents:**")
                for inc in mi.recent_incidents:
                    lines.append(f"  - {inc}")
            if mi.regulatory_developments:
                lines.append(f"- **Regulatory Developments:**")
                for reg in mi.regulatory_developments:
                    lines.append(f"  - {reg}")
            if mi.market_trends:
                lines.append(f"- **Market Trends:**")
                for trend in mi.market_trends:
                    lines.append(f"  - {trend}")
            if mi.sources:
                lines.append(f"- **Sources ({len(mi.sources)}):**")
                for src in mi.sources[:5]:
                    lines.append(f"  - {src}")
            if mi.search_queries:
                lines.append(f"- **Search Queries Used:** {'; '.join(mi.search_queries)}")
            lines.append("")

        # Consistency & Cascade
        if r.consistency_notes:
            lines.append(f"#### Consistency Notes")
            lines.append(f"{r.consistency_notes}")
            lines.append("")

        cascade = r.cascade_scoring_impact
        if cascade.upstream_risks or cascade.downstream_risks:
            lines.append(f"#### Cascade Relationships")
            if cascade.upstream_risks:
                lines.append(f"- Upstream: {', '.join(cascade.upstream_risks)}")
            if cascade.downstream_risks:
                lines.append(f"- Downstream: {', '.join(cascade.downstream_risks)}")
            if cascade.cascade_likelihood_adjustment:
                lines.append(f"- Likelihood adjustment: +{cascade.cascade_likelihood_adjustment}")
            lines.append("")

        # Flags
        if r.flags_for_review:
            lines.append(f"#### ⚠️ Flags for Review")
            for flag in r.flags_for_review:
                lines.append(f"- {flag}")
            lines.append("")

        lines.append("---")
        lines.append("")

    # Consistency check results
    if result.consistency_check:
        cc = result.consistency_check
        lines.append("## Consistency Check Results")
        lines.append("")
        lines.append(f"**Assessment:** {cc.overall_assessment}")
        lines.append(f"**Score Distribution:** {cc.score_distribution}")
        lines.append("")
        if cc.flags:
            lines.append("### Flags Raised")
            lines.append("")
            for flag in cc.flags:
                lines.append(f"- **[{flag.severity}] {flag.flag_type}** — {flag.risk_id}: {flag.description}")
                if flag.recommended_adjustment:
                    lines.append(f"  - Recommendation: {flag.recommended_adjustment}")
            lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
