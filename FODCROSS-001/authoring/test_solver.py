"""Small solver regression; source-data validation remains a separate gate."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import nnls

spec = importlib.util.spec_from_file_location(
    "fodcross_oracle", Path(__file__).resolve().parents[1] / "solution" / "compute.py")
oracle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oracle)
oracle.check_versions()


@pytest.mark.parametrize("signal_coefficients", [[0.7, -0.3, 1.2], [0.4, 0.8, 0.6], [-0.5, 0.2, 0.9]])
def test_explicit_constrained_qp_agrees_with_independent_nnls(signal_coefficients):
    design = 1000 * np.array([[1., 0., .1], [0., 1., .2], [.1, .2, 1.],
                             [1., .3, 0.], [.2, 0., .8]])
    signal = design @ np.asarray(signal_coefficients)
    reg = np.eye(3)
    fitter = oracle.ExplicitQPFitter(design, reg)
    fitted = fitter(signal)
    independently_fitted, _ = nnls(design, signal)
    np.testing.assert_allclose(fitted, independently_fitted, atol=1e-8, rtol=1e-8)
    assert np.min(reg @ fitted) >= -1e-8
    diag = fitter.diagnostics[0]
    expected = 0.5 * np.sum((design @ independently_fitted)**2) - (design @ independently_fitted) @ signal
    np.testing.assert_allclose(diag["objective"], expected, atol=1e-5, rtol=1e-10)
    assert diag["iterations"] > 0


def test_zero_quadratic_scale_is_rejected():
    with pytest.raises(ValueError, match="positive finite scale"):
        oracle.ExplicitQPFitter(np.zeros((5, 3)), np.eye(3))
