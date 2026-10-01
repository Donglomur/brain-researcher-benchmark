"""Public, explicitly approximate single-subject inference methods; no max-p rule."""
import numpy as np
from scipy import stats

def circular_null(x, y):
    assert len(x) == len(y) and len(x) > 3
    assert np.isfinite(x).all() and np.isfinite(y).all()
    assert np.std(x) > 0 and np.std(y) > 0
    shifts = np.arange(1, len(x))
    null = np.array([np.corrcoef(np.roll(x, int(k)), y)[0, 1] for k in shifts])
    observed = float(np.corrcoef(x, y)[0, 1])
    p = float((1 + np.count_nonzero(np.abs(null) >= abs(observed))) / len(x))
    return shifts, null, p

def validate_circular(x, y, report):
    shifts, null, p = circular_null(x, y)
    assert report["method"] == "circular_shift_all"
    assert report["shifts"] == shifts.tolist(), "every unique nonzero circular shift required"
    assert np.allclose(report["null_r"], null, atol=1e-7, rtol=0)
    assert np.isclose(report["p_value"], p, atol=1e-7, rtol=0)
    assert report["alpha"] == 0.05 and report["significant"] is (p < 0.05)
    return p
