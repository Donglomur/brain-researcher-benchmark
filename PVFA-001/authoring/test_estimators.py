"""Small analytical/synthetic numerical fixtures; never a scientific bank."""
import importlib
from pathlib import Path
import sys

import numpy as np
import pytest
from dipy.core.gradients import gradient_table
from dipy.reconst.dti import design_matrix, wls_fit_tensor
from dipy.reconst.fwdti import wls_iter, nls_iter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"solution"))
import estimators as e


@pytest.fixture
def geometry():
    rng = np.random.RandomState(7)
    directions = rng.normal(size=(16, 3)); directions /= np.linalg.norm(directions, axis=1)[:, None]
    bvals = np.r_[0., np.full(16, 1000.), np.full(16, 2000.)]
    bvecs = np.vstack((np.zeros((1, 3)), directions, directions))
    gtab = gradient_table(bvals, bvecs=bvecs, b0_threshold=50)
    return bvals, bvecs, design_matrix(gtab)


def signal_fixture(design, fraction=.25):
    beta = np.array([.0015, .00005, .00045, -.00003, .00002, .00035, -np.log(1000.)])
    return beta, e.predict(beta, fraction, design)


def test_tensor_roundtrip():
    raw = np.arange(12.).reshape(2, 6)
    assert np.array_equal(e.lower_tensor(e.tensor_matrix(raw)), raw)


def test_eigen_floor_metrics_and_unchanged_raw():
    beta = np.array([.0015, 0., .0005, 0., 0., -.0002, -4.])
    copy = beta.copy(); metrics = e.tensor_metrics(beta, 0.)
    assert metrics["n_eigenvalues_clipped"] == 1
    assert metrics["md"] == pytest.approx(.002/3)
    assert metrics["reported_tensor"][-1] == 0
    assert np.array_equal(beta, copy)


@pytest.mark.parametrize("floor", [0., 1e-10])
def test_zero_tensor_metrics(floor):
    result = e.tensor_metrics(np.zeros(7), floor)
    assert result["fa"] == 0
    assert bool(result["nonzero_tensor"]) == (floor > 0)


@pytest.mark.parametrize("fraction", [0., .3, 1.])
def test_prediction_and_jacobian(geometry, fraction):
    bvals, bvecs, design = geometry
    beta, _ = signal_fixture(design, fraction)
    tensor = e.tensor_matrix(beta)
    adc = np.einsum("ni,ij,nj->n", bvecs, tensor, bvecs)
    independent = np.exp(-beta[6])*((1-fraction)*np.exp(-bvals*adc)+fraction*np.exp(-bvals*.003*np.sum(bvecs*bvecs, axis=1)))
    assert np.allclose(e.predict(beta, fraction, design), independent, atol=1e-12, rtol=1e-12)
    jac = e.prediction_jacobian(beta, fraction, design)
    q = np.r_[beta, fraction]
    steps = np.array([1e-8]*6+[1e-6, 1e-6])
    for index, step in enumerate(steps):
        plus = q.copy(); minus = q.copy(); plus[index] += step; minus[index] -= step
        observed = (e.predict(plus[:7], plus[7], design)-e.predict(minus[:7], minus[7], design))/(2*step)
        assert np.allclose(jac[:, index], observed, atol=2e-4, rtol=3e-7)


def test_initializer_matches_pinned_dipy(geometry):
    bvals, _, design = geometry; _, signal = signal_fixture(design)
    initial = e.fw_initialization(design, signal, signal[0])
    reference = wls_iter(design, signal, signal[0], Diso=.003, mdreg=.0027, min_signal=1e-6, piterations=3)
    vectors = reference[3:12].reshape(3, 3)
    expected_tensor = (vectors*reference[:3]) @ vectors.T
    assert initial["status"] == "ok"
    assert initial["fraction"] == pytest.approx(reference[12], abs=1e-12)
    assert np.allclose(initial["beta"][:6], e.lower_tensor(expected_tensor), atol=1e-12)
    assert initial["beta"][6] == -np.log(signal[0])


def test_actual_tiny_freewater_fit_retains_S0_and_status(geometry):
    bvals, _, design = geometry; _, signal = signal_fixture(design)
    record = e.fit_free_water(signal, design, bvals == 0)
    reference = nls_iter(design, signal, signal[0])
    assert record["status"] == "ok" and record["eligible"]
    assert record["optimizer_status"] in (1, 2, 3, 4) and record["nfev"] > 0
    assert record["f"] == pytest.approx(reference[12], abs=1e-7)
    reference_md = np.mean(reference[:3]); reference_fa = np.sqrt(1.5*np.sum((reference[:3]-reference_md)**2)/np.sum(reference[:3]**2))
    assert record["fa"] == pytest.approx(reference_fa, abs=1e-7)
    assert record["S0_hat"] == pytest.approx(np.exp(-record["beta"][6]))
    assert np.max(np.abs(record["residual"])) < 1e-4
    assert record["scaled_jacobian_singular_values"].shape == (8,)


def test_dti_raw_coefficients_match_dipy(geometry):
    _, _, design = geometry; _, signal = signal_fixture(design)
    signals = np.vstack((signal, signal*1.3, signal*.4))
    signals[2, 3] = 0
    actual = e.dti_wls_beta(signals, design)
    reference, _ = wls_fit_tensor(design, np.maximum(signals, 1e-4), return_lower_triangular=True)
    assert np.allclose(actual, reference, atol=1e-12, rtol=1e-12)


def test_dti_diagnostic_has_only_seven_parameters(geometry):
    bvals, _, design = geometry; _, signal = signal_fixture(design)
    record = e.fit_dti(signal[None], design, bvals == 0)[0]
    assert record["optimizer_status"] is None and record["nfev"] == 0
    assert record["eligible"] and record["f"] == 0
    assert np.isfinite(record["scaled_jacobian_singular_values"][:7]).all()
    assert np.isnan(record["scaled_jacobian_singular_values"][7])
    assert record["jacobian_rank"] <= 7


@pytest.mark.parametrize("signal_value", [0., 1e-7, 1e-6])
def test_low_signal_sentinel_is_not_a_fit(geometry, signal_value):
    bvals, _, design = geometry
    record = e.fit_free_water(np.full(len(bvals), signal_value), design, bvals == 0)
    assert record["status"] == "insufficient_signal"
    assert not record["fit_attempted"] and not record["eligible"]
    assert np.isnan(record["beta"]).all() and np.isnan(record["fa"])


def test_high_MD_sentinel_is_not_tissue_fit(geometry):
    bvals, _, design = geometry
    signal = 1000*np.exp(-bvals*.003)
    record = e.fit_free_water(signal, design, bvals == 0)
    assert record["status"] == "md_threshold"
    assert record["init_f"] == 1 and not record["fit_attempted"]
    assert np.isnan(record["f"]) and np.isnan(record["fa"])


def test_high_fraction_skip_retains_initializer_only(geometry, monkeypatch):
    bvals, _, design = geometry; beta, signal = signal_fixture(design)
    monkeypatch.setattr(e, "fw_initialization", lambda *_: dict(status="high_initial_fraction", md=.001,
        fraction=.995, beta=beta, raw_beta=beta.copy()))
    record = e.fit_free_water(signal, design, bvals == 0)
    assert record["status"] == "high_initial_fraction" and not record["fit_attempted"]
    assert np.isfinite(record["initial_prediction"]).all() and np.isnan(record["beta"]).all()


def test_failed_LM_preserves_candidate_without_eligibility(geometry, monkeypatch):
    bvals, _, design = geometry; _, signal = signal_fixture(design)
    monkeypatch.setattr(e, "leastsq", lambda _, initial, **kwargs: (initial, None, {"nfev": 1800}, "budget exhausted", 5))
    record = e.fit_free_water(signal, design, bvals == 0)
    assert record["status"] == "optimizer_failed" and record["fit_attempted"] and not record["eligible"]
    assert record["optimizer_status"] == 5 and np.isfinite(record["fa"])
    assert np.isfinite(record["prediction"]).all() and record["nfev"] == 1800


@pytest.mark.parametrize("fraction,eligible", [(0., True), (1., False)])
def test_fitted_fraction_boundary_not_confused_with_sentinel(geometry, fraction, eligible):
    bvals, _, design = geometry; beta, signal = signal_fixture(design, fraction)
    record = e.base_record(len(signal)); record.update(status="ok", fit_attempted=True, beta=beta, f=fraction,
        observed_b0=signal[0], normalization_scale=signal[0], optimizer_status=1, nfev=10)
    e.finalize(record, signal, design, 0.)
    assert record["status"] == "ok" and record["eligible"] is eligible


def test_clipping_is_not_additional_exclusion(geometry):
    bvals, _, design = geometry; beta, _ = signal_fixture(design)
    beta[5] = -.0001; signal = e.predict(beta, .1, design)
    record = e.base_record(len(signal)); record.update(status="ok", fit_attempted=True, beta=beta, f=.1,
        observed_b0=signal[0], normalization_scale=signal[0], optimizer_status=1, nfev=10)
    e.finalize(record, signal, design, 0.)
    assert record["n_eigenvalues_clipped"] == 1 and record["eligible"]
    assert not np.allclose(record["prediction"], record["reported_prediction"])


@pytest.mark.parametrize("bad", [np.nan, np.inf, -1.])
def test_invalid_input_preserves_explicit_failure(geometry, bad):
    bvals, _, design = geometry; _, signal = signal_fixture(design); signal[4] = bad
    record = e.fit_free_water(signal, design, bvals == 0)
    assert record["status"] == "invalid_input" and not record["fit_attempted"]


def test_no_decomposition_fallback(geometry, monkeypatch):
    bvals, _, design = geometry; beta, signal = signal_fixture(design)
    record = e.base_record(len(signal)); record.update(status="ok", fit_attempted=True, beta=beta, f=.2,
        observed_b0=signal[0], normalization_scale=signal[0])
    monkeypatch.setattr(np.linalg, "eigh", lambda _: (_ for _ in ()).throw(np.linalg.LinAlgError("forced")))
    e.finalize(record, signal, design, 0.)
    assert record["status"] == "decomposition_failed" and not record["eligible"]
    assert np.array_equal(record["beta"], beta)
