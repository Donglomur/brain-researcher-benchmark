"""One production gate; authoring mutations are not scoring requirements."""
import os
from proof_of_work import validate_output_directory

def test_source_bound_task_response_sensitivity(original_reference):
    result = validate_output_directory(os.environ.get("OUTPUT_DIR", "/app/output"), original_reference)
    assert result["status"] == "accepted" and result["source_bound"] is True
