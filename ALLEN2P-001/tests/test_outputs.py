"""Numerical correctness, not held-out direction, rank agreement, or prose wording."""
import os
from pathlib import Path
import proof_of_work as q

OUT=Path(os.environ.get("OUTPUT_DIR","/app/output"))

def test_complete_original_presentation_and_response_evidence():
    ref=q.load_reference()
    q.read_table(OUT,"presentations.csv",q.PRESENTATION_FIELDS,("source_row_id",),q.expected_presentations(ref))
    q.read_trial_responses(OUT,ref)

def test_declared_method_estimates_aggregation_and_metadata():
    q.validate_output_directory(OUT,q.load_reference())
