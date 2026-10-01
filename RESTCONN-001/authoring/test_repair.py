import importlib.util
from pathlib import Path
import numpy as np
import pytest
ROOT = Path(__file__).resolve().parents[1]
s = importlib.util.spec_from_file_location("inference", ROOT / "tests/inference_contract.py")
m = importlib.util.module_from_spec(s); s.loader.exec_module(m)

def fixture():
    rng = np.random.default_rng(42)
    x = rng.normal(size=32)
    y = x + rng.normal(size=32)
    shifts, null, p = m.circular_null(x, y)
    return x, y, {"method": "circular_shift_all", "shifts": shifts.tolist(),
                 "null_r": null.tolist(), "p_value": p, "alpha": 0.05,
                 "significant": p < 0.05}

def test_honest_unique_shifts():
    x,y,r = fixture()
    m.validate_circular(x,y,r)

@pytest.mark.parametrize("key,value", [("p_value", 0.99), ("shifts", [1]*31),
                                      ("null_r", [0.1]*31)])
def test_fabricated_evidence_fails(key,value):
    x,y,r = fixture(); r[key]=value
    with pytest.raises(AssertionError):
        m.validate_circular(x,y,r)
