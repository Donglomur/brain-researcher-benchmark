"""Validate complete fixed-source measurements; never require a state story."""
import os
from pathlib import Path

import proof_of_work as pw


def test_complete_source_bound_measurements():
    reference = pw.load_reference(Path(__file__).with_name("reference.npz"))
    pw.validate_output_directory(Path(os.environ.get("OUTPUT_DIR", "/app/output")), reference)
