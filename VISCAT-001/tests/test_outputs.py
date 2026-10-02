"""Complete source-bound category-selection evidence; binary pass/fail."""
import os
import proof_of_work as proof


def test_outputs(source_reference):
    proof.validate_output_directory(os.environ.get("OUTPUT_DIR", "/app/output"), source_reference)
