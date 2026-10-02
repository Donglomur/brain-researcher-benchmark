"""Manufactured-only qualification; no original/task/bank file access."""
import math

import numpy as np
import pytest
from scipy import stats

import sensitivity_math as m


def toy_residuals(n=64):
    rng = np.random.default_rng(192)
    return rng.normal(size=(n, 2, 2))


def toy_design():
    n = 60
    return dict(frame_times=np.arange(n)*1.5+.75,
                onsets=np.array([3., 30., 45., 60.]), durations=np.array([5., 6., 3., 4.]),
                conditions=np.array(["language", "string", "language", "string"]),
                modulation=np.ones(4), motion=np.random.default_rng(4).normal(size=(n, 6)),
                high_pass=.01, oversampling=50, min_onset=-24.)


@pytest.mark.parametrize("bad", [True, np.bool_(False), "1", None, float("nan"), float("inf")])
def test_scalar_types_reject(bad):
    with pytest.raises(ValueError):
        m.scalar(bad)


@pytest.mark.parametrize("bad", [[1., True], [[1., 2.], [3., False]], np.array([True]),
                                  np.array([1+2j]), np.array(["1"]), np.array([1.], dtype=object),
                                  np.array([np.nan]), np.array([np.inf])])
def test_array_bad_types_and_nonfinite_reject(bad):
    with pytest.raises(ValueError):
        m.array(bad)


@pytest.mark.parametrize("bad", [True, 2., "2", -1, 2**64])
def test_integer_exact_type(bad):
    with pytest.raises(ValueError):
        m.integer(bad)


@pytest.mark.parametrize("value", [0., .1, -2., 1e300])
def test_exact_constants_have_no_fake_activity(value):
    shifted, _ = m.centered_scaled(np.full(31, value))
    assert np.array_equal(shifted, np.zeros(31))
    assert m.centered_l2(np.full(31, value)) == 0.


def test_norm_scaling_is_not_absolute_floor():
    x = np.array([-1e-250, 1e-250])
    assert m.stable_l2(x) == pytest.approx(math.sqrt(2)*1e-250, rel=1e-15, abs=0.)
    assert m.pearson(x, -x) == pytest.approx(-1., abs=1e-15)


def test_design_exact_nested_names_and_original_motion():
    args = toy_design()
    result = m.build_design(**args)
    assert result["nuisance_columns"][0] == "intercept"
    assert result["nuisance_columns"][-6:] == list(m.MOTION)
    assert result["full_columns"][-2:] == ["language", "string"]
    assert np.array_equal(result["nuisance_design"][:, -6:], args["motion"])
    assert np.array_equal(result["full_design"][:, :-2], result["nuisance_design"])
    assert np.array_equal(result["full_design"][:, -2:], result["task_design"])
    assert np.array_equal(result["frame_times"], args["frame_times"])
    assert result["condition_present"].tolist() == [True, True]


def test_zero_amplitude_retains_zero_column_no_regularization():
    args = toy_design()
    args["modulation"][args["conditions"] == "string"] = 0.
    args["motion"][:] = 0.
    result = m.build_design(**args)
    assert np.array_equal(result["task_design"][:, 1], np.zeros(len(args["frame_times"])))
    assert np.array_equal(result["nuisance_design"][:, -6:], np.zeros_like(args["motion"]))
    assert result["condition_present"].tolist() == [True, True]
    # A builder that applies full_rank could change these literal dependent columns.
    assert np.linalg.matrix_rank(result["full_design"]) < result["full_design"].shape[1]


def test_duplicate_event_occurrences_preserved_linearly():
    args = toy_design()
    original = m.build_design(**args)["task_design"]
    for field in ("onsets", "durations", "conditions", "modulation"):
        args[field] = np.concatenate([args[field], args[field]])
    doubled = m.build_design(**args)["task_design"]
    np.testing.assert_allclose(doubled, 2*original, atol=1e-14, rtol=1e-13)


def test_duplicate_amplitudes_use_accurate_sum_and_first_occurrence_order(monkeypatch):
    calls = []
    def sampler(events, model, times, **kwargs):
        calls.append((kwargs["con_id"], tuple(np.asarray(v).copy() for v in events)))
        return np.zeros((len(times), 1)), [kwargs["con_id"]]
    monkeypatch.setattr(m, "compute_regressor", sampler)
    args = toy_design()
    args.update(onsets=np.array([5., 3., 5., 7., 5.]), durations=np.ones(5),
                conditions=np.array(["language", "language", "language", "string", "language"]),
                modulation=np.array([1e16, 4., 1., 2., -1e16]))
    m.build_design(**args)
    assert calls[0][0] == "language" and calls[1][0] == "string"
    np.testing.assert_array_equal(calls[0][1][0], [5., 3.])
    np.testing.assert_array_equal(calls[0][1][2], [1., 4.])


def test_onset_at_exact_declared_sampling_boundary_is_retained():
    args = toy_design()
    args["onsets"][0] = args["frame_times"][0]+args["min_onset"]
    assert m.build_design(**args)["task_design"].shape == (60, 2)


@pytest.mark.parametrize("change", ["clock_duplicate", "motion_missing", "duration_negative",
                                    "unknown_condition", "missing_condition", "early_onset",
                                    "Boolean_modulation", "event_shape"])
def test_design_bad_axes_and_types(change):
    args = toy_design()
    if change == "clock_duplicate": args["frame_times"][1] = args["frame_times"][0]
    if change == "motion_missing": args["motion"] = args["motion"][:, :-1]
    if change == "duration_negative": args["durations"][0] = -1
    if change == "unknown_condition": args["conditions"][0] = "unknown"
    if change == "missing_condition": args["conditions"][:] = "language"
    if change == "early_onset": args["onsets"][0] = args["frame_times"][0]-24.001
    if change == "Boolean_modulation": args["modulation"] = [1., True, 1., 1.]
    if change == "event_shape": args["onsets"] = args["onsets"][:-1]
    with pytest.raises(ValueError):
        m.build_design(**args)


def test_projector_orthogonality_and_numpy_diagnostic_well_conditioned():
    rng = np.random.default_rng(9)
    x, y = rng.normal(size=(48, 5)), rng.normal(size=(48, 2))
    actual = m.fit_residuals(y, x)
    assert actual["design_rank"] == 5 and actual["residual_df"] == 43
    np.testing.assert_allclose(x.T @ actual["residuals"], 0., atol=1e-13, rtol=0.)
    u, s, _ = np.linalg.svd(x, full_matrices=False)
    kept = s > max(x.shape)*m.EPS*s[0]
    diagnostic = y-u[:, kept]@(u[:, kept].T@y)
    np.testing.assert_allclose(actual["residuals"], diagnostic, atol=2e-14, rtol=2e-14)


def test_exact_rank_deficiency_is_valid_projection():
    rng = np.random.default_rng(10)
    base, y = rng.normal(size=(40, 3)), rng.normal(size=(40, 2))
    result = m.fit_residuals(y, np.column_stack([base, base[:, 0], np.zeros(40)]))
    assert result["design_rank"] == 3
    np.testing.assert_allclose(result["residuals"], m.fit_residuals(y, base)["residuals"], atol=1e-13)


def test_input_layout_does_not_change_canonical_computational_arrays():
    rng = np.random.default_rng(77)
    x, y = rng.normal(size=(30, 4)), rng.normal(size=(30, 2))
    first = m.fit_residuals(y, x)
    second = m.fit_residuals(np.asfortranarray(y), np.asfortranarray(x))
    assert np.array_equal(first["residuals"], second["residuals"])
    assert np.array_equal(first["singular_values"], second["singular_values"])


def test_zero_rank_keeps_response():
    y = np.arange(20.).reshape(10, 2)
    result = m.fit_residuals(y, np.zeros((10, 4)))
    assert result["design_rank"] == 0 and result["rank_cutoff"] == 0.
    assert np.array_equal(result["residuals"], y)


def test_rank_cutoff_strict_greater_with_exact_diagonal_tie():
    x = np.diag([1., 8*m.EPS, 4*m.EPS, m.EPS])
    y = np.arange(8.).reshape(4, 2)
    result = m.fit_residuals(y, x)
    assert result["rank_cutoff"] == 4*m.EPS
    assert result["design_rank"] == 2
    np.testing.assert_array_equal(result["residuals"][:2], np.zeros((2, 2)))
    np.testing.assert_array_equal(result["residuals"][2:], y[2:])


def test_no_rejection_when_all_design_directions_exhaust_frames():
    raw = np.arange(12.).reshape(6, 2)
    residual = m.fit_residuals(raw, np.eye(6))["residuals"]
    support = m.source_support(raw, np.stack([residual, residual], axis=1))
    assert not support["active"].any()


@pytest.mark.parametrize("ratio,expected", [(.5, False), (1., False), (2., True)])
def test_activity_strict_boundary_same_raw_scale(ratio, expected):
    raw = np.zeros((2, 2))
    amplitude = m.ACTIVITY_FACTOR*ratio
    residuals = np.tile(np.array([-amplitude, amplitude])[:, None, None], (1, 2, 2))
    support = m.source_support(raw, residuals)
    assert support["active"].tolist() == [[expected, expected], [expected, expected]]
    assert support["raw_sample_sd"].tolist() == [0., 0.]


def test_raw_scale_threshold_is_shared_across_models():
    x = np.arange(20.)*1e6
    raw = np.column_stack([x, -x])
    residuals = toy_residuals(20)
    support = m.source_support(raw, residuals)
    assert support["activity_threshold"].shape == (2,)
    np.testing.assert_allclose(support["activity_threshold"],
        1e-12*math.sqrt(20)*np.std(raw, axis=0, ddof=1), rtol=1e-15)


def test_active_centered_fidelity_has_no_absolute_floor():
    reference = toy_residuals()*1e-10
    actual = reference.copy()
    actual[:, 0, 0] *= 1.01
    with pytest.raises(ValueError, match="centered"):
        m.residual_fidelity(actual, reference, np.ones((2, 2), bool), atol=1e-6, rtol=0.)


def test_source_close_constant_offset_does_not_change_correlation():
    reference = toy_residuals()
    actual = reference+1e-9
    m.residual_fidelity(actual, reference, np.ones((2, 2), bool), atol=1e-7, rtol=1e-7)
    a, b = m.derive_subject(actual, np.ones((2, 2), bool)), m.derive_subject(reference, np.ones((2, 2), bool))
    assert a["connectivity"] == pytest.approx(b["connectivity"], abs=1e-14)


def test_inactive_source_cannot_be_reactivated_by_accepted_jitter():
    reference = np.zeros((40, 2, 2))
    actual = toy_residuals(40)*1e-9
    active = np.zeros((2, 2), bool)
    m.residual_fidelity(actual, reference, active, atol=1e-7, rtol=1e-7)
    result = m.derive_subject(actual, active)
    assert result["connectivity"] is None and result["background_connectivity"] is None
    assert result["raw_status"] == result["background_status"] == "inactive_both"


def test_empty_residual_frames_reject_even_when_inactive():
    with pytest.raises(ValueError, match="axes"):
        m.residual_fidelity(np.zeros((0, 2, 2)), np.zeros((0, 2, 2)),
                            np.zeros((2, 2), bool), atol=1e-6, rtol=1e-6)


@pytest.mark.parametrize("bad", ["shape", "bool", "nonfinite", "large_source_change"])
def test_residual_fidelity_bad_inputs(bad):
    reference = toy_residuals()
    own = reference.copy()
    if bad == "shape": own = own[:, :1]
    if bad == "bool": own = np.ones(reference.shape, dtype=bool)
    if bad == "nonfinite": own[0, 0, 0] = np.nan
    if bad == "large_source_change": own[0, 0, 0] += 1.
    with pytest.raises(ValueError):
        m.residual_fidelity(own, reference, np.ones((2, 2), bool), atol=1e-7, rtol=1e-7)


@pytest.mark.parametrize("right,expected", [[[-3., -1., 1., 3.], 1.],
                                            [[3., 1., -1., -3.], -1.],
                                            [[1., -1., -1., 1.], 0.]])
def test_signed_zero_and_perfect_pearson(right, expected):
    assert m.pearson([-3., -1., 1., 3.], right) == pytest.approx(expected, abs=1e-14)


def test_fisher_clips_z_not_reported_r():
    assert m.fisher(1.) == math.atanh(.999)
    assert m.fisher(-1.) == -math.atanh(.999)
    assert m.fisher(0.) == 0.
    x = np.arange(20.)
    residuals = np.stack([np.column_stack([x, x]), np.column_stack([x, -x])], axis=1)
    result = m.derive_subject(residuals, np.ones((2, 2), bool))
    assert result["connectivity"] == pytest.approx(1., abs=1e-14)
    assert result["raw_minus_background_z"] == pytest.approx(2*math.atanh(.999), abs=1e-14)


@pytest.mark.parametrize("inactive,status", [([False, True], "inactive_left"),
                                            ([True, False], "inactive_right"),
                                            ([False, False], "inactive_both")])
def test_partial_model_support_keeps_other_model(inactive, status):
    active = np.array([inactive, [True, True]], bool)
    result = m.derive_subject(toy_residuals(), active)
    assert result["raw_status"] == status and result["connectivity"] is None
    assert result["background_status"] == "ok" and result["background_connectivity"] is not None
    assert result["raw_minus_background_z"] is None


def test_paired_statistics_match_independent_scipy_summary():
    values = np.array([-.7, .1, -.2, .4, .6, .3, -.1, .9, -.4, .2])
    result = m.paired_summary(values, 10)
    expected = stats.ttest_1samp(values, 0.)
    assert result["t"] == pytest.approx(expected.statistic, abs=1e-14)
    assert result["p"] == pytest.approx(expected.pvalue, abs=1e-14)
    se = stats.sem(values)
    np.testing.assert_allclose(result["ci95"], stats.t.interval(.95, 9, loc=values.mean(), scale=se), atol=1e-14)


@pytest.mark.parametrize("delta", [0., .1, -.5])
def test_zero_variance_point_interval_and_null_test(delta):
    result = m.paired_summary([delta]*10, 10)
    assert result["status"] == "zero_variance" and result["ci95"] == [delta, delta]
    assert result["t"] is None and result["p"] is None
    assert result["standard_error"] == 0. and result["df"] == 9


def test_incomplete_pair_does_not_drop_subject():
    result = m.paired_summary([.1]*9+[None], 10)
    assert result["n_expected"] == 10 and result["n_defined"] == 9
    assert result["status"] == "incomplete_support"
    assert result["mean_raw_minus_background_z"] is None and result["ci95"] is None


@pytest.mark.parametrize("bad", [[.1]*9, [.1]*9+[True], [.1]*9+[np.nan]])
def test_paired_bad_count_and_value_type(bad):
    with pytest.raises(ValueError):
        m.paired_summary(bad, 10)


def test_one_accepted_series_replay_and_id_permutation():
    ids = [f"person-{k:02}" for k in range(10)]
    residuals = {pid: toy_residuals()+i*.01 for i, pid in enumerate(ids)}
    active = {pid: np.ones((2, 2), bool) for pid in ids}
    first = m.derive_cohort(residuals, active, ids)
    second = m.derive_cohort(residuals, active, ids[::-1])
    assert first == second
    expected = [first["per_subject"][pid]["raw_minus_background_z"] for pid in ids]
    assert first["summary"]["paired_z_sensitivity"] == m.paired_summary(expected, 10)


def test_all_ten_equal_people_legitimate():
    ids = [f"person-{k:02}" for k in range(10)]
    residual = toy_residuals()
    result = m.derive_cohort({pid: residual for pid in ids},
                           {pid: np.ones((2, 2), bool) for pid in ids}, ids)
    assert result["summary"]["paired_z_sensitivity"]["status"] == "zero_variance"


def test_inactive_person_nulls_only_affected_complete_groups():
    ids = [f"person-{k:02}" for k in range(10)]
    active = {pid: np.ones((2, 2), bool) for pid in ids}
    active[ids[0]][0, 0] = False
    result = m.derive_cohort({pid: toy_residuals() for pid in ids}, active, ids)["summary"]
    assert result["raw"]["status"] == "incomplete_support" and result["raw"]["n_defined"] == 9
    assert result["background"]["status"] == "ok"
    assert result["paired_z_sensitivity"]["n_defined"] == 9
    assert result["difference_of_group_fisher_mean_r"] is None


def test_literal_complete_participant_membership():
    ids = ["sub-01", "sub-02"]
    residuals = {pid: toy_residuals() for pid in ids}
    active = {pid: np.ones((2, 2), bool) for pid in ids}
    residuals["1"] = residuals.pop("sub-01")
    with pytest.raises(ValueError, match="closed participant"):
        m.derive_cohort(residuals, active, ids)
