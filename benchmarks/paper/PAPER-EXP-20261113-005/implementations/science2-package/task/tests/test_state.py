"""Complete scientific outcome verification; no submitted code is imported."""
import json
from pathlib import Path


def test_complete_exact_reconstruction():
    """Every required count and rational moment in all 69 cases must match."""
    # grade.py runs before pytest, so an infrastructure exception cannot be
    # mistaken for an ordinary pytest assertion or partial scientific score.
    result = json.loads(Path("/logs/verifier/adapter-result.json").read_text())
    assert type(result["reward"]) is int
    assert result["reward"] == 1, result.get("status")
