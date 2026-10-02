"""Production grading: originals and public method, never a historical bank."""
import os
from pathlib import Path

import proof_of_work


def test_source_bound_complete_evidence(source_reference):
    output = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
    proof_of_work.validate(output, source_reference)
