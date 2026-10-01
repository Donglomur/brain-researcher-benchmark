import importlib.util
from pathlib import Path
import pytest
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("emo_sensitivity", ROOT / "tests/sensitivity.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

def test_signed_paired_interval():
    values = np.linspace(-0.3, 0.1, 20)
    summary = m.paired_summary(values)
    assert summary["mean_change"] == pytest.approx(-0.1)
    m.validate_summary(summary, m.paired_summary(values))

@pytest.mark.parametrize("values", [np.zeros(19), np.r_[np.zeros(19), np.nan]])
def test_missing_nonfinite_fail(values):
    with pytest.raises(AssertionError):
        m.paired_summary(values)

def test_fabricated_interval_fails():
    expected = m.paired_summary(np.linspace(-0.3, 0.1, 20))
    actual = dict(expected, ci95=[0.0, 0.0])
    with pytest.raises(AssertionError):
        m.validate_summary(actual, expected)
