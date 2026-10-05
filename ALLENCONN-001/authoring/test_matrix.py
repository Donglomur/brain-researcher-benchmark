"""Invented tiny arrays test arithmetic mechanics only, never a scientific bank."""
import copy
import sys
from pathlib import Path
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "tests"))
from proof_of_work import PIPELINE_ID, aggregate_receipt, validate_receipt_arrays
from matrix_contract import source_descriptors, summary_metrics, validate_matrix, validate_strongest, validate_results


def mechanics_fixture():
    arrays = {"experiment_ids": np.array([1001, 1002, 1003, 1004]),
        "experiment_source_ids": np.array([10, 10, 20, 30]), "source_ids": np.array([10, 20, 30]),
        "target_ids": np.array([10, 20, 30]),
        "density": np.array([[.2, .8, 0.], [.6, np.nan, 0.], [0., 0., 0.], [.1, 0., .2]]),
        "record_status": np.array([["observed"]*3, ["observed", "api_absent", "observed"],
                                    ["observed"]*3, ["observed", "zero_domain", "observed"]]),
        "unionize_id": np.array([[1, 2, 3], [4, -1, 6], [7, 8, 9], [10, 11, 12]]),
        "sum_pixels": np.array([[10., 10., 10.], [90., np.nan, 90.], [10., 10., 10.], [10., 0., 10.]])}
    arrays["sum_projection_pixels"] = arrays["density"] * arrays["sum_pixels"]
    matrix, observed, expected = aggregate_receipt(arrays, arrays["source_ids"])
    arrays.update(matrix=matrix, n_observed=observed, n_expected=expected)
    hashes = {"mechanics-only-not-real-data.json": "a"*64}
    arrays["stats"] = {"source_sha256": hashes,
        "metadata_contract": {"pipeline_id": PIPELINE_ID, "source_sha256": hashes}}
    return arrays


def matrix_rows(reference):
    return {int(s): {int(t): reference["matrix"][i, j] for j, t in enumerate(reference["target_ids"])}
            for i, s in enumerate(reference["source_ids"])}


def support_rows(reference):
    return {(int(s), int(t)): (int(reference["n_observed"][i, j]), int(reference["n_expected"][i, j]))
            for i, s in enumerate(reference["source_ids"]) for j, t in enumerate(reference["target_ids"])}


def test_equal_experiment_available_case_mean_not_pixel_weighted():
    ref = mechanics_fixture(); validate_receipt_arrays(ref)
    matrix, observed, expected = aggregate_receipt(ref, ref["source_ids"])
    assert matrix[0, 0] == pytest.approx(.4)
    assert matrix[0, 0] != pytest.approx((.2*10+.6*90)/100)
    assert matrix[0, 1] == pytest.approx(.8)  # not (.8+0)/2
    assert observed[0, 1] == 1 and expected[0, 1] == 2
    assert matrix[0, 2] == 0 and observed[0, 2] == expected[0, 2] == 2


def test_zero_domain_is_present_but_not_observed_density_support():
    ref = mechanics_fixture()
    assert ref["record_status"][3, 1] == "zero_domain"
    assert ref["unionize_id"][3, 1] == 11 and ref["density"][3, 1] == 0
    assert np.isnan(ref["matrix"][2, 1]) and ref["n_observed"][2, 1] == 0
    assert ref["n_expected"][2, 1] == 1


def test_all_zero_source_is_complete_tied_self_and_not_rejected():
    ref = mechanics_fixture()
    desc = source_descriptors(ref["matrix"], ref["source_ids"], ref["target_ids"], ref["n_expected"])
    assert desc[20] == dict(status="complete", n_missing_targets=0, n_experiments=1,
                           strongest_targets={10, 20, 30}, is_self_strongest=True, max_density=0.)
    summary = summary_metrics(desc, ref, ref)
    assert summary["n_zero_max_sources"] == 1 and summary["n_tied_max_sources"] == 1


def test_incomplete_row_has_no_full_target_argmax_or_headline_contribution():
    ref = mechanics_fixture()
    desc = source_descriptors(ref["matrix"], ref["source_ids"], ref["target_ids"], ref["n_expected"])
    assert desc[30]["status"] == "incomplete" and desc[30]["strongest_targets"] == set()
    assert desc[30]["is_self_strongest"] is None and np.isnan(desc[30]["max_density"])
    summary = summary_metrics(desc, ref, ref)
    assert summary["n_source_regions"] == 3 and summary["n_eligible_sources"] == 2
    assert summary["n_self_strongest"] == 1 and summary["self_strongest_fraction"] == .5
    assert summary["record_status_counts"] == {"observed": 10, "api_absent": 1, "zero_domain": 1}


def test_ties_use_absolute_tolerance_without_relative_expansion():
    matrix = np.array([[1., 1.-5e-13, 0.], [1e6, 1e6-1e-6, 0.]])
    desc = source_descriptors(matrix, np.array([10, 20]), np.array([10, 20, 30]), np.ones((2, 3), int))
    assert desc[10]["strongest_targets"] == {10, 20}
    assert desc[20]["strongest_targets"] == {10} and not desc[20]["is_self_strongest"]


def test_constant_positive_rows_are_legitimate_ties():
    desc = source_descriptors(np.ones((1, 3)), np.array([20]), np.array([10, 20, 30]), np.ones((1, 3), int))
    assert desc[20]["is_self_strongest"] and desc[20]["strongest_targets"] == {10, 20, 30}


@pytest.mark.parametrize("kind", ["weighted", "missing_zero", "missing_denominator", "drop_support", "fake_observed"])
def test_matrix_or_support_forgery_fails(kind):
    ref = mechanics_fixture(); matrix, support = matrix_rows(ref), support_rows(ref)
    if kind == "weighted": matrix[10][10] = .56
    elif kind == "missing_zero": matrix[30][20] = 0.
    elif kind == "missing_denominator": matrix[10][20] = .4
    elif kind == "drop_support": del support[(10, 20)]
    else: support[(10, 20)] = (2, 2)
    with pytest.raises(AssertionError): validate_matrix(matrix, support, ref, ref)


@pytest.mark.parametrize("kind", ["omit_tie", "false_incomplete_max", "wrong_n_missing", "wrong_n_experiments", "wrong_status"])
def test_strongest_table_is_recomputed(kind):
    ref = mechanics_fixture()
    desc = source_descriptors(ref["matrix"], ref["source_ids"], ref["target_ids"], ref["n_expected"])
    if kind == "omit_tie": desc[20]["strongest_targets"] = {20}
    elif kind == "false_incomplete_max": desc[30]["max_density"] = .2
    elif kind == "wrong_n_missing": desc[30]["n_missing_targets"] = 0
    elif kind == "wrong_n_experiments": desc[10]["n_experiments"] = 1
    else: desc[30]["status"] = "complete"
    with pytest.raises(AssertionError):
        validate_strongest(desc, ref["matrix"], ref["n_observed"], ref["n_expected"], ref)


def test_no_original_fraction_band_is_required():
    ref = mechanics_fixture()
    desc = source_descriptors(ref["matrix"], ref["source_ids"], ref["target_ids"], ref["n_expected"])
    result = {"status": "ok", "pipeline_id": PIPELINE_ID, **summary_metrics(desc, ref, ref)}
    assert result["self_strongest_fraction"] == .5
    validate_results(result, desc, ref, ref)


def test_empty_eligible_denominator_is_undefined_not_zero():
    ref = mechanics_fixture(); matrix = ref["matrix"].copy(); matrix[:, 0] = np.nan
    desc = source_descriptors(matrix, ref["source_ids"], ref["target_ids"], ref["n_expected"])
    summary = summary_metrics(desc, ref, ref)
    assert summary["self_strongest_fraction"] is None and summary["n_eligible_sources"] == 0
    with pytest.raises(AssertionError, match="failed_precondition"):
        validate_results({"status": "ok", "pipeline_id": PIPELINE_ID, **summary}, desc, ref, ref)


def test_accepted_numeric_rounding_cannot_create_a_categorical_tie():
    ref = mechanics_fixture()
    ref["density"][0, 0] = ref["density"][1, 0] = .5
    ref["density"][0, 1] = .5000000001
    ref["sum_projection_pixels"] = ref["density"]*ref["sum_pixels"]
    ref["matrix"], ref["n_observed"], ref["n_expected"] = aggregate_receipt(ref, ref["source_ids"])
    submitted = matrix_rows(ref); submitted[10][10] = .5000000001
    matrix, observed, expected = validate_matrix(submitted, support_rows(ref), ref, ref)
    authoritative = source_descriptors(ref["matrix"], ref["source_ids"], ref["target_ids"], ref["n_expected"])
    assert authoritative[10]["strongest_targets"] == {20} and not authoritative[10]["is_self_strongest"]
    validate_strongest(authoritative, matrix, observed, expected, ref)
    forged = source_descriptors(matrix, ref["source_ids"], ref["target_ids"], expected)
    assert forged[10]["strongest_targets"] == {10, 20} and forged[10]["is_self_strongest"]
    with pytest.raises(AssertionError, match="strongest_targets"):
        validate_strongest(forged, matrix, observed, expected, ref)


def test_near_zero_rounding_does_not_change_zero_maximum_category():
    ref = mechanics_fixture(); submitted = matrix_rows(ref)
    for target in ref["target_ids"]: submitted[20][int(target)] = 5e-13
    matrix, observed, expected = validate_matrix(submitted, support_rows(ref), ref, ref)
    authoritative = source_descriptors(ref["matrix"], ref["source_ids"], ref["target_ids"], expected)
    # The submitted maximum can be numerically rounded; the category remains
    # tied/all-zero under the exact source means, not the rounded display.
    authoritative[20]["max_density"] = 5e-13
    checked = validate_strongest(authoritative, matrix, observed, expected, ref)
    assert summary_metrics(checked, ref, ref)["n_zero_max_sources"] == 1
