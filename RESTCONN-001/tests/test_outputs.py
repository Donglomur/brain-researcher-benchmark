"""The single production grade: original source binding plus own-series replay."""
import os

from proof_of_work import validate_output_directory


def test_source_bound_circular_connectivity(original_reference):
    result = validate_output_directory(os.environ.get("OUTPUT_DIR", "/app/output"), original_reference)
    assert result["status"] == "accepted" and result["source_bound"] is True
