"""Manufactured-only qualification; no sources, files, banks or model outputs."""
import copy
import json
import math

import numpy as np
import pytest
from scipy import stats

from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1] / 'environment'))

import statistics_kernel as k


def rows(n_sites=3, per_site=6):
    result = []
    for s in range(n_sites):
        for j in range(per_site):
            index = s * per_site + j
            result.append(dict(subject=f"site{s}_person{j:04d}", age=12. + 7*s + j,
                               site_id=f"site{s}", connectivity=.03*s + .004*j + .02*math.sin(1.7*index),
                               mean_fd=.1 + .008*j + .004*math.cos(index), sex=j % 2,
                               typical_control=(j % 3 != 0)))
    return result


def accepted(data):
    return {r["subject"]: r["connectivity"] for r in data}


@pytest.mark.parametrize("value", [True, np.bool_(False), "1", None, float("nan"), float("inf"), 1+0j])
def test_reject_invalid_scalar(value):
    with pytest.raises(ValueError):
        k.real(value)


@pytest.mark.parametrize("value", [[1, True], [np.bool_(True), 2], np.array([True, False]),
                                  np.array([1, 2], dtype=object), [1+0j, 2+0j], [1, np.nan]])
def test_reject_invalid_numeric_vector(value):
    with pytest.raises(ValueError):
        k.array(value, 1)


def test_float32_numeric_input_and_exact_constant_center():
    x = np.full(19, .1, dtype=np.float32)
    assert np.array_equal(k.center(x), np.zeros(19))
    assert k.stable_norm(k.center(x)) == 0


@pytest.mark.parametrize("scale", [1e-300, 1., 1e300])
def test_stable_pearson_scaling(scale):
    x = scale * np.array([-3., -1., 0., 1., 4.])
    y = scale * np.array([2., -1., 4., 0., -2.])
    expected = stats.pearsonr(np.array([-3., -1., 0., 1., 4.]), np.array([2., -1., 4., 0., -2.])).statistic
    assert k.pearson(x, y) == pytest.approx(expected, abs=2e-15)


def test_zero_and_perfect_pearson_not_answer_direction_gates():
    x = np.array([-1., 0., 1.])
    assert k.pearson(x, x) == 1
    assert k.pearson(x, -x) == -1
    assert k.pearson([-1., 1., -1., 1.], [-1., -1., 1., 1.]) == 0
    assert k.pearson(x, [.1, .1, .1]) is None


@pytest.mark.parametrize("sign", [1., -1.])
def test_signed_connectivity_cap_and_diagonal_exclusion(sign):
    x = np.array([-3., -1., 0., 1., 3.])
    result = k.connectivity(np.column_stack([x, sign*x, np.full(5, .1)]))
    assert result["active_columns"] == [True, True, False]
    assert result["n_edges"] == 1
    assert result["connectivity"] == pytest.approx(sign * math.atanh(.999), abs=1e-14)


def test_fisher_mean_not_raw_mean_or_absolute_mean():
    x = np.array([-2., -1., 0., 1., 2., 3.])
    table = np.column_stack([x, .7*x + np.array([1, -1, 1, -1, 1, -1]),
                             -.3*x + np.array([0, 1, -1, 1, -1, 0])])
    edges = np.corrcoef(table, rowvar=False)[np.triu_indices(3, 1)]
    target = np.arctanh(np.clip(edges, -.999, .999)).mean()
    result = k.connectivity(table)["connectivity"]
    assert result == pytest.approx(target, abs=1e-14)
    assert abs(result - edges.mean()) > 1e-3
    assert abs(result - np.abs(np.arctanh(np.clip(edges, -.999, .999))).mean()) > 1e-3


@pytest.mark.parametrize("scale", [1e-300, 1., 1e300])
def test_source_connectivity_scales_before_covariance(scale):
    x = np.array([[-2., 1., 4.], [-1., -1., 0.], [1., 2., -2.], [3., -2., 1.]])
    assert k.connectivity(scale*x)["connectivity"] == pytest.approx(k.connectivity(x)["connectivity"], abs=1e-13)


def test_source_no_new_nearconstant_cutoff():
    x = np.array([1., 1. + 2e-15, 1. - 2e-15, 1. + 4e-15])
    result = k.connectivity(np.column_stack([x, np.arange(4), np.full(4, .1)]))
    assert result["n_active_columns"] == 2
    assert result["status"] == "ok"


@pytest.mark.parametrize("bad", [np.nan, np.inf, -np.inf])
def test_nonfinite_source_even_would_be_inactive_is_rejected(bad):
    table = np.column_stack([np.arange(5), np.arange(5)**2, np.ones(5)])
    table[0, 2] = bad
    with pytest.raises(ValueError, match="nonfinite"):
        k.connectivity(table)


def test_source_all_constant_keeps_all_column_identities():
    result = k.connectivity(np.ones((7, 200)))
    assert result["active_columns"] == [False] * 200
    assert result["connectivity"] is None
    assert result["status"] == "insufficient_active_columns"


def test_float32_outward_fisher_cap_receipt_is_permitted():
    data = [dict(subject="literal_01", connectivity=k.CONNECTIVITY_LIMIT, age=20,
                 site_id="one", mean_fd=None, sex=None, typical_control=None)]
    result = k.analyze(data, {"literal_01": float(np.float32(k.CONNECTIVITY_LIMIT))})
    assert result["n_base"] == 1


@pytest.mark.parametrize("sign", [-1, 1])
def test_beyond_serialized_cap_allowance_rejected(sign):
    data = rows(1, 5)
    data[0]["connectivity"] = sign*k.CONNECTIVITY_LIMIT
    y = accepted(data)
    y[data[0]["subject"]] = sign*(k.CONNECTIVITY_LIMIT + k.VALUE_ATOL + k.VALUE_RTOL*k.CONNECTIVITY_LIMIT + 1e-8)
    with pytest.raises(ValueError, match="serialized domain"):
        k.analyze(data, y)


def test_gesvd_named_rank_recipe(monkeypatch):
    original = k.linalg.svd
    calls = []
    def logged(*args, **kwargs):
        calls.append(kwargs)
        return original(*args, **kwargs)
    monkeypatch.setattr(k.linalg, "svd", logged)
    x = np.arange(12.)
    model = k.nuisance_design(12, covariates={"motion": x, "duplicate": x})
    assert model.rank == 2 and len(model.column_ids) == 3
    assert model.cutoff == max(model.design.shape)*k.EPS*model.singular_values[0]
    assert calls and all(c["lapack_driver"] == "gesvd" and c["check_finite"] for c in calls)


def test_center_before_projection_avoids_large_level_cancellation():
    x = np.array([-3., -1., 0., 1., 3.])
    model = k.nuisance_design(5)
    shifted = 2**40 + x
    assert model.residual(shifted) == pytest.approx(model.residual(x), abs=1e-12)


def test_rank_cutoff_away_from_tie_uses_strict_public_scale():
    a = np.array([1., -1., 1., -1.]) / 2
    b = np.array([1., 1., -1., -1.]) / 2
    model = k.projection(np.column_stack([np.ones(4), 32*k.EPS*a, 2*k.EPS*b]),
                         ["intercept", "above_cutoff", "below_cutoff"])
    assert model.rank == 2
    assert model.singular_values[1] > model.cutoff > model.singular_values[2]


def test_redundant_nuisance_uses_rank_not_width():
    x = np.arange(12.)
    y = np.sin(x)
    model = k.nuisance_design(12, covariates={"constant": np.ones(12), "duplicate_intercept": np.ones(12)})
    result = k.association(x, y, y, model)
    assert result["rank"] == 1
    assert result["df"] == 10
    assert result["r"] == pytest.approx(k.pearson(x, y), abs=1e-14)


@pytest.mark.parametrize("df", [-1, 0, 1, 2, 17])
def test_inference_df_separates_r_p_ci(df):
    result = k.correlation_inference(.3, df)
    assert result["r"] == .3
    assert (result["p"] is not None) == (df > 0)
    assert (result["ci95"] is not None) == (df > 1)
    if df > 1:
        width = stats.norm.ppf(.975)/math.sqrt(df-1)
        assert result["ci95"] == pytest.approx(np.tanh(np.arctanh(.3) + np.array([-width, width])))


@pytest.mark.parametrize("sign", [-1., 1.])
@pytest.mark.parametrize("df", [0, 1, 10])
def test_perfect_correlation_explicit_null_interval(sign, df):
    out = k.correlation_inference(sign, df)
    assert out["r"] == sign and out["ci95"] is None and out["t"] is None
    assert out["p"] == (0.0 if df > 0 else None)
    assert out["ci_status"] == "perfect_correlation"


@pytest.mark.parametrize("r,df", [(1.00000001, 3), (-1.00000001, 3), (.1, True), (True, 3)])
def test_inference_domains_and_bool_are_not_tolerances(r, df):
    with pytest.raises(ValueError):
        k.correlation_inference(r, df)


def test_zero_correlation_p_one():
    out = k.correlation_inference(0, 12)
    assert out["t"] == 0 and out["p"] == 1


def test_canonical_inactive_residual_cannot_be_reactivated_by_jitter():
    x = np.arange(12.)
    model = k.nuisance_design(12, covariates={"motion": x})
    ref = .1 + .01*x
    y = ref + 1e-8*np.sin(x)
    out = k.association(np.sin(x), y, ref, model)
    assert out["r"] is None and not out["connectivity_support"]["active"]


def test_active_residual_relative_fidelity_has_no_absolute_floor():
    x = np.arange(12.)
    model = k.nuisance_design(12, covariates={"motion": x})
    ref = .1 + .01*x + 1e-8*np.sin(x)
    y = ref + 1e-10*np.cos(x)
    with pytest.raises(ValueError, match="fidelity"):
        k.association(np.sin(2*x), y, ref, model)


def test_activity_strict_boundary():
    source = np.array([-1., 1.])
    below = k.supported(.5*k.ACTIVITY_REL*source, source)
    above = k.supported(2*k.ACTIVITY_REL*source, source)
    assert not below["active"] and above["active"]
    # The exact computed comparison (not a rounded reported norm) is authority.
    equality = k.supported(k.ACTIVITY_REL*source, source)
    assert equality["active"] == (equality["centered_norm"] > equality["activity_threshold"])


def test_no_offset_gate_in_centered_fidelity():
    ref = np.array([-.4, -.1, .1, .5])
    k.fidelity(ref + 1e-7, ref, k.supported(ref, ref))


def test_nested_quadratic_matches_well_conditioned_ols_model():
    age = np.arange(10., 30.)
    az = k.center(age)/(k.stable_norm(k.center(age))/math.sqrt(len(age)))
    y = .1 + .03*az + .02*az**2 + .01*np.sin(age)
    out = k.quadratic(age, y, y)
    X0 = np.column_stack([np.ones(len(age)), az])
    X1 = np.column_stack([np.ones(len(age)), az, az**2])
    b0 = np.linalg.lstsq(X0, y, rcond=None)[0]
    b1 = np.linalg.lstsq(X1, y, rcond=None)[0]
    e0, e1 = y-X0@b0, y-X1@b1
    target = ((e0@e0)-(e1@e1))/((e1@e1)/(len(age)-3))
    assert out["base_rank"] == 2 and out["full_rank"] == 3 and out["added_rank"] == 1
    assert out["quadratic_beta"] == pytest.approx(b1[2], abs=1e-13)
    assert out["F_added_quadratic"] == pytest.approx(target, rel=1e-12)


def test_quadratic_has_only_one_base_svd(monkeypatch):
    original = k.linalg.svd
    shapes = []
    def logged(a, **kwargs):
        shapes.append(a.shape)
        return original(a, **kwargs)
    monkeypatch.setattr(k.linalg, "svd", logged)
    x = np.arange(10.)
    k.quadratic(x, np.sin(x), np.sin(x))
    assert shapes == [(10, 2)]


def test_quadratic_two_distinct_ages_no_added_rank():
    age = np.array([10., 20.] * 6)
    y = np.sin(np.arange(12.))
    out = k.quadratic(age, y, y)
    assert out["added_rank"] == 0 and out["full_rank"] == out["base_rank"]
    assert out["status"] == "no_added_rank"
    assert out["quadratic_beta"] is None and out["F_added_quadratic"] is None


@pytest.mark.parametrize("n", [0, 1, 9])
def test_quadratic_constant_age_defined_status_not_nan(n):
    out = k.quadratic(np.full(n, 20.), np.zeros(n), np.zeros(n))
    assert out["F_added_quadratic"] is None
    json.dumps(out, allow_nan=False)


def test_canonical_perfect_quadratic_fit_denominator_stays_undefined():
    age = np.arange(10., 30.)
    ref = .1 + .0003*age**2
    y = ref + 1e-9*np.sin(age)
    out = k.quadratic(age, y, ref)
    assert out["added_rank"] == 1
    assert out["status"] == "inactive_full_model_residual"
    assert out["F_added_quadratic"] is None and out["p_added_quadratic"] is None


def test_quadratic_active_full_residual_fidelity_uses_same_r1():
    age = np.arange(10., 30.)
    ref = .1 + .0003*age**2 + 1e-7*np.sin(age)
    with pytest.raises(ValueError, match="fidelity"):
        k.quadratic(age, ref + 1e-9*np.cos(age), ref)


def test_zero_added_gain_has_f_zero_p_one():
    out = k.added_term_inference(0., 2., 1, 15, True)
    assert out == dict(F_added_quadratic=0., p_added_quadratic=1., status="ok")


@pytest.mark.parametrize("gain,error,df1,df2,active,status", [
    (1., 0., 1, 12, False, "inactive_full_model_residual"),
    (0., 0., 1, 12, False, "inactive_full_model_residual"),
    (1., 2., 0, 12, True, "no_added_rank"),
    (1., 2., 1, 0, True, "nonpositive_residual_df"),
])
def test_quadratic_undefined_cases(gain, error, df1, df2, active, status):
    out = k.added_term_inference(gain, error, df1, df2, active)
    assert out["status"] == status and out["F_added_quadratic"] is None and out["p_added_quadratic"] is None


@pytest.mark.parametrize("args", [(-1., 2., 1, 12, True), (1., -1., 1, 12, True),
                                 (1., 2., True, 12, True), (1., 2., 1, 12, 1)])
def test_no_negative_gain_abs_repair_or_epsilon_denominator(args):
    with pytest.raises(ValueError):
        k.added_term_inference(*args)


@pytest.mark.parametrize("error,df2", [(0., 12), (float(np.nextafter(0., 1.)), 12)])
def test_supported_squared_error_underflow_not_f_zero_or_division_error(error, df2):
    out = k.added_term_inference(0., error, 1, df2, True)
    assert out["status"] == "numerical_underflow"
    assert out["F_added_quadratic"] is None and out["p_added_quadratic"] is None


def test_tiny_scale_quadratic_keeps_norm_support_and_reports_underflow():
    age = np.arange(10., 30.)
    y = 1e-200*(np.sin(age) + .02*age**2)
    out = k.quadratic(age, y, y)
    assert out["full_residual_support"]["active"]
    assert out["rss_quadratic"] == 0
    assert out["status"] == "numerical_underflow"
    assert out["F_added_quadratic"] is None and out["p_added_quadratic"] is None
    assert out["full_rank"] == 3 and out["quadratic_beta"] is not None


def test_positive_gain_final_ratio_underflow_is_not_exact_zero_gain():
    out = k.added_term_inference(float(np.nextafter(0., 1.)), 2., 1, 1, True)
    assert out["status"] == "numerical_underflow"
    assert out["F_added_quadratic"] is None and out["p_added_quadratic"] is None


def test_near_cancellation_gain_is_nonnegative_without_rss_subtraction():
    age = np.arange(10., 30.)
    y = .1 + .01*age + 1e-10*age**2 + .01*np.sin(age)
    out = k.quadratic(age, y, y)
    assert out["gain_ss"] >= 0 and out["rss_quadratic"] >= 0
    assert out["status"] == "ok"


def test_full_five_sensitivities_exist_below_fifty_people():
    data = rows()
    out = k.analyze(data, accepted(data))
    assert out["n_source"] == 18 and out["n_base"] == 18
    assert set(out["sensitivity"]) == {"motion", "diagnosis", "sex", "nonlinear_age", "site_specific_slopes"}
    assert out["sensitivity"]["motion"]["n"] == 18
    assert out["sensitivity"]["diagnosis"]["n"] == 12
    json.dumps(out, allow_nan=False)


def test_sensitivity_inherits_site_parent_without_reapplying_five():
    data = rows()
    for r in data[:4]:
        r["mean_fd"] = None
    out = k.analyze(data, accepted(data))
    mo = out["sensitivity"]["motion"]
    assert mo["site_counts"]["site0"] == 2
    assert len([s for s in mo["ids"] if s.startswith("site0_")]) == 2
    assert mo["pooled"]["ids"] == mo["within_site"]["ids"] == mo["ids"]


def test_primary_small_site_not_in_any_inherited_sensitivity():
    data = rows(2, 6) + rows(1, 4)
    for r in data[-4:]:
        r["subject"] = "small_" + r["subject"]
        r["site_id"] = "small"
    out = k.analyze(data, accepted(data))
    assert out["n_base"] == 16 and out["n_within"] == 12
    for name in ("motion", "sex", "diagnosis"):
        assert all(not s.startswith("small_") for s in out["sensitivity"][name]["ids"])


def test_all_rows_kept_with_explicit_missing_reasons():
    data = rows()
    data[0]["connectivity"] = None
    data[1]["age"] = None
    data[2]["age"] = 0
    data[3]["age"] = 120
    data[4]["site_id"] = None
    out = k.analyze(data, accepted(data))
    assert len(out["cohort"]) == len(data)
    by_id = {r["subject"]: r for r in out["cohort"]}
    assert by_id[data[0]["subject"]]["base_reason"] == "undefined_source_connectivity"
    assert by_id[data[1]["subject"]]["base_reason"] == "missing_age"
    assert by_id[data[2]["subject"]]["base_reason"] == "age_outside_open_0_120"
    assert by_id[data[4]["subject"]]["base_eligible"] and not by_id[data[4]["subject"]]["within_eligible"]


def test_between_site_is_equal_site_not_expanded_participant_weight():
    data = rows(3, 6)
    # Extra distinct participant identities intentionally change one site's n.
    for j, source in enumerate(copy.deepcopy(data[:6])):
        source["subject"] = f"extra_{j}"
        data.append(source)
    out = k.analyze(data, accepted(data))
    m = out["site_means"]
    expected = k.pearson([r["mean_age"] for r in m], [r["mean_connectivity"] for r in m])
    weighted = k.pearson([r["mean_age"] for r in m for _ in range(r["n"])],
                         [r["mean_connectivity"] for r in m for _ in range(r["n"])])
    assert out["between_site"]["r"] == pytest.approx(expected, abs=1e-14)
    assert abs(expected-weighted) > 1e-6
    assert out["between_site"]["unit"] == "site" and out["between_site"]["n"] == 3


def test_source_close_own_values_drive_all_replay_not_canonical_endpoint():
    data = rows()
    y = accepted(data)
    for j, r in enumerate(data):
        y[r["subject"]] += 1e-10*math.cos(j)
    out = k.analyze(data, y)
    unchanged = k.analyze(data, accepted(data))
    expected = k.pearson([r["age"] for r in data], [y[r["subject"]] for r in data])
    assert out["pooled"]["r"] == pytest.approx(expected, abs=1e-14)
    assert out["pooled"]["r"] != unchanged["pooled"]["r"]


def test_constant_source_response_all_correlations_undefined_not_fabrication():
    data = rows()
    for r in data:
        r["connectivity"] = .1
    y = {r["subject"]: .1 + 1e-8*math.sin(i) for i, r in enumerate(data)}
    out = k.analyze(data, y)
    assert out["pooled"]["r"] is None and out["within_site"]["r"] is None
    assert out["between_site"]["r"] is None
    site = out["sensitivity"]["site_specific_slopes"]
    assert site["n_expected"] == 3 and site["n_defined"] == 0
    assert site["frac_sites_positive"] is None


def test_coherent_near_zero_sign_counts_follow_own_unrounded_values():
    data = []
    x = [-2., -1., 0., 1., 2.]
    y = [.01, -.02, .02, -.02, .01]
    for s in range(3):
        for j in range(5):
            data.append(dict(subject=f"s{s}_{j}", age=20.+10*s+x[j], site_id=f"s{s}",
                             connectivity=y[j], mean_fd=None, sex=None, typical_control=None))
    plus = {r["subject"]: r["connectivity"] + 1e-10*x[j % 5] for j, r in enumerate(data)}
    minus = {r["subject"]: r["connectivity"] - 1e-10*x[j % 5] for j, r in enumerate(data)}
    a = k.analyze(data, plus)["sensitivity"]["site_specific_slopes"]
    b = k.analyze(data, minus)["sensitivity"]["site_specific_slopes"]
    assert a["n_sites_positive"] == 3 and b["n_sites_positive"] == 0
    assert all(round(r["r"], 6) == 0 for r in a["per_site"] + b["per_site"])


def test_one_undefined_site_does_not_disappear_from_summary():
    data = rows()
    for r in data[:6]:
        r["connectivity"] = .1
    out = k.analyze(data, accepted(data))
    site = out["sensitivity"]["site_specific_slopes"]
    assert site["n_expected"] == 3 and site["n_defined"] == 2
    assert len(site["per_site"]) == 3
    for key in ("median_within_site_r", "frac_sites_positive", "min_r", "max_r", "n_sites_positive"):
        assert site[key] is None
    constant = next(r for r in site["per_site"] if r["site_id"] == "site0")
    assert constant["slope"] == 0 and constant["r"] is None


def test_constant_age_site_has_no_slope():
    data = rows()
    for r in data[:6]:
        r["age"] = 20
    site = k.analyze(data, accepted(data))["sensitivity"]["site_specific_slopes"]["per_site"]
    result = next(r for r in site if r["site_id"] == "site0")
    assert result["slope"] is None and result["r"] is None


def test_keyed_input_permutation_invariant():
    data = rows()
    y = accepted(data)
    assert k.analyze(list(reversed(data)), dict(reversed(list(y.items())))) == k.analyze(data, y)


@pytest.mark.parametrize("kind", ["duplicate", "digit_id", "missing", "extra", "bool_connectivity",
                                 "undefined_filled", "far_value", "bool_age", "control_number"])
def test_bad_identity_or_typed_source_binding(kind):
    data = rows()
    y = accepted(data)
    if kind == "duplicate":
        data[1]["subject"] = data[0]["subject"]
    elif kind == "digit_id":
        y["0000"] = y.pop(data[0]["subject"])
    elif kind == "missing":
        y.pop(data[0]["subject"])
    elif kind == "extra":
        y["fake"] = 0
    elif kind == "bool_connectivity":
        y[data[0]["subject"]] = True
    elif kind == "undefined_filled":
        data[0]["connectivity"] = None
    elif kind == "far_value":
        y[data[0]["subject"]] += .01
    elif kind == "bool_age":
        data[0]["age"] = True
    else:
        data[0]["typical_control"] = 2
    with pytest.raises(ValueError):
        k.analyze(data, y)


def test_empty_complete_case_outputs_are_present_and_json_finite():
    data = rows()
    for r in data:
        r.update(mean_fd=None, sex=None, typical_control=None)
    out = k.analyze(data, accepted(data))
    for name in ("motion", "sex", "diagnosis"):
        assert out["sensitivity"][name]["n"] == 0
        assert out["sensitivity"][name]["pooled"]["r"] is None
    json.dumps(out, allow_nan=False)


def test_empty_source_rows_generic_manufactured_contract():
    out = k.analyze([], {})
    assert out["n_source"] == 0 and out["pooled"]["r"] is None
    assert out["sensitivity"]["site_specific_slopes"]["status"] == "incomplete_support"
    json.dumps(out, allow_nan=False)
