"""Manufactured-only qualification of authoring control construction.

This module imports the draft control helpers but never requests its genuine
fixtures, source_reference.reconstruct, or any original output path.
"""
import copy

import numpy as np
import pytest

import proof_of_work as p
import test_actual_outputs as q


@pytest.fixture(scope="module")
def kernel():
    return p.load_kernel()


def tiny_replay(kernel, mode):
    ids = ["0010042", "0010064"]
    people, accepted, analyses = {}, {}, []
    for index, sid in enumerate(ids):
        clean = np.zeros((52, 48))
        active = np.zeros(48, dtype=bool)
        if mode == "quantitative":
            clean[:, :3] = np.random.default_rng(19410+index).normal(size=(52, 3)); active[:3] = True
        elif mode == "zero_variability":
            clean[:, :2] = np.sin(np.arange(52)[:, None]/3.); active[:2] = True
        elif mode == "partial":
            if index == 0:
                clean[:, :3] = np.random.default_rng(19410).normal(size=(52, 3)); active[:3] = True
        elif mode != "inactive": raise AssertionError("unknown manufactured mode")
        people[sid] = dict(active=active, clean=clean)
        accepted[sid] = clean
        analyses.append(kernel.analyze_subject(clean, clean, active, sid, 0))
    reference = dict(participant_ids=ids, persons=people)
    return reference, accepted, analyses, kernel.summarize_subjects(analyses, ids)


@pytest.fixture(scope="module")
def examples(kernel):
    return {mode: tiny_replay(kernel, mode) for mode in ("quantitative", "zero_variability", "partial", "inactive")}


MODES = ("gaussian_null", "median_null_mean", "inverse_ratio", "no_plus_one", "strict_ties", "ddof0", "raw_r_instead_of_fisher", "ratio_of_group_means")


@pytest.mark.parametrize("mode", MODES)
def test_manufactured_quantitative_controls_have_honest_gap_inventory(kernel, examples, mode):
    ref, accepted, analyses, dynamics = examples["quantitative"]
    snapshot = copy.deepcopy(q._scalar_snapshot(analyses, dynamics))
    changed, report, gaps = q.component_candidate(analyses, dynamics, ref, accepted, kernel, mode)
    assert q._scalar_snapshot(analyses, dynamics) == snapshot
    measured = q.observable_gaps(snapshot, q._scalar_snapshot(changed, report))
    assert all(gaps[k] == value for k, value in measured.items())
    assert gaps["construction"] == "constructed" and gaps["n_constructed_cells"] > 0
    assert type(gaps["effective"]) is bool
    if mode in ("gaussian_null", "no_plus_one", "ddof0", "raw_r_instead_of_fisher"):
        assert gaps["effective"], "manufactured control must change a required observable"


@pytest.mark.parametrize("mode", MODES)
def test_inactive_controls_unavailable_except_always_declared_denominator(kernel, examples, mode):
    ref, accepted, analyses, dynamics = examples["inactive"]
    _, _, gaps = q.component_candidate(analyses, dynamics, ref, accepted, kernel, mode)
    if mode == "no_plus_one":
        assert gaps["construction"] == "constructed" and gaps["effective"]
        assert gaps["n_exact_fields_changed"] >= 6
    else:
        assert gaps["construction"] == "unavailable_support"
        assert not gaps["effective"] and gaps["n_constructed_cells"] == 0


def test_zero_variability_ddof0_is_not_called_a_negative(kernel, examples):
    ref, accepted, analyses, dynamics = examples["zero_variability"]
    for item in analyses:
        assert all(row["mean_edge_sd"] == row["mean_edge_sd_null"] == 0 for row in item["windows"])
    _, _, gaps = q.component_candidate(analyses, dynamics, ref, accepted, kernel, "ddof0")
    assert gaps["construction"] == "constructed" and not gaps["effective"]


def test_exact_zero_ties_strict_greater_is_effective_but_ratio_stays_null(kernel, examples):
    ref, accepted, analyses, dynamics = examples["zero_variability"]
    changed, report, gaps = q.component_candidate(analyses, dynamics, ref, accepted, kernel, "strict_ties")
    assert gaps["effective"] and gaps["n_exact_fields_changed"] > 0
    for item in changed:
        for row in item["windows"]:
            assert row["n_exceedances"] == 0 and row["p_numerator"] == 1
            assert row["p_value"] == 1/51 and row["significant"] is True
            assert row["ratio_status"] == "zero_null_mean" and row["observed_over_null_ratio"] is None
    assert all(row["mean_subject_observed_over_null_ratio"]["value"] is None for row in report["windows"])


def test_ddof0_factor_applies_to_every_defined_observed_and_null(kernel, examples):
    ref, accepted, analyses, dynamics = examples["quantitative"]
    changed, _, _ = q.component_candidate(analyses, dynamics, ref, accepted, kernel, "ddof0")
    for old, new in zip(analyses, changed):
        factors = {row["window_tr"]: np.sqrt((row["n_windows"]-1)/row["n_windows"]) for row in old["windows"]}
        for a, b in zip(old["windows"], new["windows"]):
            assert b["mean_edge_sd"] == pytest.approx(a["mean_edge_sd"]*factors[a["window_tr"]], rel=1e-14, abs=0.)
        for a, b in zip(old["surrogates"], new["surrogates"]):
            assert b["mean_edge_sd"] == pytest.approx(a["mean_edge_sd"]*factors[a["window_tr"]], rel=1e-14, abs=0.)


def test_incomplete_group_ratio_control_never_available_case(kernel, examples):
    ref, accepted, analyses, dynamics = examples["partial"]
    _, result, gaps = q.component_candidate(analyses, dynamics, ref, accepted, kernel, "ratio_of_group_means")
    assert gaps["construction"] == "unavailable_support" and not gaps["effective"]
    assert all(row["mean_subject_observed_over_null_ratio"]["status"] == "incomplete_support" for row in result["windows"])


@pytest.mark.parametrize("gap,expected", [(0., False), (5e-7, False), (3e-6, True)])
def test_effectiveness_uses_public_float_tolerance(gap, expected):
    report = q.observable_gaps(dict(value=0.), dict(value=gap))
    assert report["effective"] is expected


def test_exact_count_boolean_null_and_per_draw_changes_are_not_lost():
    expected = {"count": 1, "flag": True, "value": None, "draws": [False, True]}
    candidate = {"count": 2, "flag": False, "value": 0., "draws": [True, True]}
    gaps = q.observable_gaps(expected, candidate)
    assert gaps["n_exact_fields_changed"] == 4 and gaps["effective"]


def test_rounding_never_changes_required_integers_booleans_or_nulls():
    out = q.rounded_scalars(dict(value=.12345678, count=50, flag=True, missing=None))
    assert out == dict(value=.123457, count=50, flag=True, missing=None)
    assert type(out["count"]) is int and type(out["flag"]) is bool
