"""V2 Pipeline — single-call parsing, richer dedup, same mapping/output.

Key changes from v1:
- Preprocesses transcript to strip interviewer lines
- Single LLM call for parsing (no chunking)
- Richer dedup with full evidence context
- Same registry mapper, review queue, and output builder
"""

from __future__ import annotations

import logging
import os
import time

import chromadb

from riskmapper.deduplicator_v2 import deduplicate_risks_v2
from riskmapper.human_review_queue import generate_review_queue
from riskmapper.llm_wrapper import LLMWrapper
from riskmapper.output_builder import build_output
from riskmapper.registry_mapper import map_risks
from riskmapper.risk_registry_loader import load_registry
from riskmapper.schemas import PipelineError
from riskmapper.transcript_parser_v2 import parse_transcript_v2

logger = logging.getLogger(__name__)


def run_pipeline_v2(
    transcript_path: str,
    sector: str,
    registry_path: str,
    output_dir: str,
) -> None:
    """Execute the V2 RiskMapper pipeline."""
    os.makedirs(output_dir, exist_ok=True)
    _setup_logging(output_dir)

    pipeline_start = time.time()
    logger.info("V2 Pipeline started | sector=%s", sector)

    if not os.path.isfile(transcript_path):
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    if not os.path.isfile(registry_path):
        raise FileNotFoundError(f"Registry not found: {registry_path}")

    llm = LLMWrapper()
    chroma_client = chromadb.Client()

    # Step 1: Load registry
    t = time.time()
    logger.info("Step 1: Loading registry")
    try:
        count = load_registry(registry_path, sector, chroma_client)
        logger.info("Step 1 done | entries=%d | %.2fs", count, time.time() - t)
    except Exception as e:
        logger.error("Step 1 FAILED: %s", e)
        raise PipelineError(f"Registry loading failed: {e}") from e

    # Step 2: Parse transcript (single call)
    t = time.time()
    logger.info("Step 2: Parsing transcript (single call)")
    try:
        with open(transcript_path, "r", encoding="utf-8") as f:
            raw_transcript = f.read()
        mentions = parse_transcript_v2(raw_transcript, sector, llm)
        logger.info("Step 2 done | mentions=%d | %.2fs", len(mentions), time.time() - t)
    except Exception as e:
        logger.error("Step 2 FAILED: %s", e)
        raise PipelineError(f"Transcript parsing failed: {e}") from e

    # Step 3: Deduplicate (richer context)
    # Wait for rate limit cooldown after heavy parsing call
    logger.info("Waiting 15s for rate limit cooldown...")
    time.sleep(15)
    t = time.time()
    logger.info("Step 3: Deduplicating")
    try:
        deduped = deduplicate_risks_v2(mentions, llm)
        logger.info(
            "Step 3 done | input=%d | output=%d | %.2fs",
            len(mentions), len(deduped), time.time() - t,
        )
    except Exception as e:
        logger.error("Step 3 FAILED: %s", e)
        raise PipelineError(f"Deduplication failed: {e}") from e

    # Step 4: Map to registry
    t = time.time()
    logger.info("Step 4: Mapping to registry")
    try:
        mapped = map_risks(deduped, sector, chroma_client, llm)
        logger.info(
            "Step 4 done | total=%d | unmapped=%d | %.2fs",
            len(mapped), sum(1 for r in mapped if r.unmapped), time.time() - t,
        )
    except Exception as e:
        logger.error("Step 4 FAILED: %s", e)
        raise PipelineError(f"Registry mapping failed: {e}") from e

    # Step 5: Human review queue
    t = time.time()
    review_path = os.path.join(output_dir, "human_review_queue.json")
    review_count = generate_review_queue(mapped, review_path)
    logger.info("Step 5 done | review=%d | %.2fs", review_count, time.time() - t)

    # Step 6: Build output
    t = time.time()
    build_output(mapped, output_dir)
    logger.info("Step 6 done | %.2fs", time.time() - t)

    total = time.time() - pipeline_start
    logger.info(
        "V2 Pipeline complete | risks=%d | mapped=%d | unmapped=%d | "
        "review=%d | time=%.2fs",
        len(mapped),
        sum(1 for r in mapped if not r.unmapped),
        sum(1 for r in mapped if r.unmapped),
        review_count, total,
    )


def _setup_logging(output_dir: str) -> None:
    log_path = os.path.join(output_dir, "pipeline.log")
    root = logging.getLogger("riskmapper")
    root.setLevel(logging.INFO)
    root.handlers = [h for h in root.handlers if not isinstance(h, logging.FileHandler)]

    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter("%(asctime)s | %(name)s | %(levelname)s | %(message)s"))
    root.addHandler(fh)

    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
               for h in root.handlers):
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter("%(name)s | %(message)s"))
        root.addHandler(ch)
