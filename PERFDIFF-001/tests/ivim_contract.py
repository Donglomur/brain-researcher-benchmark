"""Parameter/status linkage and paired source-signal arithmetic for IVIM."""
import numpy as np

from proof_of_work import (
    METHODS, PARAMETERS, PARAMETER_ATOL, PARAMETER_RTOL, NRMSE_ATOL, NO_SOLVER,
    PREDICTION_ATOL_OVER_B0, SUMMARY_ATOL, PIPELINE_ID, DATASET_ID, STATUSES, admissible, bound_flags,
    assert_numeric_arrays, integer, match_contract, number, observed_b0,
    ordered_rows, normalized_predictions, signal_nrmse,
)


def primary_choice(result):
    primary = result["primary_method"]
    assert isinstance(primary, str) and primary in METHODS, "primary_method must name a submitted public method"
    return primary


def validate_parameters(groups, reference):
    assert set(groups) == set(METHODS), "both declared methods required"
    arrays = {}
    b0 = observed_b0(reference["signal"], reference["bvals"])
    scale = np.where(np.isfinite(b0) & (b0 > 0), b0, 1.0)
    for name in METHODS:
        rows = ordered_rows(groups[name], reference)
        params = np.asarray([row["params"] for row in rows])
        ref = reference["methods"][name]
        for index, parameter in enumerate(PARAMETERS):
            actual, expected = params[:, index], ref["params"][:, index]
            if parameter == "S0":
                actual, expected, parameter = actual / scale, expected / scale, "S0_over_b0"
            assert_numeric_arrays(actual, expected, atol=PARAMETER_ATOL[parameter], rtol=PARAMETER_RTOL,
                                  label=f"{name} {parameter} reference parameters")
        for field in ("status", "init_projected", "fallback", "component_swap"):
            assert np.array_equal([row[field] for row in rows], ref[field]), f"incorrect {name} {field}"
        assert not any(row["fallback"] for row in rows), "fallback is not a graded fit"
        eligible = np.asarray([row["eligible"] for row in rows])
        assert np.array_equal(eligible, reference["eligible"]), "source eligibility flags differ"
        ok = np.asarray([row["status"] == "ok" for row in rows])
        assert np.all(~ok | (eligible & admissible(params))), "successful fit violates the public admissibility rule"
        for index, row in enumerate(rows):
            status, calls = row["optimizer_status"], row["nfev"]
            assert ((np.isnan(status) and calls == 0) or
                    (np.isfinite(status) and calls > 0)), "optimizer status/nfev disagree"
            if row["status"] in NO_SOLVER:
                assert np.isnan(status) and calls == 0, "no-solver status must not claim optimizer execution"
            elif row["status"] == "ok":
                assert status > 0, "successful fit must have a successful optimizer status"
            elif row["status"] == "optimizer_failed":
                assert np.isnan(status) or status <= 0, "failed optimizer must not claim success"
            else:
                assert status > 0, "postfit parameter rejection requires a returned successful optimizer"
            assert row["bound_flags"] == bound_flags(row["params"], b0[index]), "bound flags must recompute from parameters"
        residual = signal_nrmse(params, reference["signal"], reference["bvals"])
        assert_numeric_arrays([row["nrmse"] for row in rows], residual, atol=NRMSE_ATOL,
                              rtol=PARAMETER_RTOL, label=f"{name} source-reconstructed NRMSE")
        assert_numeric_arrays(normalized_predictions(params, reference["signal"], reference["bvals"]),
                              ref["normalized_predictions"], atol=PREDICTION_ATOL_OVER_B0,
                              rtol=PARAMETER_RTOL, label=f"{name} normalized source predictions")
        arrays[name] = {"params": params, "valid": ok, "nrmse": residual, "rows": rows, "b0": b0}
    common = np.logical_and.reduce([arrays[name]["valid"] for name in METHODS])
    for name in METHODS:
        assert np.array_equal([row["common_valid"] for row in arrays[name]["rows"]], common), "common-valid must be the exact method intersection"
    return arrays, common


def validate_f_maps(primary, sweep, groups, reference, selected):
    assert set(sweep) == set(METHODS), "both declared f-map methods required"
    for name in METHODS:
        values = ordered_rows(sweep[name], reference)
        expected = [row["params"][1] for row in ordered_rows(groups[name], reference)]
        assert_numeric_arrays(values, expected, atol=1e-6, label=f"{name} f map/parameter linkage")
    assert_numeric_arrays(ordered_rows(primary, reference), ordered_rows(sweep[selected], reference),
                          atol=1e-6, label="primary f map/declared method linkage")


def metric_summary(params, residual, mask):
    summary = {"n_voxels": int(np.sum(mask))}
    for index, parameter in enumerate(PARAMETERS):
        summary[f"{parameter}_mean"] = float(np.mean(params[mask, index])) if np.any(mask) else None
    summary["nrmse_mean"] = float(np.mean(residual[mask])) if np.any(mask) else None
    return summary


def validate_summary(actual, expected, *, counts=True, b0_scale=1.0):
    assert isinstance(actual, dict), "metric summary must be an object"
    if counts:
        assert integer(actual["n_voxels"]) == expected["n_voxels"], "incorrect valid-fit denominator"
    for key, tolerance in SUMMARY_ATOL.items():
        value = expected[key]
        if value is None:
            assert actual[key] is None, "empty valid set requires null metrics"
        else:
            tolerance *= b0_scale if key == "S0_mean" else 1.0
            assert abs(number(actual[key]) - value) <= tolerance, f"incorrect recomputed {key}"


def validate_results(result, arrays, common):
    assert result.get("status") == "ok", "ivim_results.json status must be ok"
    assert result.get("pipeline_id") == PIPELINE_ID, "incorrect result pipeline"
    selected = primary_choice(result)
    assert result["diffusivity_units"] == "mm^2/s", "incorrect diffusivity units"
    fits = result["fits"]
    assert isinstance(fits, list) and len(fits) == len(METHODS)
    assert all(isinstance(fit, dict) and isinstance(fit.get("method"), str) for fit in fits)
    assert {fit["method"] for fit in fits} == set(METHODS), "summary methods must be distinct and exact"
    for fit in fits:
        values = arrays[fit["method"]]
        scale = float(np.mean(values["b0"][values["valid"]])) if values["valid"].any() else 1.0
        validate_summary(fit, metric_summary(values["params"], values["nrmse"], values["valid"]), b0_scale=scale)
    shared = result["common_valid"]
    assert integer(shared["n_voxels"]) == int(common.sum()), "incorrect common-valid denominator"
    assert set(shared["by_method"]) == set(METHODS)
    summaries = {}
    for name in METHODS:
        values = arrays[name]
        summaries[name] = metric_summary(values["params"], values["nrmse"], common)
        scale = float(np.mean(values["b0"][common])) if common.any() else 1.0
        validate_summary(shared["by_method"][name], summaries[name], b0_scale=scale)
    assert set(shared["paired_differences"]) == {"segmented_minus_trr"}
    differences = {key: (summaries[METHODS[1]][key] - summaries[METHODS[0]][key])
                   if common.any() else None for key in SUMMARY_ATOL}
    validate_summary(shared["paired_differences"]["segmented_minus_trr"], differences, counts=False, b0_scale=scale)
    return selected


def validate_metadata(metadata, reference, selected):
    assert metadata.get("status") == "ok", "run_metadata.json status must be ok"
    match_contract(metadata, reference["stats"]["metadata_contract"])
    assert metadata["source_sha256"] == reference["stats"]["source_sha256"], "incorrect source SHA256 mapping"
    assert metadata["primary_method"] == selected, "metadata primary method disagrees"
    methods = metadata["fitted_methods"]
    assert isinstance(methods, list) and len(methods) == len(METHODS) and set(methods) == set(METHODS), "metadata fitted methods disagree"
    assert integer(metadata["n_box_voxels"]) == len(reference["keys"]), "incorrect metadata box count"
    assert integer(metadata["n_tissue_voxels"]) == int(reference["tissue_eligible"].sum()), "incorrect metadata tissue count"
    assert integer(metadata["n_eligible_voxels"]) == int(reference["eligible"].sum()), "incorrect metadata eligible count"
    assert integer(metadata["n_common_valid_voxels"]) == int(reference["common_valid"].sum()), "incorrect metadata common-valid count"
    assert set(metadata["status_counts"]) == set(METHODS)
    for name in METHODS:
        counts = metadata["status_counts"][name]
        assert set(counts) == STATUSES, "status counts must account for every public status"
        for status in STATUSES:
            expected = int(np.sum(reference["methods"][name]["status"].astype(str) == status))
            assert integer(counts[status]) == expected, "incorrect status count"


def validate_source_summary(result, reference):
    assert result["dataset_id"] == DATASET_ID, "incorrect result dataset"
    assert integer(result["n_box_voxels"]) == len(reference["keys"]), "incorrect complete-box count"
    assert integer(result["n_tissue_voxels"]) == int(reference["tissue_eligible"].sum()), "incorrect tissue count"
    assert integer(result["n_eligible_voxels"]) == int(reference["eligible"].sum()), "incorrect source-eligible count"
