"""Bounded numerical unit fixtures, never a scientific task/reference cohort."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("ivim_unit_compute", TASK / "solution/compute.py")
compute = importlib.util.module_from_spec(spec)
spec.loader.exec_module(compute)
B = np.asarray(compute.BVALS, float)


def signal(q=(1.0, 0.1, 0.01, 0.001)):
    return 1000.0 * compute.normalized_prediction(q, B)


def test_explicit_jacobian_matches_independent_central_differences():
    q = np.asarray([1.1, 0.12, 0.018, 0.0012])
    difference = np.empty((len(B), 4))
    for index, step in enumerate((1e-6, 1e-6, 1e-7, 1e-8)):
        above, below = q.copy(), q.copy()
        above[index] += step
        below[index] -= step
        difference[:, index] = (compute.normalized_prediction(above, B) - compute.normalized_prediction(below, B)) / (2*step)
    np.testing.assert_allclose(compute.normalized_jacobian(q, B), difference, atol=1e-6, rtol=1e-6)


def test_component_swap_preserves_signal():
    original = np.asarray([1.2, 0.2, 0.001, 0.02])
    swapped = np.asarray([1.2, 0.8, 0.02, 0.001])
    np.testing.assert_allclose(compute.normalized_prediction(original, B),
                               compute.normalized_prediction(swapped, B), atol=1e-14)


@pytest.mark.parametrize("method", compute.METHODS)
def test_small_noiseless_numerical_fixture(method):
    observed = signal()
    result = compute.fit_voxel(observed, B, 1000.0, True, True, method)
    assert result["status"] == "ok"
    assert result["optimizer_status"] > 0 and result["nfev"] > 0
    assert not result["fallback"]
    s0, fraction, fast, slow = result["params"]
    assert s0 > 0 and 0 < fraction < 1 and 0 <= slow < fast <= 1
    prediction = s0 * (fraction * np.exp(-B*fast) + (1-fraction)*np.exp(-B*slow))
    residual = (prediction-observed)/1000.0
    assert result["nrmse"] == pytest.approx(np.sqrt(np.mean(residual**2)), abs=1e-14)
    fit_mask = np.ones(len(B), bool) if method == "trr_explicit" else B < 200
    assert result["cost"] == pytest.approx(0.5*np.sum(residual[fit_mask]**2), abs=1e-14)
    if method == "trr_explicit":
        np.testing.assert_allclose(result["params"], [1000, .1, .01, .001], rtol=1e-5, atol=1e-8)


@pytest.mark.parametrize("tissue,eligible,status", [
    (False, False, "not_tissue"), (True, False, "invalid_signal"),
])
def test_ineligible_rows_are_retained_without_a_solver(tissue, eligible, status):
    result = compute.fit_voxel(signal(), B, 1000, tissue, eligible, "trr_explicit")
    assert result["status"] == status and result["nfev"] == 0
    assert np.isnan(result["params"]).all()
    assert np.isnan(result["optimizer_status"])


def test_projection_only_changes_initializer(monkeypatch):
    monkeypatch.setattr(compute, "log_linear", lambda y, b, mask: (2.0, -0.1) if mask[-1] else (1.0, 2.0))
    raw, projected = compute.trr_initialization(np.ones(21), B)
    np.testing.assert_allclose(raw, [1, -1, 2, -.1])
    np.testing.assert_allclose(projected, [1, 1e-6, 1-1e-8, 1e-8])


def test_segmented_out_of_bounds_preserves_known_candidates(monkeypatch):
    monkeypatch.setattr(compute, "log_linear", lambda *args: (1.1, 0.001))
    result = compute.fit_voxel(signal(), B, 1000, True, True, "segmented_b200")
    assert result["status"] == "segmented_out_of_bounds"
    assert result["params"][0] == 1000 and result["params"][1] == pytest.approx(-0.1)
    assert np.isnan(result["params"][2]) and result["params"][3] == .001
    assert result["nfev"] == 0 and result["bound_flags"] == "f_lower"
    assert not result["fallback"]


def test_optimizer_failure_keeps_candidate_without_admitting_it(monkeypatch):
    def failed(fun, initial, **kwargs):
        return SimpleNamespace(x=np.asarray(initial), status=0, success=False, nfev=1000,
                               cost=float(np.sum(fun(initial)**2)/2))
    monkeypatch.setattr(compute, "least_squares", failed)
    result = compute.fit_voxel(signal(), B, 1000, True, True, "trr_explicit")
    assert result["status"] == "optimizer_failed" and not result["fallback"]
    assert np.isfinite(result["params"]).all() and np.isfinite(result["nrmse"])
    assert result["nfev"] == 1000


def test_converged_reversed_components_are_canonicalized(monkeypatch):
    def swapped(fun, initial, **kwargs):
        candidate = np.asarray([1, .2, .001, .02])
        return SimpleNamespace(x=candidate, status=1, success=True, nfev=5,
                               cost=float(np.sum(fun(candidate)**2)/2))
    monkeypatch.setattr(compute, "least_squares", swapped)
    result = compute.fit_voxel(signal(), B, 1000, True, True, "trr_explicit")
    assert result["status"] == "ok" and result["component_swap"]
    np.testing.assert_allclose(result["params"], [1000, .8, .02, .001])


def test_degenerate_components_are_not_admitted(monkeypatch):
    def degenerate(fun, initial, **kwargs):
        candidate = np.asarray([1, .2, .001, .001])
        return SimpleNamespace(x=candidate, status=1, success=True, nfev=5,
                               cost=float(np.sum(fun(candidate)**2)/2))
    monkeypatch.setattr(compute, "least_squares", degenerate)
    result = compute.fit_voxel(signal(), B, 1000, True, True, "trr_explicit")
    assert result["status"] == "degenerate_or_unordered"
    assert "Dstar_D_lower" in result["bound_flags"]


def test_public_serialization_uses_empty_and_null_not_nonstandard_json(tmp_path):
    compute.write_csv(tmp_path/"rows.csv", ["missing", "flag"], [[np.nan, True]])
    assert (tmp_path/"rows.csv").read_text().splitlines()[1] == ",true"
    compute.write_json(tmp_path/"empty.json", {"mean": None})
    assert json.loads((tmp_path/"empty.json").read_text()) == {"mean": None}
    with pytest.raises(ValueError):
        compute.write_json(tmp_path/"invalid.json", {"mean": float("nan")})
