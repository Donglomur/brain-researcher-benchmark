"""Manufactured-only DEVCONN qualification; no sources, banks, or file outputs."""
import copy
import importlib.util
from pathlib import Path

import numpy as np
import pytest
from scipy import stats

SPEC = importlib.util.spec_from_file_location("devconn_reporting_under_test", Path(__file__).with_name("reporting_kernel.py"))
K = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(K)


def bins_fixture():
    coords = np.column_stack(([0., 1., 3., 7., 15., 31.], np.zeros(6), np.zeros(6)))
    return K.distance_bins(coords, [f"roi-{i}" for i in range(6)])


def clean_fixture(seed=7):
    y = np.random.default_rng(seed).normal(size=(40, 6))
    return y - y.mean(axis=0), np.ones(6, dtype=bool)


def cohort_fixture():
    ids = [f"child-{i:02}" for i in range(6)] + [f"adult-{i:02}" for i in range(3)]
    source, masks, covariates = {}, {}, {}
    rng = np.random.default_rng(1907)
    for i, sid in enumerate(ids):
        y = rng.normal(size=(40, 6)) + rng.normal(size=(40, 1)) * (.1 + i / 8)
        source[sid] = y - y.mean(axis=0)
        masks[sid] = np.ones(6, dtype=bool)
        covariates[sid] = {"age": float(5 + i * 3 % 11),
                           "mean_fd": [0.19, .2, .21, .01, .15, .24, .1, .2, .05][i],
                           "group": "child" if i < 6 else "adult"}
    return {"accepted_clean": {s: y.copy() for s, y in source.items()},
            "reference_clean": source, "active": masks, "covariates": covariates,
            "subject_ids": ids, "coordinates": np.column_stack(([0., 1., 3., 7., 15., 31.], np.zeros(6), np.zeros(6))),
            "roi_ids": [f"roi-{i}" for i in range(6)],
            "expected_children": 6, "expected_adults": 3, "expected_rois": 6}


@pytest.mark.parametrize("bad", [True, [1, True], [[1., False]], ["1", "2"],
                                  np.array([1], object), [1j], [np.nan], [np.inf], [-np.inf]])
def test_strict_real_inputs(bad):
    with pytest.raises(ValueError):
        K.real_array(bad)


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int16, np.uint16])
def test_real_copy_dtype(dtype):
    original = np.array([[1, 2], [3, 4]], dtype=dtype)
    actual = K.real_array(original, 2)
    assert actual.dtype == np.float64 and actual.flags.c_contiguous
    actual[0, 0] = 99
    assert original[0, 0] == 1


@pytest.mark.parametrize("scale", [1., 1e308, 1e-308, np.nextafter(0., 1.)])
def test_matrix_and_scalar_signed_pearson_at_extreme_scales(scale):
    x = np.array([-1., -1., 1., 1.]) * scale
    y = np.array([-1., 1., -1., 1.]) * scale
    matrix, defined = K.correlation_matrix(np.column_stack((x, -x, y)), np.ones(3, bool))
    assert defined.all()
    assert matrix[0, 1] == pytest.approx(-1., abs=1e-14)
    assert matrix[0, 2] == pytest.approx(0., abs=1e-14)
    assert K.pearson(x, -x) == pytest.approx(-1., abs=1e-14)


@pytest.mark.parametrize("constant", [0., .1, 1e308, 1e-308])
def test_constants_do_not_manufacture_direction(constant):
    assert K.pearson(np.full(8, constant), np.arange(8)) is None
    assert not K.residual_active(np.arange(8), np.full(8, constant))


@pytest.mark.parametrize("factor,expected", [(0., False), (1e-13, False), (1e-12, False), (2e-12, True), (1., True)])
def test_activity_boundary(factor, expected):
    x = np.array([-1., 1., -1., 1.])
    assert K.residual_active(x * factor, x) is expected


def test_subnormal_relative_fidelity_and_constant_offset():
    source = np.array([0., np.nextafter(0., 1.)])
    with np.errstate(all="raise"):
        assert K.centered_relative_error(np.ones(2), source) == 1.
    x = np.array([-2., -1., 1., 2.])
    assert K.validate_continuous_fidelity(x + 4, x)
    with pytest.raises(ValueError, match="continuous_centered_fidelity"):
        K.validate_continuous_fidelity(x * 2, x)


def test_clean_affine_change_allowed_but_erasing_tiny_direction_rejected():
    source, mask = clean_fixture()
    K.validate_clean_series(source * (1 + 2e-8) + 1e-9, source, mask)
    with pytest.raises(ValueError, match="clean_centered_fidelity"):
        K.validate_clean_series(np.zeros_like(source), source * 1e-12, mask)


@pytest.mark.parametrize("mutation", ["shape", "mask_int", "mask_shape", "nonfinite", "pointwise", "canonical_nonzero", "active_constant"])
def test_clean_binding_failures(mutation):
    source, mask = clean_fixture()
    observed = source.copy()
    if mutation == "shape": observed = observed[:-1]
    elif mutation == "mask_int": mask = mask.astype(int)
    elif mutation == "mask_shape": mask = mask[:-1]
    elif mutation == "nonfinite": observed[0, 0] = np.nan
    elif mutation == "pointwise": observed[0, 0] += .01
    elif mutation == "canonical_nonzero": mask[0] = False
    elif mutation == "active_constant": source[:, 0] = observed[:, 0] = 0
    with pytest.raises(ValueError): K.validate_clean_series(observed, source, mask)


def test_strict_bin_ties_are_neither_filled_nor_rebalanced():
    bins = K.distance_bins(np.column_stack((np.arange(4), np.zeros(4), np.zeros(4))), list("abcd"))
    assert bins["q1_mm"] == 1 and bins["q2_mm"] == 2
    assert bins["short_range"].sum() == 0 and bins["long_range"].sum() == 1
    assert np.array_equal(bins["pairs"], np.column_stack(np.triu_indices(4, 1)))
    collapsed = K.distance_bins(np.zeros((4, 3)), list("abcd"))
    assert not collapsed["short_range"].any() and not collapsed["long_range"].any()


def test_264_canonical_geometry_has_all_34716_pairs():
    bins = K.distance_bins(np.column_stack((np.arange(264), np.zeros(264), np.zeros(264))), [str(i) for i in range(264)])
    assert bins["n_pairs"] == 34716 and bins["pairs"].shape == (34716, 2)


@pytest.mark.parametrize("mutation", ["bool", "shape", "duplicate", "numeric_id", "nonfinite"])
def test_geometry_types(mutation):
    coords = np.zeros((3, 3)); ids = list("abc")
    if mutation == "bool": coords = np.ones((3, 3), bool)
    elif mutation == "shape": coords = coords[:, :2]
    elif mutation == "duplicate": ids[-1] = ids[0]
    elif mutation == "numeric_id": ids[0] = 1
    elif mutation == "nonfinite": coords[0, 0] = np.inf
    with pytest.raises(ValueError): K.distance_bins(coords, ids)


def test_fisher_z_is_signed_untransformed_mean_not_tanh_or_mean_r():
    source, active = clean_fixture()
    bins = bins_fixture()
    actual = K.participant_metrics(source, active, bins)
    i, j = bins["pairs"].T
    z = np.arctanh(np.clip(np.corrcoef(source.T)[i, j], -.999, .999))
    for name in K.METRICS[:2]:
        assert actual["values"][name] == pytest.approx(z[bins[name]].mean(), abs=1e-13)
    same = np.tile(np.array([-1., -1., 1., 1.])[:, None], (1, 6))
    perfect = K.participant_metrics(same, active, bins)
    assert perfect["values"]["short_range"] == pytest.approx(np.arctanh(.999), abs=1e-14)
    assert perfect["values"]["short_range"] > 1
    assert perfect["values"]["segregation"] == 0


def test_canonical_eligible_edges_no_coverage_floor_no_jitter_reactivation():
    x = np.array([-1., -1., 1., 1.] * 5)
    reference = np.zeros((20, 6)); reference[:, 0] = x; reference[:, 5] = -x
    mask = np.array([True, False, False, False, False, True])
    observed = reference.copy(); observed[:, ~mask] = np.linspace(-5e-8, 5e-8, 20)[:, None]
    K.validate_clean_series(observed, reference, mask)
    result = K.participant_metrics(observed, mask, bins_fixture())
    assert result["values"]["short_range"] is None
    assert result["values"]["long_range"] == pytest.approx(-np.arctanh(.999), abs=1e-14)
    assert result["edge_counts"]["long_range"]["n_used_edges"] == 1
    assert result["statuses"]["segregation"] == "incomplete_edge_families"


def test_active_constant_is_unavailable_not_silently_removed():
    source, mask = clean_fixture(); source[:, 0] = 0
    result = K.participant_metrics(source, mask, bins_fixture())
    assert result["statuses"]["short_range"] == "numerical_failure"
    assert result["edge_counts"]["short_range"]["n_used_edges"] == result["edge_counts"]["short_range"]["n_nominal_edges"]


def test_correlation_roundoff_budget():
    assert np.array_equal(K.checked_correlations([1 + 5e-13, -1 - 5e-13]), [1., -1.])
    assert K.checked_correlations([1 + 2e-12]) is None


@pytest.mark.parametrize("fd,rank", [([.1] * 6, 1), ([0, 0, 1, 1, 2, 2], 2)])
def test_actual_fd_rank_and_df(fd, rank):
    result = K.fd_rank_projector(fd)
    assert result["rank"] == rank and result["df"] == 6 - rank - 1


@pytest.mark.parametrize("r", [-1., 1.])
def test_perfect_correlation_keeps_p_zero(r):
    assert K.correlation_inference(r, 9) == {"r": r, "p": 0., "status": "perfect_correlation"}


@pytest.mark.parametrize("r,df", [(True, 4), (.2, True), (1.01, 4), (np.inf, 4)])
def test_inference_types(r, df):
    with pytest.raises(ValueError): K.correlation_inference(r, df)


def test_rank_constants_ties_and_own_perturbed_ranks():
    age = np.arange(6); source = np.array([.1, .1, .2, .3, .4, .5]); own = source.copy(); own[0] += 1e-9
    result = K.rank_inference(age, own, np.ones(6), source)
    assert result["r"] == pytest.approx(stats.spearmanr(age, own).statistic, abs=1e-13)
    assert result["motion_adjusted_rank_r"] == pytest.approx(result["r"], abs=1e-13)
    assert result["motion_adjusted_df"] == result["df"] == 4
    assert abs(result["r"] - K.rank_inference(age, source, np.ones(6), source)["r"]) > .01
    flat = K.rank_inference(age, np.arange(6) * 1e-10 + .2, np.ones(6), np.full(6, .2))
    assert flat["r"] is None and flat["status"] == "constant_source_metric"


def test_unsupported_partial_ranks_are_explicit():
    age = np.arange(6); y = [.1, .3, .2, .5, .6, .4]
    assert K.rank_inference(age, y, age, y)["motion_adjusted_rank_status"] == "inactive_age_rank"
    assert K.rank_inference(y, age, age, age)["motion_adjusted_rank_status"] == "inactive_connectivity_rank"
    assert K.rank_inference([5] * 6, y, np.ones(6), y)["status"] == "inactive_age_rank"
    assert K.correlation_inference(.5, 0)["status"] == "insufficient_df"


def test_exact_bootstrap_index_draw_consumption():
    actual = K.bootstrap_indices(6)
    rng = np.random.default_rng(11)
    expected = np.stack([rng.integers(0, 6, 6) for _ in range(1000)])
    assert np.array_equal(actual, expected) and actual.shape == (1000, 6)
    assert np.any([len(set(row)) < 6 for row in actual])


def test_complete_or_null_linear_percentiles():
    values = np.linspace(-1, 1, 1000); defined = np.ones(1000, bool)
    result = K.percentile_interval(values, defined)
    assert result["ci95"] == pytest.approx(np.quantile(values, [.025, .975], method="linear"))
    defined[91] = False
    result = K.percentile_interval(values, defined)
    assert result["ci95"] is None and result["n_defined"] == 999 and result["n_expected"] == 1000


def test_bootstrap_constant_resamples_retained_despite_accepted_jitter():
    source = np.array([0., 0., 1., 2.]); own = source.copy(); own[0] = 1e-10
    result = K.child_estimates(np.arange(4), {m: own for m in K.METRICS}, np.ones(4), {m: source for m in K.METRICS})
    receipt = result["bootstrap"]
    draws = np.all(receipt["indices"] < 2, axis=1)
    assert draws.any()
    assert not receipt["defined"][draws].any()
    assert np.all(receipt["status"][draws] == "constant_source_metric")
    for m in K.METRICS:
        assert result["effects"][m]["raw_bootstrap"]["ci95"] is None


def test_per_resample_continuous_fidelity_is_not_only_full_sample_guard():
    source = np.array([0., 1e-12, 1.]); own = source.copy(); own[0] = 1e-9
    assert K.validate_continuous_fidelity(own, source)
    with pytest.raises(ValueError, match="continuous_centered_fidelity"):
        K.child_estimates(np.arange(3), {m: own for m in K.METRICS}, np.ones(3), {m: source for m in K.METRICS})


@pytest.mark.parametrize("left,right", [([1., 2., 4.], [2., 5., 8., 9.]), ([.1] * 3, [0., 1., 2., 3.])])
def test_welch_matches_independent_scipy_including_one_zero_variance(left, right):
    actual = K.welch_groups(left, right, left, right); expected = stats.ttest_ind(left, right, equal_var=False)
    assert actual["status"] == "ok"
    assert actual["t"] == pytest.approx(expected.statistic, abs=1e-13)
    assert actual["p"] == pytest.approx(expected.pvalue, abs=1e-13)
    assert actual["df"] == pytest.approx(expected.df, abs=1e-13)


@pytest.mark.parametrize("left,right", [([.1] * 3, [.1] * 4), ([.1] * 3, [.3] * 4)])
def test_zero_se_keeps_means_and_difference_without_invented_inference(left, right):
    result = K.welch_groups(left, right, left, right)
    assert result["status"] == "zero_standard_error"
    assert result["t"] is result["p"] is result["df"] is None
    assert result["difference"] == pytest.approx(left[0] - right[0], abs=1e-15)


@pytest.mark.parametrize("left,right,status", [([], [1., 2.], "incomplete_subject_support"),
    ([1., None, 3.], [1., 2.], "incomplete_subject_support"), ([1.], [1., 2.], "insufficient_group_size"),
    ([0., 1e-200], [0., 2e-200], "numerical_underflow"), ([-1e308, 1e308], [-1e308, 1e308], "numerical_overflow")])
def test_welch_unavailable_reasons(left, right, status):
    result = K.welch_groups(left, right, left, right)
    assert result["status"] == status and result["t"] is result["p"] is None


def test_source_constant_groups_cannot_gain_welch_support_from_admitted_jitter():
    left_source = np.full(3, .1); right_source = np.full(4, .3)
    left = left_source + np.array([1., 2., 4.]) * 1e-10
    right = right_source + np.array([-2., -1., 3., 5.]) * 1e-10
    result = K.welch_groups(left, right, left_source, right_source)
    assert result["status"] == "zero_standard_error"
    assert result["t"] is result["p"] is result["df"] is None
    assert result["child"]["mean"] == K.complete_mean(left)["mean"]
    assert result["adult"]["mean"] == K.complete_mean(right)["mean"]
    assert result["difference"] != K.complete_mean(left_source)["mean"] - K.complete_mean(right_source)["mean"]


def test_one_source_constant_group_uses_zero_variance_but_own_mean():
    left_source = np.full(3, .1); right_source = np.array([.2, .3, .5, .7])
    left = left_source + np.array([1., 2., 4.]) * 1e-10
    right = right_source * (1 + 2e-7) + 2e-8
    result = K.welch_groups(left, right, left_source, right_source)
    mean_left = K.complete_mean(left)["mean"]
    mean_right = K.complete_mean(right)["mean"]
    expected_t = (mean_left - mean_right) / np.sqrt(np.var(right, ddof=1) / len(right))
    assert result["status"] == "ok"
    assert result["t"] == pytest.approx(expected_t, abs=1e-13)
    assert result["df"] == pytest.approx(len(right) - 1, abs=1e-13)


def test_nonconstant_welch_groups_allow_source_close_affine_values_and_replay_own():
    left_source = np.array([.1, .4, .2]); right_source = np.array([.3, .6, .7, .2])
    left = left_source * (1 + 2e-7) + 2e-8
    right = right_source * (1 - 2e-7) - 1e-8
    result = K.welch_groups(left, right, left_source, right_source)
    expected = stats.ttest_ind(left, right, equal_var=False)
    assert result["status"] == "ok"
    assert result["t"] == pytest.approx(expected.statistic, abs=1e-13)
    assert result["p"] == pytest.approx(expected.pvalue, abs=1e-13)


@pytest.mark.parametrize("side", [0, 1])
def test_each_nonconstant_welch_group_has_relative_conditioning(side):
    canonical = [np.array([0., 1., 3.]) * 1e-12, np.array([2., 4., 5.]) * 1e-12]
    own = [v.copy() for v in canonical]
    own[side] *= 2
    # Tiny absolute changes would pass a fixed absolute scalar tolerance, but
    # cannot double a canonical nonconstant group's variance direction.
    with pytest.raises(ValueError, match="continuous_centered_fidelity"):
        K.welch_groups(own[0], own[1], canonical[0], canonical[1])


def test_restricted_constant_subset_does_not_inherit_full_group_variance():
    left_source = np.array([.1, .1, .1, .5]); right_source = np.array([.3, .3, .3, .8])
    left = left_source + np.array([1., 2., 3., 0.]) * 1e-10
    right = right_source + np.array([-2., 1., 2., 0.]) * 1e-10
    full = K.welch_groups(left, right, left_source, right_source)
    restricted = K.welch_groups(left[:3], right[:3], left_source[:3], right_source[:3])
    assert full["status"] == "ok"
    assert restricted["status"] == "zero_standard_error" and restricted["t"] is None


def test_analyze_passes_canonical_full_and_restricted_variance_support():
    fixture = cohort_fixture()
    same = fixture["reference_clean"]["child-00"].copy()
    for i, sid in enumerate(fixture["subject_ids"]):
        fixture["reference_clean"][sid] = same.copy()
        own = same.copy()
        own[:, 0] += (i + 1) * 1e-9 * same[:, 1]
        fixture["accepted_clean"][sid] = own
    result = K.analyze(**fixture)
    # Accepted signals genuinely perturb the scalar receipts; their canonical
    # constant group support must still govern the two Welch variance arms.
    assert len({row["segregation"] for row in result["participant_rows"]}) > 1
    effects = result["age_effects"]
    for record in (effects["segregation_child_vs_adult"],
                   effects["motion_control"]["segregation_low_motion_restriction"]):
        assert record["status"] == "zero_standard_error"
        assert record["t"] is record["p"] is record["df"] is None


def test_welch_canonical_membership_and_missing_support_are_required():
    with pytest.raises(ValueError, match="welch_canonical_shape"):
        K.welch_groups([1., 2.], [3., 4.], [1.], [3., 4.])
    with pytest.raises(ValueError, match="canonical_metric_missing"):
        K.welch_groups([1., 2.], [3., 4.], [1., None], [3., 4.])


def test_complete_cohort_replay_reordering_and_strict_restriction():
    fixture = cohort_fixture(); retained = copy.deepcopy(fixture)
    result = K.analyze(**fixture)
    assert len(result["participant_rows"]) == 9
    low = result["age_effects"]["motion_control"]["segregation_low_motion_restriction"]
    assert low["child_ids"] == ["child-00", "child-03", "child-04"]
    assert low["adult_ids"] == ["adult-00", "adult-02"]
    assert low["fd_thresh"] == .2 and low["status"] == "ok"
    assert result["bootstrap"]["r"].shape == (1000, 3, 2)
    assert result["bootstrap"]["defined"].dtype.kind == "b"
    fixture["subject_ids"].reverse()
    again = K.analyze(**fixture)
    assert again["age_effects"] == result["age_effects"]
    assert again["participant_rows"] == result["participant_rows"]
    assert np.array_equal(again["bootstrap"]["indices"], result["bootstrap"]["indices"])
    for kind in ("accepted_clean", "reference_clean", "active"):
        for sid in retained["subject_ids"]: assert np.array_equal(fixture[kind][sid], retained[kind][sid])


def test_coherent_own_affine_series_and_roi_axis_permutation():
    fixture = cohort_fixture(); permutation = [5, 3, 1, 4, 0, 2]
    baseline = K.analyze(**fixture)
    for sid in fixture["subject_ids"]:
        fixture["accepted_clean"][sid] = (fixture["accepted_clean"][sid] * (1 + 2e-8) + 1e-9)[:, permutation]
        fixture["reference_clean"][sid] = fixture["reference_clean"][sid][:, permutation]
        fixture["active"][sid] = fixture["active"][sid][permutation]
    fixture["coordinates"] = fixture["coordinates"][permutation]
    fixture["roi_ids"] = [fixture["roi_ids"][i] for i in permutation]
    result = K.analyze(**fixture)
    for original, accepted in zip(baseline["participant_rows"], result["participant_rows"]):
        for m in K.METRICS: assert accepted[m] == pytest.approx(original[m], abs=1e-13)


def test_incomplete_subject_retained_without_available_case_group_mean():
    fixture = cohort_fixture(); sid = "child-00"
    fixture["reference_clean"][sid][:] = 0; fixture["accepted_clean"][sid][:] = 5e-8; fixture["active"][sid][:] = False
    result = K.analyze(**fixture)
    for m in K.METRICS:
        record = result["age_effects"]["children_age_spearman"][m]
        assert record["n_expected"] == 6 and record["n_defined"] == 5 and record["r"] is None
        assert result["age_effects"]["group_means"][m]["child"]["mean"] is None
        assert result["age_effects"]["group_means"][m]["adult"]["mean"] is not None
    assert len(result["participant_rows"]) == 9
    assert not result["bootstrap"]["defined"][np.any(result["bootstrap"]["indices"] == 0, axis=1)].any()


@pytest.mark.parametrize("inactive", [False, True])
def test_constant_or_all_inactive_cohort_has_honest_complete_nulls(inactive):
    fixture = cohort_fixture()
    same = fixture["reference_clean"]["child-00"].copy()
    if inactive: same[:] = 0
    for sid in fixture["subject_ids"]:
        fixture["reference_clean"][sid] = same.copy()
        fixture["accepted_clean"][sid] = same.copy()
        fixture["active"][sid][:] = not inactive
    result = K.analyze(**fixture)
    assert not result["bootstrap"]["defined"].any()
    for metric in K.METRICS:
        effect = result["age_effects"]["children_age_spearman"][metric]
        assert effect["r"] is effect["motion_adjusted_rank_r"] is None
        expected = "incomplete_subject_support" if inactive else "constant_source_metric"
        assert effect["status"] == expected
        group = result["age_effects"]["group_means"][metric]["adult"]
        assert (group["mean"] is None) is inactive
    expected_welch = "incomplete_subject_support" if inactive else "zero_standard_error"
    assert result["age_effects"]["segregation_child_vs_adult"]["status"] == expected_welch


@pytest.mark.parametrize("mutation", ["id", "missing", "groups", "fd_bool", "fd_negative", "age_text", "roi_count", "bool_expected"])
def test_input_identity_domains_fail_before_bootstrap(mutation):
    fixture = cohort_fixture()
    if mutation == "id": fixture["subject_ids"][-1] = fixture["subject_ids"][0]
    elif mutation == "missing": fixture["active"].pop("child-00")
    elif mutation == "groups": fixture["covariates"]["child-00"]["group"] = "adult"
    elif mutation == "fd_bool": fixture["covariates"]["child-00"]["mean_fd"] = True
    elif mutation == "fd_negative": fixture["covariates"]["child-00"]["mean_fd"] = -.1
    elif mutation == "age_text": fixture["covariates"]["child-00"]["age"] = "7"
    elif mutation == "roi_count": fixture["expected_rois"] = 264
    elif mutation == "bool_expected": fixture["expected_children"] = True
    with pytest.raises(ValueError): K.analyze(**fixture)
