"""Single source-bound production check; genuine mutation QA is authoring only."""
import os
from pathlib import Path


def test_source_bound_fcmatur(original_reference):
    import output_contract
    assert Path(output_contract.__file__).resolve().parent == Path(__file__).resolve().parent
    result = output_contract.validate(os.environ.get("OUTPUT_DIR", "/app/output"), original_reference)
    assert result["status"] == "accepted"
