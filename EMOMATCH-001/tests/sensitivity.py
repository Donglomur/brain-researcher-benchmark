"""Public paired coefficient-sensitivity summaries, not causal specificity tests."""
import numpy as np
from scipy.stats import t


def paired_summary(values):
    x = np.asarray(values, dtype=float)
    assert x.ndim == 1 and len(x) == 20 and np.isfinite(x).all()
    mean = float(x.mean())
    halfwidth = float(t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x)))
    return {"n": len(x), "mean_change": mean, "ci95": [mean - halfwidth, mean + halfwidth]}


def validate_summary(actual, expected):
    assert actual["n"] == expected["n"]
    assert np.isclose(actual["mean_change"], expected["mean_change"], atol=1e-4, rtol=0)
    assert np.allclose(actual["ci95"], expected["ci95"], atol=1e-4, rtol=0)
