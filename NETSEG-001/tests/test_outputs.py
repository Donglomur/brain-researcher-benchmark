"""Complete original-source, own-primitive grading entry point."""
import os
from pathlib import Path

import proof_of_work as p


def test_complete_source_bound_output(source_reference):
    p.validate_output_directory(Path(os.environ.get("OUTPUT_DIR", "/app/output")), source_reference)
