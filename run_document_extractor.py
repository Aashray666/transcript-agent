"""Entry point — run the Document Risk Extractor on any supported file.

Usage:
    python run_document_extractor.py \
        --file data/audit_report.pdf \
        --type audit_report \
        --sector Automotive \
        --output output_doc_extraction

Supported document types:
    audit_report        Internal audit reports, management letters
    con_call_transcript Earnings calls, investor day transcripts
    annual_report       10-K, annual reports, integrated reports
    board_presentation  Board packs, risk committee presentations
    management_letter   External auditor management letters
    regulatory_filing   SEC filings, regulatory submissions
    other               Any other document

Supported file formats:
    .pdf    (requires: pip install pdfplumber)
    .docx   (requires: pip install python-docx)
    .xlsx   (requires: pip install openpyxl — already installed)
    .txt    (no extra dependencies)
    .md     (no extra dependencies)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("doc_extractor")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract risks from any corporate document",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--file", "-f",
        required=True,
        help="Path to the document file (PDF, DOCX, XLSX, TXT, MD)",
    )
    parser.add_argument(
        "--type", "-t",
        required=True,
        choices=[
            "audit_report", "con_call_transcript", "annual_report",
            "board_presentation", "management_letter", "regulatory_filing", "other",
        ],
        help="Type of document",
    )
    parser.add_argument(
        "--sector", "-s",
        default="General",
        help="Client sector (e.g. Automotive, Banking, Healthcare). Default: General",
    )
    parser.add_argument(
        "--output", "-o",
        default="output_doc_extraction",
        help="Output directory. Default: output_doc_extraction",
    )
    parser.add_argument(
        "--max-chunk-chars",
        type=int,
        default=3000,
        help="Maximum characters per chunk. Default: 3000 (~750 tokens)",
    )
    parser.add_argument(
        "--overlap-chars",
        type=int,
        default=200,
        help="Overlap between consecutive chunks. Default: 200",
    )
    parser.add_argument(
        "--dedup-target",
        type=int,
        default=30,
        help="Target maximum unique risks after deduplication. Default: 30",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="NVIDIA API key (overrides NVIDIA_API_KEY env var and .env file)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Validate file exists
    if not os.path.isfile(args.file):
        logger.error("File not found: %s", args.file)
        sys.exit(1)

    # Import here so errors are clear
    try:
        from riskmapper.document_extractor import extract_risks_from_document
        from riskmapper.llm_wrapper import LLMWrapper
    except ImportError as exc:
        logger.error("Import failed: %s", exc)
        sys.exit(1)

    # Initialize LLM
    try:
        llm = LLMWrapper(api_key=args.api_key)
    except EnvironmentError as exc:
        logger.error(
            "LLM initialization failed: %s\n"
            "  Set NVIDIA_API_KEY in your environment, create a .env file, "
            "or pass --api-key YOUR_KEY",
            exc,
        )
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("Document Risk Extractor")
    logger.info("  File:    %s", args.file)
    logger.info("  Type:    %s", args.type)
    logger.info("  Sector:  %s", args.sector)
    logger.info("  Output:  %s", args.output)
    logger.info("=" * 60)

    start = time.time()

    result = extract_risks_from_document(
        file_path=args.file,
        document_type=args.type,
        sector=args.sector,
        llm=llm,
        output_dir=args.output,
        max_chunk_chars=args.max_chunk_chars,
        overlap_chars=args.overlap_chars,
        dedup_target_max=args.dedup_target,
    )

    elapsed = time.time() - start
    s = result.summary

    print(f"\n{'=' * 60}")
    print(f"EXTRACTION COMPLETE — {s.deduplicated_risks} risks found")
    print(f"{'=' * 60}")
    print(f"  Document:  {s.document_name}")
    print(f"  Chunks:    {s.total_chunks} total, {s.chunks_with_risks} with risks")
    print(f"  Raw mentions: {s.raw_mentions} → {s.deduplicated_risks} after dedup")
    print(f"")
    print(f"  Severity breakdown:")
    print(f"    Critical:    {s.critical_count}")
    print(f"    High:        {s.high_count}")
    print(f"    Medium:      {s.medium_count}")
    print(f"    Low:         {s.low_count}")
    print(f"    Unspecified: {s.unspecified_count}")
    print(f"")
    print(f"  Special flags:")
    print(f"    Material weaknesses: {s.material_weakness_count}")
    print(f"    Repeat findings:     {s.repeat_finding_count}")
    print(f"    Quantified risks:    {s.quantified_count}")
    print(f"")
    print(f"  Time: {elapsed:.1f}s")
    print(f"")
    print(f"  Outputs written to: {args.output}/")
    print(f"    - {os.path.basename(args.file).replace('.', '_')}_extraction.json")
    print(f"    - {os.path.basename(args.file).replace('.', '_')}_risks.json")
    print(f"    - {os.path.basename(args.file).replace('.', '_')}_report.md")

    if result.risks:
        print(f"\n  Top risks by severity:")
        sorted_risks = sorted(
            result.risks,
            key=lambda r: (
                -{"CRITICAL": 5, "HIGH": 4, "MEDIUM": 3, "LOW": 2, "UNSPECIFIED": 1}.get(
                    r.severity_signal, 1
                ),
            ),
        )
        for r in sorted_risks[:5]:
            qty = f" [{r.financial_quantification}]" if r.financial_quantification else ""
            flags = f" ⚑ {', '.join(r.flags[:2])}" if r.flags else ""
            print(f"    {r.risk_id} [{r.severity_signal}] {r.client_description[:60]}{qty}{flags}")


if __name__ == "__main__":
    main()
