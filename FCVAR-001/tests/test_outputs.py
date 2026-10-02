"""The single source-bound production output check; no authoring mutations."""
import os
from pathlib import Path


def test_source_bound_fcvar(original_reference):
    import proof_of_work
    assert Path(proof_of_work.__file__).resolve().parent == Path(__file__).resolve().parent, "private proof module required"
    result = proof_of_work.validate_output_directory(os.environ.get("OUTPUT_DIR", "/app/output"), original_reference)
    assert result["status"] == "accepted"
