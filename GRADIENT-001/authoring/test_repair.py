import importlib.util
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("gradient_contract", ROOT / "tests/gradient_contract.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
def test_stale_reference_rejected(tmp_path):
    with pytest.raises(AssertionError, match="regenerate"):
        module.validate_evidence(tmp_path, {"schema_version": "v1"})
def test_public_version():
    assert module.VERSION == "gradient-config-v2"
