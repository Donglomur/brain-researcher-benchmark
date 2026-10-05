"""Tiny summary-mechanics examples only; never source/reference evidence."""
import copy
from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from proof_of_work import METHODS, PARAMETERS, PIPELINE_ID, SUMMARY_ATOL
from ivim_contract import metric_summary, validate_results, validate_summary


def summary_example():
    # Distinct own-valid denominators force an actual paired intersection.
    arrays = {
        METHODS[0]: {"params": np.array([[1000., .2, .02, .001], [900., .4, .03, .002]]),
                     "valid": np.array([True, True]), "nrmse": np.array([.01, .03]),
                     "b0": np.array([1000., 1000.])},
        METHODS[1]: {"params": np.array([[1000., .1, .01, .001], [1000., -.1, np.nan, .002]]),
                     "valid": np.array([True, False]), "nrmse": np.array([.02, np.nan]),
                     "b0": np.array([1000., 1000.])},
    }
    common = np.array([True, False])
    shared = {name: metric_summary(values["params"], values["nrmse"], common) for name, values in arrays.items()}
    result = {"status": "ok", "pipeline_id": PIPELINE_ID, "primary_method": METHODS[0],
              "diffusivity_units": "mm^2/s",
              "fits": [{"method": name, **metric_summary(values["params"], values["nrmse"], values["valid"])}
                       for name, values in arrays.items()],
              "common_valid": {"n_voxels": 1, "by_method": shared,
                  "paired_differences": {"segmented_minus_trr": {
                      key: shared[METHODS[1]][key] - shared[METHODS[0]][key] for key in SUMMARY_ATOL}}}}
    return result, arrays, common


@pytest.mark.parametrize("defect", [None, "wrong_count", "wrong_common_count", "own_as_common",
    "missing_D", "wrong_D", "wrong_S0", "absolute_difference", "wrong_units", "wrong_primary",
    "duplicate_method", "boolean_number", "nan_mean", "failed_status"])
def test_explicit_summary_arithmetic(defect):
    result, arrays, common = summary_example()
    if defect == "wrong_count":
        result["fits"][0]["n_voxels"] += 1
    elif defect == "wrong_common_count":
        result["common_valid"]["n_voxels"] += 1
    elif defect == "own_as_common":
        result["common_valid"]["by_method"][METHODS[0]] = result["fits"][0]
    elif defect == "missing_D":
        result["fits"][0].pop("D_mean")
    elif defect == "wrong_D":
        result["fits"][0]["D_mean"] *= 1000
    elif defect == "wrong_S0":
        result["fits"][0]["S0_mean"] += 1
    elif defect == "absolute_difference":
        result["common_valid"]["paired_differences"]["segmented_minus_trr"]["f_mean"] = .1
    elif defect == "wrong_units":
        result["diffusivity_units"] = "um^2/ms"
    elif defect == "wrong_primary":
        result["primary_method"] = "trr"
    elif defect == "duplicate_method":
        result["fits"][1]["method"] = METHODS[0]
    elif defect == "boolean_number":
        result["fits"][0]["f_mean"] = True
    elif defect == "nan_mean":
        result["fits"][0]["f_mean"] = float("nan")
    elif defect == "failed_status":
        result["status"] = "failed_precondition"
    if defect is None:
        assert validate_results(result, arrays, common) == METHODS[0]
    else:
        with pytest.raises((AssertionError, KeyError, ValueError)):
            validate_results(result, arrays, common)


def test_empty_set_requires_null_not_invented_zero():
    summary = metric_summary(np.full((2, 4), np.nan), np.full(2, np.nan), np.zeros(2, bool))
    assert summary["n_voxels"] == 0
    validate_summary(summary, summary)
    wrong = {**summary, "f_mean": 0}
    with pytest.raises(AssertionError, match="null"):
        validate_summary(wrong, summary)


def test_agreement_has_no_minimum_spread_gate():
    result, arrays, common = summary_example()
    arrays[METHODS[1]] = copy.deepcopy(arrays[METHODS[0]])
    common[:] = True
    common_stats = metric_summary(arrays[METHODS[0]]["params"], arrays[METHODS[0]]["nrmse"], common)
    result["fits"] = [{"method": name, **common_stats} for name in METHODS]
    result["common_valid"] = {"n_voxels": 2, "by_method": {name: common_stats for name in METHODS},
                              "paired_differences": {"segmented_minus_trr": {key: 0 for key in SUMMARY_ATOL}}}
    assert validate_results(result, arrays, common) == METHODS[0]
