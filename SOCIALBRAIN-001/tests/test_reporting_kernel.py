"""Manufactured-only numerical qualification; no source paths or file reads."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from scipy import stats


SPEC = importlib.util.spec_from_file_location("reporting_kernel_under_test", Path(__file__).with_name("reporting_kernel.py"))
K = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(K)


def clean_fixture(seed=4, n=48):
    rng = np.random.default_rng(seed)
    clean = rng.normal(size=(n, 2, 12))
    clean -= clean.mean(axis=0)
    return clean, np.ones((2, 12), dtype=bool)


def cohort_fixture(n_child=6, n_adult=3):
    ids = [f"child-{i:02}" for i in range(n_child)] + [f"adult-{i:02}" for i in range(n_adult)]
    rng = np.random.default_rng(1842)
    source, masks, covariates = {}, {}, {}
    for i, sid in enumerate(ids):
        signal = rng.normal(size=(48, 2, 12))
        common = rng.normal(size=(48, 2, 1))
        signal += common * (0.1 + i / 8)
        signal -= signal.mean(axis=0)
        source[sid] = signal
        masks[sid] = np.ones((2, 12), dtype=bool)
        covariates[sid] = {"age": float(5 + (i * 3) % 11),
                           "mean_fd": float(0.1 + ((i * 7) % 13) / 100),
                           "group": "child" if i < n_child else "adult"}
    return {"accepted_clean": {sid: x.copy() for sid, x in source.items()},
            "reference_clean": source, "active": masks, "covariates": covariates,
            "subject_ids": ids, "expected_children": n_child, "expected_adults": n_adult}


@pytest.mark.parametrize("bad", [True, [1, True], [[1.0, False]], ["1", "2"],
                                  np.array([1], dtype=object), np.array([1j]),
                                  [np.nan], [np.inf], [-np.inf]])
def test_numeric_types_fail_closed(bad):
    with pytest.raises(ValueError):
        K.real_array(bad)


@pytest.mark.parametrize("dtype", [np.float32, np.float64, np.int16, np.uint16])
def test_real_arrays_canonical_float64_copy(dtype):
    original = np.array([[1, 2], [3, 4]], dtype=dtype)
    result = K.real_array(original, 2)
    assert result.dtype == np.float64 and result.flags.c_contiguous
    result[0, 0] = 99
    assert original[0, 0] == 1


@pytest.mark.parametrize("scale", [1.0, 1e308, 1e-308, np.nextafter(0.0, 1.0)])
def test_stable_signed_zero_pearson_at_extreme_scales(scale):
    x = np.array([-1.0, -1.0, 1.0, 1.0]) * scale
    assert K.pearson(x, x) == pytest.approx(1.0, abs=1e-14)
    assert K.pearson(x, -x) == pytest.approx(-1.0, abs=1e-14)
    assert K.pearson(x, np.array([-1.0, 1.0, -1.0, 1.0]) * scale) == pytest.approx(0.0, abs=1e-14)


@pytest.mark.parametrize("constant", [0.0, 0.1, 1e308, 1e-308])
def test_exact_constant_no_manufactured_direction(constant):
    assert K.pearson(np.full(8, constant), np.arange(8)) is None
    assert not K.residual_active(np.arange(8), np.full(8, constant))


@pytest.mark.parametrize("factor,expected", [(0.0, False), (1e-13, False), (1e-12, False), (2e-12, True), (1.0, True)])
def test_activity_strict_boundary(factor, expected):
    raw = np.array([-1.0, 1.0, -1.0, 1.0])
    assert K.residual_active(raw * factor, raw) is expected


def test_activity_scaled_comparison_does_not_restore_overflowed_norm():
    raw = np.array([-1e308, 1e308, -1e308, 1e308])
    assert K.residual_active(raw * 0.1, raw)
    assert not K.residual_active(raw * 1e-13, raw)
    assert not K.residual_active(np.array([-1e-308, 1e-308] * 2), raw)


def test_relative_fidelity_has_no_absolute_floor_for_tiny_vectors():
    x = np.array([-3.0, -1.0, 1.0, 3.0]) * 1e-300
    assert K.centered_relative_error(x, x) == 0.0
    assert K.validate_continuous_fidelity(x * (1 + 2e-7), x)
    with pytest.raises(ValueError, match="continuous_centered_fidelity"):
        K.validate_continuous_fidelity(x * 2, x)
    assert K.centered_relative_error(np.zeros(4), x) == pytest.approx(1.0, abs=1e-14)


def test_centered_fidelity_allows_constant_offset():
    x = np.array([-2.0, -1.0, 1.0, 2.0])
    assert K.centered_relative_error(x + 4.0, x) < 1e-14
    assert K.validate_continuous_fidelity(x + 4.0, x)


def test_smallest_subnormal_direction_cannot_be_erased_by_unit_scale():
    smallest = np.nextafter(0.0, 1.0)
    source = np.array([0.0, smallest])
    assert K.residual_active(source, source)
    assert K.centered_relative_error(np.zeros(2), source) == pytest.approx(1.0, abs=1e-14)
    with pytest.raises(ValueError, match="continuous_centered_fidelity"):
        K.validate_continuous_fidelity(np.zeros(2), source)


def test_continuous_source_constant_keeps_support_false_despite_jitter():
    source = np.full(6, 0.1)
    observed = source + np.arange(6) * 1e-12
    assert not K.validate_continuous_fidelity(observed, source)
    assert K.centered_relative_error(observed, source) == np.inf


def test_constant_observation_against_subnormal_reference_is_finite_relative_one():
    source = np.array([0.0, np.nextafter(0.0, 1.0)])
    for offset in (0.0, 1.0, 1e308):
        observed = np.full(2, offset)
        with np.errstate(all="raise"):
            assert K.centered_relative_error(observed, source) == 1.0
            with pytest.raises(ValueError, match="continuous_centered_fidelity"):
                K.validate_continuous_fidelity(observed, source)


def test_clean_own_affine_perturbation_passes():
    reference, mask = clean_fixture()
    observed = reference * (1 + 2e-8) + 1e-9
    accepted, canonical, active = K.validate_clean_series(observed, reference, mask)
    assert np.array_equal(accepted, observed)
    assert np.array_equal(canonical, reference)
    assert np.array_equal(active, mask)


def test_inactive_jitter_does_not_activate_or_change_unaffected_family():
    reference, mask = clean_fixture()
    mask[0, 0] = False
    reference[:, 0, 0] = 0
    observed = reference.copy()
    observed[:, 0, 0] = np.linspace(-5e-8, 5e-8, reference.shape[0])
    K.validate_clean_series(observed, reference, mask)
    results = K.participant_metrics(observed, mask)
    assert results["values"]["within_tom"] is None
    assert results["values"]["across_network"] is None
    assert results["statuses"]["within_pain"] == "ok"
    assert results["statuses"]["across_network_gsr"] == "ok"


@pytest.mark.parametrize("change", ["shape", "mask_int", "mask_shape", "nonfinite", "pointwise", "inactive_jitter", "canonical_nonzero", "canonical_active_constant"])
def test_clean_binding_rejects(change):
    reference, mask = clean_fixture()
    observed = reference.copy()
    if change == "shape":
        observed = observed[:-1]
    elif change == "mask_int":
        mask = mask.astype(int)
    elif change == "mask_shape":
        mask = mask[:, :-1]
    elif change == "nonfinite":
        observed[0, 0, 0] = np.nan
    elif change == "pointwise":
        observed[0, 0, 0] += 1e-3
    elif change == "inactive_jitter":
        mask[0, 0] = False
        reference[:, 0, 0] = 0
        observed[:, 0, 0] = 1e-6
    elif change == "canonical_nonzero":
        mask[0, 0] = False
    elif change == "canonical_active_constant":
        reference[:, 0, 0] = 0
        observed[:, 0, 0] = 0
    with pytest.raises(ValueError):
        K.validate_clean_series(observed, reference, mask)


def test_pointwise_close_cannot_erase_tiny_active_direction():
    reference, mask = clean_fixture()
    reference *= 1e-12
    with pytest.raises(ValueError, match="clean_centered_fidelity"):
        K.validate_clean_series(np.zeros_like(reference), reference, mask)


def test_fixed_edges_signed_fisher_and_two_pipeline_identity():
    x = np.array([-1.0, -1.0, 1.0, 1.0] * 4)
    signals = np.empty((x.size, 2, 12))
    signals[:, 0, :6] = x[:, None]
    signals[:, 0, 6:] = -x[:, None]
    signals[:, 1, :] = x[:, None]
    result = K.participant_metrics(signals, np.ones((2, 12), dtype=bool))
    assert [len(K.FAMILIES[name][1]) for name in K.METRICS] == [15, 15, 36, 36]
    assert result["values"]["within_tom"] == pytest.approx(K.FISHER_CAP, abs=1e-14)
    assert result["values"]["within_pain"] == pytest.approx(K.FISHER_CAP, abs=1e-14)
    assert result["values"]["across_network"] == pytest.approx(-K.FISHER_CAP, abs=1e-14)
    assert result["values"]["across_network_gsr"] == pytest.approx(K.FISHER_CAP, abs=1e-14)


def test_fisher_family_replay_against_independent_corrcoef_formula():
    signals, mask = clean_fixture(55)
    result = K.participant_metrics(signals, mask)
    for metric, (arm, pairs) in K.FAMILIES.items():
        correlation = np.corrcoef(signals[:, arm, :].T)
        entries = np.array([correlation[i, j] for i, j in pairs])
        expected = np.tanh(np.mean(np.arctanh(np.clip(entries, -K.FISHER_CAP, K.FISHER_CAP))))
        assert result["values"][metric] == pytest.approx(expected, abs=1e-13)


def test_false_active_constant_is_numerical_failure_not_zero_corr():
    signals, mask = clean_fixture()
    signals[:, 0, 0] = 0.0
    result = K.participant_metrics(signals, mask)
    assert result["values"]["within_tom"] is None
    assert result["statuses"]["within_tom"] == "numerical_failure"


@pytest.mark.parametrize("fd,rank", [([0.1] * 6, 1), ([0, 0, 1, 1, 2, 2], 2), ([1, 2, 3, 4, 5, 6], 2)])
def test_fd_projector_actual_rank_and_df(fd, rank):
    result = K.fd_rank_projector(fd)
    assert result["rank"] == rank
    assert result["df"] == len(fd) - rank - 1
    assert np.max(np.abs(result["basis"].T @ result["basis"] - np.eye(rank))) < 1e-13


@pytest.mark.parametrize("r", [-1.0, 1.0])
def test_perfect_correlation_has_p_zero_without_infinite_receipt(r):
    result = K.correlation_inference(r, 12)
    assert result == {"r": r, "p": 0.0, "status": "perfect_correlation"}


@pytest.mark.parametrize("df", [-2, 0])
def test_insufficient_df_is_null(df):
    assert K.correlation_inference(0.2, df) == {"r": None, "p": None, "status": "insufficient_df"}


@pytest.mark.parametrize("r", [-0.8, 0.0, 0.7])
def test_declared_two_sided_t_approximation(r):
    df = 9
    result = K.correlation_inference(r, df)
    expected = 2 * stats.t.sf(abs(r * np.sqrt(df / (1 - r * r))), df)
    assert result["p"] == pytest.approx(expected, abs=1e-15)
    assert result["status"] == "ok"


@pytest.mark.parametrize("r,df", [(True, 4), (0.3, True), (1.01, 4), (np.inf, 4), ("0.3", 4)])
def test_inference_strict_types_and_domains(r, df):
    with pytest.raises(ValueError):
        K.correlation_inference(r, df)


def test_constant_fd_partial_reduces_to_ordinary_with_correct_df():
    age = [1, 2, 3, 4, 5, 6]
    y = [0.3, 0.1, 0.5, 0.2, 0.8, 0.6]
    result = K.rank_inference(age, y, [0.1] * 6, y)
    assert result["motion_adjusted_nuisance_rank"] == 1
    assert result["df"] == result["motion_adjusted_df"] == 4
    assert result["motion_adjusted_rank_r"] == pytest.approx(result["r"], abs=1e-13)
    assert result["motion_adjusted_rank_p"] == pytest.approx(result["p"], abs=1e-13)


def test_tied_own_values_match_spearman_and_do_not_use_source_rank_gate():
    age = np.arange(1, 7)
    source = np.array([0.1, 0.1, 0.2, 0.3, 0.4, 0.5])
    accepted = source.copy()
    accepted[0] += 1e-9
    own = K.rank_inference(age, accepted, np.ones(6), source)
    canonical = K.rank_inference(age, source, np.ones(6), source)
    assert own["r"] == pytest.approx(stats.spearmanr(age, accepted).statistic, abs=1e-13)
    assert canonical["r"] == pytest.approx(stats.spearmanr(age, source).statistic, abs=1e-13)
    assert abs(own["r"] - canonical["r"]) > 0.01


def test_constant_source_metric_prevents_tolerated_rank_manufacture():
    source = np.full(6, 0.2)
    accepted = source + np.arange(6) * 1e-10
    result = K.rank_inference(np.arange(6), accepted, np.ones(6), source)
    assert result["status"] == result["motion_adjusted_rank_status"] == "constant_source_metric"
    assert result["r"] is None and result["motion_adjusted_rank_r"] is None


def test_constant_age_and_projected_age_have_explicit_null_statuses():
    y = [0.1, 0.3, 0.2, 0.5, 0.6, 0.4]
    constant = K.rank_inference([5] * 6, y, np.arange(6), y)
    assert constant["status"] == constant["motion_adjusted_rank_status"] == "inactive_age_rank"
    projected = K.rank_inference(np.arange(6), y, np.arange(6), y)
    assert projected["r"] is not None
    assert projected["motion_adjusted_rank_status"] == "inactive_age_rank"


def test_projected_connectivity_null_is_own_rank_decision():
    age = [1, 4, 2, 6, 3, 5]
    y = np.arange(6) / 10
    result = K.rank_inference(age, y, np.arange(6), y)
    assert result["r"] is not None
    assert result["motion_adjusted_rank_status"] == "inactive_connectivity_rank"


def test_complete_manufactured_cohort_returns_all_four_metrics_and_groups():
    fixture = cohort_fixture()
    result = K.analyze(**fixture)
    assert len(result["participant_rows"]) == 9
    for name in K.METRICS:
        assert all(row[name + "_status"] == "ok" for row in result["participant_rows"])
        assert result["age_effects"][name]["n_defined"] == 6
        assert result["age_effects"][name]["r"] is not None
        assert result["age_effects"]["adult_support"][name] == {"n_expected": 3, "n_defined": 3, "status": "ok"}
    json.dumps(result, allow_nan=False)


def test_coherent_subject_order_is_not_numeric_authority():
    fixture = cohort_fixture()
    result = K.analyze(**fixture)
    fixture["subject_ids"] = list(reversed(fixture["subject_ids"]))
    permuted = K.analyze(**fixture)
    assert result["age_effects"] == permuted["age_effects"]
    assert {r["subject_id"]: r for r in result["participant_rows"]} == {r["subject_id"]: r for r in permuted["participant_rows"]}


def test_full_cohort_own_affine_series_perturbation_is_replayed():
    fixture = cohort_fixture()
    for sid in fixture["subject_ids"]:
        fixture["accepted_clean"][sid] = fixture["reference_clean"][sid] * (1 + 2e-8) + 1e-9
    result = K.analyze(**fixture)
    assert all(row[name] is not None for row in result["participant_rows"] for name in K.METRICS)


def test_missing_child_metric_never_drops_person_or_edge():
    fixture = cohort_fixture()
    sid = "child-00"
    fixture["active"][sid][0, 0] = False
    fixture["reference_clean"][sid][:, 0, 0] = 0
    fixture["accepted_clean"][sid][:, 0, 0] = 0
    result = K.analyze(**fixture)
    assert len(result["participant_rows"]) == 9
    for name in ("within_tom", "across_network"):
        record = result["age_effects"][name]
        assert record["n_expected"] == 6 and record["n_defined"] == 5
        assert record["status"] == record["motion_adjusted_rank_status"] == "incomplete_subject_support"
        assert record["r"] is None and record["motion_adjusted_rank_r"] is None
    assert result["age_effects"]["within_pain"]["n_defined"] == 6
    assert result["age_effects"]["across_network_gsr"]["n_defined"] == 6


def test_missing_adult_metric_is_complete_group_null_not_nanmean():
    fixture = cohort_fixture()
    sid = "adult-00"
    fixture["active"][sid][1, 0] = False
    fixture["reference_clean"][sid][:, 1, 0] = 0
    fixture["accepted_clean"][sid][:, 1, 0] = 0
    result = K.analyze(**fixture)["age_effects"]
    assert result["adult_means"]["across_network_gsr"] is None
    assert result["adult_support"]["across_network_gsr"] == {"n_expected": 3, "n_defined": 2, "status": "incomplete_subject_support"}
    assert result["adult_means"]["within_tom"] is not None


def test_constant_adult_means_are_legitimate():
    fixture = cohort_fixture()
    same = fixture["reference_clean"]["adult-00"].copy()
    for sid in ("adult-00", "adult-01", "adult-02"):
        fixture["reference_clean"][sid] = same.copy()
        fixture["accepted_clean"][sid] = same.copy()
    result = K.analyze(**fixture)
    adult = next(row for row in result["participant_rows"] if row["subject_id"] == "adult-00")
    for name in K.METRICS:
        assert result["age_effects"]["adult_means"][name] == pytest.approx(adult[name], abs=1e-15)
        assert result["age_effects"]["adult_support"][name]["status"] == "ok"


def test_all_inactive_still_retains_every_subject_and_null_group():
    fixture = cohort_fixture()
    for sid in fixture["subject_ids"]:
        fixture["reference_clean"][sid][:] = 0
        fixture["accepted_clean"][sid][:] = 5e-8
        fixture["active"][sid][:] = False
    result = K.analyze(**fixture)
    assert len(result["participant_rows"]) == 9
    for name in K.METRICS:
        assert result["age_effects"][name]["n_defined"] == 0
        assert result["age_effects"]["adult_support"][name]["n_defined"] == 0
        assert result["age_effects"]["adult_means"][name] is None


@pytest.mark.parametrize("mutation", ["duplicate_id", "missing_id", "extra_mapping", "group_count", "unknown_group", "bool_age", "text_fd", "bool_expected", "zero_expected"])
def test_cohort_identity_and_covariate_types_are_exact(mutation):
    fixture = cohort_fixture()
    if mutation == "duplicate_id":
        fixture["subject_ids"][-1] = fixture["subject_ids"][0]
    elif mutation == "missing_id":
        fixture["accepted_clean"].pop("child-00")
    elif mutation == "extra_mapping":
        fixture["active"]["unexpected"] = np.ones((2, 12), bool)
    elif mutation == "group_count":
        fixture["covariates"]["child-00"]["group"] = "adult"
    elif mutation == "unknown_group":
        fixture["covariates"]["child-00"]["group"] = "Child"
    elif mutation == "bool_age":
        fixture["covariates"]["child-00"]["age"] = True
    elif mutation == "text_fd":
        fixture["covariates"]["child-00"]["mean_fd"] = "0.1"
    elif mutation == "bool_expected":
        fixture["expected_children"] = True
    elif mutation == "zero_expected":
        fixture["expected_children"] = 0
    with pytest.raises(ValueError):
        K.analyze(**fixture)


def test_analysis_does_not_mutate_inputs_or_cache_returned_receipts():
    fixture = cohort_fixture()
    retained = copy.deepcopy(fixture)
    result = K.analyze(**fixture)
    original = result["participant_rows"][0]["within_tom"]
    result["participant_rows"][0]["within_tom"] = 0.987654
    again = K.analyze(**fixture)
    assert again["participant_rows"][0]["within_tom"] == original
    for name in ("accepted_clean", "reference_clean", "active"):
        for sid in fixture["subject_ids"]:
            assert np.array_equal(fixture[name][sid], retained[name][sid])
