"""Run the pipeline on the Automotive transcript."""
import logging
import sys

logging.basicConfig(level=logging.INFO, stream=sys.stdout, format="%(name)s | %(message)s")

from riskmapper.pipeline import run_pipeline

print("Starting pipeline on auto_transcript.txt (Automotive sector)...")
print()
run_pipeline(
    transcript_path="auto_transcript.txt",
    sector="Automotive",
    registry_path="risk.xlsx",
    output_dir="output_auto",
)
print()
print("PIPELINE COMPLETE — check output_auto/ directory")
