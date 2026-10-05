"""Arithmetic and label binding for the declared fODF recipes."""
import numpy as np

from proof_of_work import (
    ARITHMETIC_TOL, ESTIMATORS, PIPELINE_ID, estimator_values, integer,
    match_contract, number, ordered_values,
)


def primary_choice(report, groups):
    assert len(groups) >= 2 and set(groups) <= ESTIMATORS, "at least two public estimators required"
    primary = report["primary_estimator"]
    assert isinstance(primary, str) and primary in groups, "primary estimator must be a submitted estimator"
    return primary


def validate_maps(primary, groups, reference, selected):
    assert selected in groups, "primary estimator must be a submitted estimator"
    assert len(groups) >= 2 and set(groups) <= ESTIMATORS, "at least two public estimators required"
    arrays = {}
    for name, mapping in groups.items():
        values = ordered_values(mapping, reference)
        assert np.array_equal(values, reference["maps"][name]), f"voxel peak counts differ from declared estimator {name}"
        arrays[name] = values
    primary_values = ordered_values(primary, reference)
    assert np.array_equal(primary_values, arrays[selected]), "primary map and declared estimator map disagree"
    return primary_values, arrays


def validate_results(report, primary, groups):
    selected = primary_choice(report, groups)
    assert report.get("status") == "ok", "crossing.json status must be ok"
    assert report.get("pipeline_id") == PIPELINE_ID, "incorrect result pipeline"
    counts = np.asarray(primary)
    assert counts.ndim == 1 and len(counts) > 0, "nonempty primary map required"
    assert integer(report["n_roi_voxels"]) == len(counts), "incorrect ROI voxel count"
    assert integer(report["n_crossing_voxels"]) == int(np.sum(counts >= 2)), "incorrect crossing voxel count"
    assert abs(number(report["crossing_fraction"]) - np.mean(counts >= 2)) <= ARITHMETIC_TOL, "primary fraction must recompute"
    assert abs(number(report["mean_peaks_per_voxel"]) - np.mean(counts)) <= ARITHMETIC_TOL, "mean peak count must recompute"
    fractions = estimator_values(report["crossing_fraction_by_estimator"])
    assert set(fractions) == set(groups), "fraction summaries must cover exactly the submitted estimators"
    for name, values in groups.items():
        assert abs(fractions[name] - np.mean(np.asarray(values) >= 2)) <= ARITHMETIC_TOL, f"incorrect {name} crossing fraction"
    return selected


def validate_metadata(metadata, reference, selected, groups):
    assert metadata.get("status") == "ok", "run_metadata.json status must be ok"
    match_contract(metadata, reference["stats"]["metadata_contract"])
    assert metadata["source_sha256"] == reference["stats"]["source_sha256"], "incorrect source digest mapping"
    assert metadata["primary_estimator"] == selected, "metadata primary estimator disagrees"
    fitted = metadata["fitted_estimators"]
    assert isinstance(fitted, list) and all(isinstance(name, str) for name in fitted)
    assert len(fitted) == len(set(fitted)) and set(fitted) == set(groups), "metadata fitted estimators disagree"
