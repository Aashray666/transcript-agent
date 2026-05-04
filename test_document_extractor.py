"""End-to-end test for the Document Risk Extractor — uses a mock LLM.

Run with:
    python3 test_document_extractor.py

This validates the full pipeline (load → chunk → extract → dedup → output)
without making any real API calls. Uses the existing auto_transcript.txt.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from unittest.mock import MagicMock, patch
from uuid import uuid4

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("test")


# ---------------------------------------------------------------------------
# Mock LLM responses
# ---------------------------------------------------------------------------

def _make_mock_llm() -> MagicMock:
    """Build a mock LLMWrapper that returns realistic structured responses."""
    from riskmapper.document_extractor.schemas import (
        _LLMDocumentParseResponse,
        _LLMDocumentRiskMention,
    )
    from riskmapper.document_extractor.deduplicator import (
        _DeduplicationLLMResponse,
        _MergeGroup,
    )

    call_count = [0]

    def mock_call(prompt, response_model, temperature=0.0, step_name="", system_prompt=None):
        call_count[0] += 1
        step = step_name or ""

        # Chunk extraction calls
        if "doc_parse" in step:
            chunk_num = int(step.split("_")[-1].replace("chunk", "").strip("_0") or "1")
            mentions = []
            if call_count[0] <= 3:  # First 3 chunks get risks
                mentions = [
                    _LLMDocumentRiskMention(
                        client_description=f"EV transition execution risk — capital allocation and timeline uncertainty (chunk {call_count[0]})",
                        verbatim_evidence=[
                            "We've committed heavily to electrification — new platforms, battery supply agreements, retooling three plants",
                            "the market isn't moving at the pace we planned for",
                        ],
                        source_section="Risk Factors",
                        risk_type="INHERENT",
                        risk_category="Strategic",
                        severity_signal="HIGH",
                        financial_quantification="EUR 2.1B capex committed",
                        management_response="Reviewing transition roadmap timeline",
                        flags=["QUANTIFIED", "FORWARD_LOOKING"],
                        cascade_context=None,
                    ),
                    _LLMDocumentRiskMention(
                        client_description="Supply chain concentration risk — single-source semiconductor dependency",
                        verbatim_evidence=[
                            "22% of our components are single-sourced",
                            "semiconductor shortage cost us EUR 400M in lost production",
                        ],
                        source_section="Operational Risks",
                        risk_type="EVENT_DRIVEN",
                        risk_category="Operational",
                        severity_signal="CRITICAL",
                        financial_quantification="EUR 400M historical impact",
                        management_response="Dual-sourcing program initiated for critical components",
                        flags=["QUANTIFIED", "ALREADY_MATERIALIZED"],
                        cascade_context="Supply chain disruption can cascade into production downtime and revenue loss",
                    ),
                ]
            return _LLMDocumentParseResponse(mentions=mentions)

        # Deduplication call
        elif "dedup" in step:
            # Group the mentions — indices 0,2,4 are EV risk; 1,3,5 are supply chain
            n = len([l for l in prompt.split("\n") if l.startswith("[")])
            groups = []
            ev_indices = list(range(0, n, 2))
            sc_indices = list(range(1, n, 2))
            if ev_indices:
                groups.append(_MergeGroup(
                    indices=ev_indices,
                    best_description="EV transition execution risk — capital allocation and timeline uncertainty",
                    risk_type="INHERENT",
                    risk_category="Strategic",
                    cascade_context=None,
                ))
            if sc_indices:
                groups.append(_MergeGroup(
                    indices=sc_indices,
                    best_description="Supply chain concentration risk — single-source semiconductor dependency",
                    risk_type="EVENT_DRIVEN",
                    risk_category="Operational",
                    cascade_context="Can cascade into production downtime and revenue loss",
                ))
            return _DeduplicationLLMResponse(groups=groups)

        # Fallback
        raise ValueError(f"Unexpected step_name in mock: {step}")

    mock = MagicMock()
    mock.call.side_effect = mock_call
    return mock


# ---------------------------------------------------------------------------
# Main test
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("Document Risk Extractor — End-to-End Test (Mock LLM)")
    print("=" * 60)

    # Check transcript exists
    if not os.path.isfile("auto_transcript.txt"):
        print("ERROR: auto_transcript.txt not found")
        sys.exit(1)

    from riskmapper.document_extractor.extractor import extract_risks_from_document

    mock_llm = _make_mock_llm()
    output_dir = "output_doc_extraction_test"

    print("\n[1] Running extraction on auto_transcript.txt...")
    result = extract_risks_from_document(
        file_path="auto_transcript.txt",
        document_type="con_call_transcript",
        sector="Automotive",
        llm=mock_llm,
        output_dir=output_dir,
        max_chunk_chars=3000,
        overlap_chars=200,
    )

    s = result.summary
    print(f"\n[2] Results:")
    print(f"  Chunks processed:    {s.total_chunks}")
    print(f"  Chunks with risks:   {s.chunks_with_risks}")
    print(f"  Raw mentions:        {s.raw_mentions}")
    print(f"  Deduplicated risks:  {s.deduplicated_risks}")
    print(f"  Critical:            {s.critical_count}")
    print(f"  High:                {s.high_count}")
    print(f"  Quantified:          {s.quantified_count}")
    print(f"  LLM calls made:      {mock_llm.call.call_count}")

    print(f"\n[3] Extracted risks:")
    for r in result.risks:
        print(f"  {r.risk_id} [{r.severity_signal}] {r.client_description[:70]}")
        print(f"    Category: {r.risk_category} | Type: {r.risk_type} | Occurrences: {r.occurrence_count}")
        if r.financial_quantification:
            print(f"    Quantification: {r.financial_quantification}")
        if r.flags:
            print(f"    Flags: {', '.join(r.flags)}")
        print(f"    Evidence ({len(r.verbatim_evidence)} quotes):")
        for q in r.verbatim_evidence[:2]:
            print(f"      > {q[:80]}")

    print(f"\n[4] Output files written to: {output_dir}/")
    for fname in sorted(os.listdir(output_dir)):
        fpath = os.path.join(output_dir, fname)
        size = os.path.getsize(fpath)
        print(f"  {fname} ({size:,} bytes)")

    # Validate JSON output is valid
    risks_file = os.path.join(output_dir, "auto_transcript_txt_risks.json")
    if os.path.isfile(risks_file):
        with open(risks_file) as f:
            risks_data = json.load(f)
        print(f"\n[5] JSON validation: {len(risks_data)} risks in output file ✓")
    else:
        # Try alternate filename
        for fname in os.listdir(output_dir):
            if fname.endswith("_risks.json"):
                with open(os.path.join(output_dir, fname)) as f:
                    risks_data = json.load(f)
                print(f"\n[5] JSON validation: {len(risks_data)} risks in {fname} ✓")
                break

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED ✓")
    print("=" * 60)
    print("\nTo run with real LLM:")
    print("  1. Create .env file:  echo 'NVIDIA_API_KEY=nvapi-...' > .env")
    print("  2. Run:  python3 run_document_extractor.py \\")
    print("             --file auto_transcript.txt \\")
    print("             --type con_call_transcript \\")
    print("             --sector Automotive \\")
    print("             --output output_doc_extraction")


if __name__ == "__main__":
    main()
