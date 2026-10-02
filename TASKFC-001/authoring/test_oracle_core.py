"""Manufactured only. Import the isolated task oracle; no source data paths."""
import copy
import importlib.util
import math
from pathlib import Path

import numpy as np
import pytest
from nilearn.glm.first_level import make_first_level_design_matrix
from scipy import linalg, stats

SPEC = importlib.util.spec_from_file_location("prospective_taskfc_oracle", Path(__file__).resolve().parents[1] / "solution" / "oracle_core.py")
o = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(o)


def design(n=80, events=None, motion=None):
    if events is None:
        events = [{"trial_type": "language", "onset": 8.0, "duration": 10.0},
                  {"trial_type": "string", "onset": 35.0, "duration": 10.0}]
    if motion is None:
        motion = np.random.default_rng(10).normal(size=(n, 6))
    return o.build_design(n, 1.5, 0.75, events, motion)


def residual_record(correlation=0.5, n=50):
    # Two centered orthonormal manufactured vectors, no fitted/source inputs.
    t = np.arange(n, dtype=float)
    a = np.cos(2*np.pi*t/n); b = np.sin(2*np.pi*t/n)
    a /= np.linalg.norm(a); b /= np.linalg.norm(b)
    partner = correlation*a + math.sqrt(1-correlation**2)*b
    return np.stack((np.column_stack((a, partner)), np.column_stack((a, b))), axis=1)


@pytest.mark.parametrize("bad", [True, [1.0, True], [False, 2], np.array([True, False]), "1.2"])
def test_numeric_types_fail(bad):
    with pytest.raises((ValueError, TypeError)):
        o.array64(bad, 1)


@pytest.mark.parametrize("value", [0.0, 0.1, -3.25, 1e300])
def test_exact_constant_centering(value):
    result = o.centered(np.full(11, value))
    assert result["l2"] == result["sample_sd"] == result["scaled_l2"] == 0
    assert np.array_equal(result["scaled"], np.zeros(11))


def test_scaled_centered_norm_large_finite():
    x = np.array([1e150, -1e150, 0.0, 2e150])
    result = o.centered(x)
    expected = np.linalg.norm(x/1e150-(x/1e150).mean())*1e150
    assert result["l2"] == pytest.approx(expected, rel=1e-14)


def test_l2_preserves_tiny_nonzero_norm():
    assert o.stable_l2(np.array([3e-250, 4e-250])) == pytest.approx(5e-250, rel=1e-14, abs=0)


def test_sphere_exact_radius_includes_boundary():
    supports = o.sphere_support((5, 5, 5), np.eye(4), [(2, 2, 2), (1, 1, 1)], radius=1)
    for center, indices in zip(((2, 2, 2), (1, 1, 1)), supports):
        expected = []
        for ijk in np.ndindex(5, 5, 5):
            if sum((v-c)**2 for v, c in zip(ijk, center)) <= 1:
                expected.append(np.ravel_multi_index(ijk, (5, 5, 5)))
        assert np.array_equal(indices, expected)
        assert len(indices) == 7


def test_sphere_no_nearest_rescue():
    with pytest.raises(ValueError, match="empty_sphere"):
        o.sphere_support((2, 2, 2), np.eye(4), [(0.5, 0.5, 0.5)]*2, radius=0.1)


def test_sphere_fov_truncation_no_brain_mask():
    supports = o.sphere_support((3, 3, 3), np.eye(4), [(0, 0, 0)]*2, radius=1)
    assert len(supports[0]) == 4
    assert np.array_equal(supports[0], supports[1])  # Explicit overlap is allowed.


def test_sphere_flipped_sheared_grid_manual_centers():
    affine = np.array([[-2, 0.5, 0, 7], [0, 2, 0.25, -3], [0, 0, 3, 1], [0, 0, 0, 1.0]])
    centers = [(4, 0, 5), (3, 2, 5)]
    supports = o.sphere_support((4, 4, 4), affine, centers, radius=3)
    for seed, selected in zip(centers, supports):
        expected = []
        for ijk in np.ndindex(4, 4, 4):
            xyz = affine @ np.array([*ijk, 1.0])
            if sum((xyz[k]-seed[k])**2 for k in range(3)) <= 9:
                expected.append(np.ravel_multi_index(ijk, (4, 4, 4)))
        assert np.array_equal(selected, expected)


def test_mean_float64_and_unmeasured_nonfinite():
    volume = np.array([1e8, 1, -1e8, np.nan], dtype=np.float32).reshape(2, 2, 1)
    assert o.voxel_mean(volume, np.array([0, 1, 2])) == pytest.approx(1/3)
    with pytest.raises(ValueError, match="selected_voxels"):
        o.voxel_mean(volume, np.array([0, 3]))


@pytest.mark.parametrize("support", [np.array([1, 0]), np.array([1, 1]), np.array([4]), np.array([True])])
def test_support_key_rejections(support):
    with pytest.raises(ValueError):
        o.voxel_mean(np.ones((2, 2, 1)), support)


def test_clock_design_names_cosine_count_and_source_immutability():
    events = [{"trial_type": "language", "onset": 8., "duration": 5.},
              {"trial_type": "string", "onset": 30., "duration": 5.}]
    before = copy.deepcopy(events)
    motion = np.random.default_rng(1).normal(size=(100, 6)); motion_before = motion.copy()
    result = design(100, events, motion)
    assert result["frame_times"][0] == 0.75
    assert np.array_equal(result["frame_times"], 0.75+1.5*np.arange(100))
    assert result["nuisance_names"] == ("intercept", "drift_1", "drift_2", "drift_3") + o.MOTION_NAMES
    assert result["full_names"][-2:] == ("language", "string")
    assert events == before and np.array_equal(motion, motion_before)


def test_well_conditioned_public_components_match_wrapper():
    import pandas as pd
    events = [{"trial_type": "language", "onset": 8., "duration": 10.},
              {"trial_type": "string", "onset": 35., "duration": 10.}]
    result = design(events=events)
    old = make_first_level_design_matrix(result["frame_times"], pd.DataFrame(events),
                                         hrf_model="glover", drift_model="cosine", high_pass=.01)
    assert np.allclose(result["task_design"], old[["language", "string"]], atol=1e-14, rtol=1e-13)
    drift_names = [name for name in old if name.startswith("drift_")]
    assert np.allclose(result["nuisance_design"][:, 1:1+len(drift_names)], old[drift_names], atol=1e-14)


def test_duplicate_events_preserve_amplitude_multiplicity():
    events = [{"trial_type": "language", "onset": 8., "duration": 10.},
              {"trial_type": "language", "onset": 8., "duration": 10.},
              {"trial_type": "string", "onset": 35., "duration": 10.}]
    duplicates = design(events=events)
    combined = design(events=[dict(events[0], modulation=2.), events[-1]])
    assert np.array_equal(duplicates["task_design"], combined["task_design"])
    assert duplicates["effective_events"][0]["n_source_rows"] == 2


def test_zero_duration_is_retained_and_finite():
    events = [{"trial_type": name, "onset": onset, "duration": 0.}
              for name, onset in zip(o.TASK_NAMES, (10., 35.))]
    result = design(events=events)
    assert np.isfinite(result["task_design"]).all()
    assert np.any(result["task_design"] != 0)


@pytest.mark.parametrize("change", ["condition", "missing_condition", "onset", "duration", "modulation", "bool_onset"])
def test_event_precondition_rejections(change):
    events = [{"trial_type": "language", "onset": 8., "duration": 5.},
              {"trial_type": "string", "onset": 30., "duration": 5.}]
    if change == "condition": events[0]["trial_type"] = "other"
    elif change == "missing_condition": events.pop()
    elif change == "onset": events[0]["onset"] = -24.  # Earlier than .75-24.
    elif change == "duration": events[0]["duration"] = -1.
    elif change == "modulation": events[0]["modulation"] = np.inf
    else: events[0]["onset"] = True
    with pytest.raises(ValueError):
        design(events=events)


@pytest.mark.parametrize("bad", [np.zeros((80, 5)), np.full((80, 6), np.nan)])
def test_motion_not_dropped_or_imputed(bad):
    with pytest.raises(ValueError):
        design(motion=bad)


def test_rank_deficient_projection_no_full_rank_regularization():
    n = 40
    x = np.column_stack((np.ones(n), np.arange(n), 2*np.arange(n), np.zeros(n)))
    y = np.random.default_rng(12).normal(size=(n, 2))
    result = o.fit_residuals(y, x)
    assert result["rank"] == 2 and result["residual_df"] == 38
    expected = y - x @ np.linalg.lstsq(x, y, rcond=max(x.shape)*o.EPS64)[0]
    assert np.allclose(result["residuals"], expected, atol=1e-12, rtol=1e-12)
    assert np.linalg.norm(x.T @ result["residuals"]) < 1e-10


@pytest.mark.parametrize("factor,expected_rank", [(0.5, 1), (1.0, 1), (2.0, 2)])
def test_strict_singular_cutoff_boundary(factor, expected_rank):
    x = np.diag([1., 2*o.EPS64*factor])
    result = o.fit_residuals(np.array([[2., 3.], [4., 7.]]), x)
    assert result["rank"] == expected_rank
    assert result["rank_threshold"] == 2*o.EPS64


def test_zero_design_rank_zero_and_no_coefficient_requirement():
    y = np.random.default_rng(4).normal(size=(30, 2))
    result = o.fit_residuals(y, np.zeros((30, 3)))
    assert result["rank"] == 0 and np.array_equal(result["residuals"], y)


def test_exact_constant_and_projection_jitter_inactive():
    n = 60
    y = np.full((n, 2), 0.1)
    fit = o.fit_residuals(y, np.ones((n, 1)))
    support = o.model_support(fit["residuals"], y)
    assert not support["active"].any()
    jitter = np.column_stack((np.arange(n), -np.arange(n)))*1e-15
    assert not o.model_support(jitter, y)["active"].any()


def test_same_raw_scale_both_models_and_resolvable_signal():
    n = 80
    y = np.column_stack((np.arange(n)*1e8, np.arange(n)))
    a = o.model_support(np.sin(np.arange(n))[:, None]*np.ones((1, 2)), y)
    b = o.model_support(np.cos(np.arange(n))[:, None]*np.ones((1, 2)), y)
    assert np.array_equal(a["activity_threshold"], b["activity_threshold"])
    assert a["active"].all() and b["active"].all()


@pytest.mark.parametrize("r", [-1., -0.5, 0., 0.5, 1.])
def test_unflipped_signed_pearson_and_fisher(r):
    record = residual_record(r)
    actual = o.pearson(record[:, 0, 0], record[:, 0, 1])
    assert actual == pytest.approx(r, abs=2e-15)
    assert o.fisher(actual) == pytest.approx(math.atanh(np.clip(r, -.999, .999)), abs=2e-15)


def test_complete_group_signed_changes_and_input_immutable():
    residuals = [residual_record(r) for r in np.linspace(-.6, .2, 10)]
    before = [r.copy() for r in residuals]
    active = np.ones((10, 2, 2), dtype=bool)
    result = o.derive(residuals, active, [f"person{i}" for i in range(10)])
    deltas = [row["raw_minus_background_z"] for row in result["rows"]]
    summary = result["paired_z_sensitivity"]
    assert summary["status"] == "ok" and summary["mean_raw_minus_background_z"] < 0
    assert summary["mean_raw_minus_background_z"] == pytest.approx(np.mean(deltas), abs=1e-15)
    tt = stats.ttest_1samp(deltas, 0.)
    assert summary["t"] == pytest.approx(tt.statistic, rel=1e-13)
    assert summary["p"] == pytest.approx(tt.pvalue, rel=1e-13)
    assert all(np.array_equal(a, b) for a, b in zip(before, residuals))


def test_one_inactive_model_keeps_other_group_no_omission():
    residuals = [residual_record(.3)]*10
    active = np.ones((10, 2, 2), dtype=bool); active[3, 1, 0] = False
    result = o.derive(residuals, active, [str(i) for i in range(10)])
    assert result["raw"]["status"] == "ok"
    assert result["background"] == dict(status="incomplete_support", n_expected=10, n_defined=9,
                                        mean_z=None, fisher_mean_r=None)
    assert result["rows"][3]["background_status"] == "inactive_left"
    assert result["difference_of_group_fisher_mean_r"] is None
    assert result["paired_z_sensitivity"]["ci95"] is None
    assert result["paired_z_sensitivity"]["n_defined"] == 9
    assert len(result["rows"]) == 10


@pytest.mark.parametrize("delta", [-0.2, 0., 0.2])
def test_constant_difference_point_interval_and_null_t(delta):
    summary = o.paired_summary([delta]*10, 10)
    assert summary["status"] == "zero_variance" and summary["df"] == 9
    assert summary["ci95"] == [summary["mean_raw_minus_background_z"]]*2
    assert summary["t"] is None and summary["p"] is None


def test_pilot_complete_denominator_not_reduced_to_available():
    result = o.derive([residual_record(.5)], np.ones((1, 2, 2), dtype=bool), ["person0"])
    assert result["raw"]["n_defined"] == 1
    assert result["raw"]["fisher_mean_r"] is None
    assert result["paired_z_sensitivity"]["mean_raw_minus_background_z"] is None


def test_canonical_inactive_can_have_finite_rounding_jitter():
    result = o.derive([residual_record(.9)]*10, np.zeros((10, 2, 2), dtype=bool), [str(i) for i in range(10)])
    assert all(row["connectivity"] is None for row in result["rows"])
    assert all(row["raw_status"] == "inactive_both" for row in result["rows"])
    assert result["paired_z_sensitivity"]["n_defined"] == 0


def test_numeric_mask_or_duplicate_person_keys_rejected():
    with pytest.raises(ValueError, match="mask"):
        o.derive([residual_record(.3)]*2, np.ones((2, 2, 2)), ["a", "b"])
    with pytest.raises(ValueError, match="keys"):
        o.derive([residual_record(.3)]*2, np.ones((2, 2, 2), dtype=bool), ["a", "a"])


def test_no_csv_scalar_cascade_api():
    result = o.derive([residual_record(.99900001)]*10, np.ones((10, 2, 2), dtype=bool), [str(i) for i in range(10)])
    expected = result["raw"]["fisher_mean_r"]
    for row in result["rows"]:
        row["connectivity"] = .9989999
    # Display receipts are not an alternate computational input to this replay.
    assert result["raw"]["fisher_mean_r"] == expected
    assert expected == pytest.approx(.999, abs=1e-15)
