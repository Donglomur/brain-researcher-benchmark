"""The sole production source-bound output case; no transformation closure QA."""
import os

import proof_of_work


def test_source_bound_signed_map_spin(original_reference):
    result = proof_of_work.validate_output_directory(
        os.environ.get("OUTPUT_DIR", "/app/output"), original_reference)
    assert result["status"] == "accepted" and result["source_bound"]
