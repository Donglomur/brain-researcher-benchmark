"""Recompute projection-only equal-experiment means and identifiable full-row maxima."""
from pathlib import Path
import numpy as np

from proof_of_work import (PIPELINE_ID, RECORD_STATUSES, NUMERIC_ATOL, NUMERIC_RTOL,
    SUMMARY_ATOL, TIE_ATOL, number, integer, read_json, match_contract,
    load_experiment_targets, load_matrix, load_support, load_strongest,
    validate_receipt_arrays, aggregate_receipt)


def validate_experiment_targets(rows, reference):
    experiments, targets = reference["experiment_ids"], reference["target_ids"]
    assert set(rows) == {(int(experiment), int(target)) for experiment in experiments for target in targets}, "exact Cartesian experiment/target membership required"
    shape = len(experiments), len(targets)
    arrays = {"experiment_source_ids": reference["experiment_source_ids"].copy(),
        "record_status": np.empty(shape, dtype="U16"), "unionize_id": np.empty(shape, dtype=np.int64),
        **{name: np.empty(shape) for name in ("density", "sum_projection_pixels", "sum_pixels")}}
    for i, experiment in enumerate(experiments):
        for j, target in enumerate(targets):
            source, status, unionize, density, projected, pixels = rows[(int(experiment), int(target))]
            assert source == reference["experiment_source_ids"][i], "experiment source mapping differs from frozen atlas"
            arrays["record_status"][i, j], arrays["unionize_id"][i, j] = status, unionize
            arrays["density"][i, j], arrays["sum_projection_pixels"][i, j], arrays["sum_pixels"][i, j] = density, projected, pixels
    validate_receipt_arrays(arrays)
    assert np.array_equal(arrays["record_status"], reference["record_status"]), "experiment record statuses differ from source"
    assert np.array_equal(arrays["unionize_id"], reference["unionize_id"]), "unionize record IDs differ from source"
    for name in ("density", "sum_projection_pixels", "sum_pixels"):
        assert np.allclose(arrays[name], reference[name], atol=NUMERIC_ATOL, rtol=NUMERIC_RTOL, equal_nan=True), f"experiment {name} differs from raw source"
    return arrays


def validate_matrix(matrix_rows, support_rows, arrays, reference):
    sources, targets = reference["source_ids"], reference["target_ids"]
    assert set(matrix_rows) == set(sources), "exact source-ID matrix rows required"
    assert set(support_rows) == {(int(source), int(target)) for source in sources for target in targets}, "exact matrix-support Cartesian membership required"
    matrix = np.asarray([[matrix_rows[int(source)][int(target)] for target in targets] for source in sources])
    expected_matrix, observed, expected = aggregate_receipt(arrays, sources)
    assert np.array_equal(np.isnan(matrix), np.isnan(expected_matrix)), "undefined matrix entries must remain missing, not zero"
    assert np.allclose(matrix, expected_matrix, atol=NUMERIC_ATOL, rtol=NUMERIC_RTOL, equal_nan=True), "matrix must be available-case equal-experiment density means"
    assert np.allclose(matrix, reference["matrix"], atol=NUMERIC_ATOL, rtol=NUMERIC_RTOL, equal_nan=True), "matrix differs from source-derived reference"
    for i, source in enumerate(sources):
        for j, target in enumerate(targets):
            actual = support_rows[(int(source), int(target))]
            assert actual == (int(observed[i, j]), int(expected[i, j])), "matrix observed/expected denominator differs"
    return matrix, observed, expected


def source_descriptors(matrix, sources, targets, expected):
    result = {}
    for i, source in enumerate(sources):
        missing = int(np.isnan(matrix[i]).sum())
        row = {"status": "incomplete" if missing else "complete", "n_missing_targets": missing,
               "n_experiments": int(expected[i, 0]), "strongest_targets": set(),
               "is_self_strongest": None, "max_density": np.nan}
        if not missing:
            maximum = float(np.max(matrix[i]))
            tied = set(map(int, targets[np.isclose(matrix[i], maximum, atol=TIE_ATOL, rtol=0)]))
            row.update(max_density=maximum, strongest_targets=tied, is_self_strongest=int(source) in tied)
        result[int(source)] = row
    return result


def validate_strongest(rows, matrix, observed, expected, reference):
    # Numeric CSV tolerances must not turn rounding into a new tie, change a
    # zero maximum, or identify an incomplete source. Categorize the frozen,
    # full-precision source means rather than the rounded submitted matrix.
    authoritative_matrix, _, authoritative_expected = aggregate_receipt(reference, reference["source_ids"])
    descriptors = source_descriptors(authoritative_matrix, reference["source_ids"],
                                     reference["target_ids"], authoritative_expected)
    assert set(rows) == set(descriptors), "exact strongest-source membership required"
    for source, expected_row in descriptors.items():
        actual = rows[source]
        for key in ("status", "n_missing_targets", "n_experiments", "strongest_targets", "is_self_strongest"):
            assert actual[key] == expected_row[key], f"incorrect source {source} {key}"
        if expected_row["status"] == "incomplete":
            assert np.isnan(actual["max_density"]), "incomplete source has no identifiable full-target maximum"
        else:
            assert np.isclose(number(actual["max_density"]), expected_row["max_density"], atol=NUMERIC_ATOL, rtol=NUMERIC_RTOL), "source maximum does not match matrix"
    return descriptors


def summary_metrics(descriptors, arrays, reference):
    complete = [row for row in descriptors.values() if row["status"] == "complete"]
    n_self = sum(row["is_self_strongest"] for row in complete)
    return {"n_experiments": len(reference["experiment_ids"]), "n_target_structures": len(reference["target_ids"]),
        "n_source_regions": len(reference["source_ids"]), "n_eligible_sources": len(complete),
        "n_self_strongest": int(n_self), "self_strongest_fraction": n_self/len(complete) if complete else None,
        "n_zero_max_sources": sum(row["max_density"] == 0 for row in complete),
        "n_tied_max_sources": sum(len(row["strongest_targets"]) > 1 for row in complete),
        "record_status_counts": {status: int(np.sum(arrays["record_status"] == status)) for status in RECORD_STATUSES}}


def validate_summary_values(document, expected):
    for key, value in expected.items():
        if key == "record_status_counts":
            assert isinstance(document[key], dict) and set(document[key]) == set(RECORD_STATUSES), "incorrect record-status count fields"
            for status, count in value.items():
                assert integer(document[key][status]) == count, "incorrect source record-status count"
        elif key == "self_strongest_fraction":
            if value is None:
                assert document[key] is None, "undefined fraction must be null"
            else:
                assert 0 <= number(document[key]) <= 1 and abs(number(document[key])-value) <= SUMMARY_ATOL, "self fraction must use eligible complete sources"
        else:
            assert integer(document[key]) == value, f"incorrect recomputed {key}"


def validate_results(result, descriptors, arrays, reference):
    assert result.get("status") == "ok" and result.get("pipeline_id") == PIPELINE_ID, "incorrect result status/pipeline"
    expected = summary_metrics(descriptors, arrays, reference)
    assert expected["n_eligible_sources"] > 0, "failed_precondition: no identifiable full-target source rows"
    validate_summary_values(result, expected)
    return expected


def validate_metadata(metadata, expected, reference):
    assert metadata.get("status") == "ok", "metadata status must be ok"
    match_contract(metadata, reference["stats"]["metadata_contract"])
    assert metadata["source_sha256"] == reference["stats"]["source_sha256"], "source hash mapping differs"
    validate_summary_values(metadata, expected)


def validate_output_directory(output, reference):
    output = Path(output)
    arrays = validate_experiment_targets(load_experiment_targets(output / "experiment_targets.csv"), reference)
    matrix, observed, expected = validate_matrix(load_matrix(output / "connectivity_matrix.csv", reference["target_ids"]),
        load_support(output / "matrix_support.csv"), arrays, reference)
    descriptors = validate_strongest(load_strongest(output / "source_strongest.csv"), matrix, observed, expected, reference)
    summary = validate_results(read_json(output / "self_projection.json"), descriptors, arrays, reference)
    validate_metadata(read_json(output / "run_metadata.json"), summary, reference)
    assert (output / "findings.md").read_text(encoding="utf-8").strip(), "nonempty findings required"
    return summary
