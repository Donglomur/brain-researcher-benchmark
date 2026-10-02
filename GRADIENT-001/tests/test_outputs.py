"""One source-authenticated production decision; no outcome or prose target."""
import os

from proof_of_work import validate
from source_reference import reconstruct


def test_source_bound_gradient():
    reference = reconstruct()
    result = validate(os.environ.get("OUTPUT_DIR", "/app/output"), reference)
    assert result["status"] == "accepted"
