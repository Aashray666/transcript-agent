"""Pipeline orchestrator — runs the full RiskMapper pipeline end to end.

Executes: load registry → parse transcript → deduplicate → map to registry
→ generate human review queue → build output. Logs each step with timing.
"""

from __future__ import annotations

import logging
import os
import time

import chromadb

from riskmapper.deduplicator import deduplicate_risks
from riskmapper.human_review_queue import generate_review_queue
from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.output_builder import build_output
from riskmapper.post_validator import validate_risk_universe
from riskmapper.registry_mapper import map_risks
from riskmapper.risk_registry_loader import load_registry
from riskmapper.schemas import PipelineError
from riskmapper.transcript_parser import parse_transcript

logger = logging.getLogger(__name__)


def run_pipeline(
    transcript_path: str,
    sector: str,
    registry_path: str,
    output_dir: str,
) -> None:
    """Execute the full RiskMapper pipeline.

    Args:
        transcript_path: Path to the transcript TXT file.
        sector: Client sector matching a sheet in the registry XLSX.
        registry_path: Path to the risk registry XLSX workbook.
        output_dir: Directory for all output files.

    Raises:
        FileNotFoundError: If transcript or registry file missing.
        EnvironmentError: If GROQ_API_KEY not set.
        PipelineError: If a critical step fails.
    """
    # --- Setup ---
    os.makedirs(output_dir, exist_ok=True)
    _setup_logging(output_dir)

    pipeline_start = time.time()
    logger.info("Pipeline started | sector=%s", sector)

    # Validate inputs
    if not os.path.isfile(transcript_path):
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    if not os.path.isfile(registry_path):
        raise FileNotFoundError(f"Registry not found: {registry_path}")

    # Initialise components
    llm = LLMWrapper()
    chroma_client = chromadb.Client()

    # --- Step 1: Load registry ---
    step_start = time.time()
    logger.info("Step 1: Loading risk registry")
    try:
        count = load_registry(registry_path, sector, chroma_client)
        logger.info(
            "Step 1 complete | entries=%d | %.2fs",
            count, time.time() - step_start,
        )
    except Exception as exc:
        logger.error("Step 1 FAILED: %s", exc)
        raise PipelineError(f"Registry loading failed: {exc}") from exc

    # --- Step 2: Parse transcript ---
    step_start = time.time()
    logger.info("Step 2: Parsing transcript")
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            transcript_text = f.read()
        mentions = parse_transcript(transcript_text, sector, llm)
        logger.info(
            "Step 2 complete | mentions=%d | %.2fs",
            len(mentions), time.time() - step_start,
        )
    except Exception as exc:
        logger.error("Step 2 FAILED: %s", exc)
        raise PipelineError(f"Transcript parsing failed: {exc}") from exc

    # --- Step 3: Deduplicate ---
    step_start = time.time()
    logger.info("Step 3: Deduplicating risk mentions")
    try:
        deduped = deduplicate_risks(mentions, llm)
        logger.info(
            "Step 3 complete | input=%d | output=%d | %.2fs",
            len(mentions), len(deduped), time.time() - step_start,
        )
    except Exception as exc:
        logger.error("Step 3 FAILED: %s", exc)
        raise PipelineError(f"Deduplication failed: {exc}") from exc

    # --- Step 4: Map to registry ---
    step_start = time.time()
    logger.info("Step 4: Mapping risks to registry")
    try:
        mapped = map_risks(deduped, sector, chroma_client, llm)
        logger.info(
            "Step 4 complete | total=%d | unmapped=%d | %.2fs",
            len(mapped),
            sum(1 for r in mapped if r.unmapped),
            time.time() - step_start,
        )
    except Exception as exc:
        logger.error("Step 4 FAILED: %s", exc)
        raise PipelineError(f"Registry mapping failed: {exc}") from exc

    # --- Step 5: Validate risk universe (Feedback Loop 2) ---
    step_start = time.time()
    logger.info("Step 5: Validating risk universe")
    mapped = validate_risk_universe(mapped, llm)
    logger.info(
        "Step 5 complete | risks_after_validation=%d | %.2fs",
        len(mapped), time.time() - step_start,
    )

    # --- Step 6: Generate human review queue ---
    step_start = time.time()
    logger.info("Step 6: Generating human review queue")
    review_path = os.path.join(output_dir, "human_review_queue.json")
    try:
        review_count = generate_review_queue(mapped, review_path)
        logger.info(
            "Step 6 complete | review_count=%d | %.2fs",
            review_count, time.time() - step_start,
        )
    except Exception as exc:
        logger.error("Step 6 FAILED: %s", exc)
        raise PipelineError(f"Review queue generation failed: {exc}") from exc

    # --- Step 7: Build output ---
    step_start = time.time()
    logger.info("Step 7: Building output files")
    try:
        build_output(mapped, output_dir)
        logger.info(
            "Step 7 complete | %.2fs", time.time() - step_start,
        )
    except Exception as exc:
        logger.error("Step 7 FAILED: %s", exc)
        raise PipelineError(f"Output building failed: {exc}") from exc

    # --- Done ---
    total_time = time.time() - pipeline_start
    logger.info(
        "Pipeline complete | total_risks=%d | mapped=%d | unmapped=%d | "
        "review=%d | total_time=%.2fs",
        len(mapped),
        sum(1 for r in mapped if not r.unmapped),
        sum(1 for r in mapped if r.unmapped),
        review_count,
        total_time,
    )


def _setup_logging(output_dir: str) -> None:
    """Configure logging to write to pipeline.log in the output directory."""
    log_path = os.path.join(output_dir, "pipeline.log")

    # Get root logger for the riskmapper package
    root_logger = logging.getLogger("riskmapper")
    root_logger.setLevel(logging.INFO)

    # Remove existing file handlers to avoid duplicates on re-runs
    root_logger.handlers = [
        h for h in root_logger.handlers
        if not isinstance(h, logging.FileHandler)
    ]

    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s")
    )
    root_logger.addHandler(file_handler)

    # Also log to console
    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
               for h in root_logger.handlers):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter("%(name)s | %(message)s")
        )
        root_logger.addHandler(console_handler)
