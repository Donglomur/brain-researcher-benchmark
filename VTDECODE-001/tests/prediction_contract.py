"""Validate source-indexed predictions and recompute the reported accuracies."""
import csv
import hashlib
import json
import math
from collections import defaultdict

import numpy as np

CATEGORIES = {"bottle", "cat", "chair", "face", "house", "scissors", "scrambledpix", "shoe"}
FOLD_TOL = 1e-6
HEADLINE_TOL = 0.000051


def finite_number(value):
    assert not isinstance(value, bool), "a number, not a boolean, is required"
    result = float(value)
    assert math.isfinite(result), "a finite number is required"
    return result


def integer(value):
    result = finite_number(value)
    assert result >= 0 and result.is_integer(), "nonnegative integer source index required"
    return int(result)


def validate_predictions(out, source, expected_sha256, reference=None):
    """Check membership and score arithmetic, plus reference predictions if supplied.

    A reference-free call is useful for isolated schema tests only. The task's
    verifier always supplies the independently retained classifier outputs.
    """
    assert hashlib.sha256(source.read_bytes()).hexdigest() == expected_sha256, "source label bytes changed"
    lines = source.read_text().splitlines()
    assert lines[0].split() == ["labels", "chunks"]
    expected = {}
    for volume, line in enumerate(lines[1:]):
        label, run = line.split()
        if label != "rest":
            assert label in CATEGORIES
            expected[volume] = (integer(run), label)
    with (out / "predictions.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    submitted = {}
    per_run = defaultdict(list)
    for row in rows:
        volume = integer(row["volume_id"])
        assert volume not in submitted and volume in expected, "duplicate/unknown volume"
        run, truth = expected[volume]
        assert integer(row["held_out_run"]) == run, "wrong source run"
        assert row["true_label"] == truth, "wrong source class"
        predicted = row["predicted_label"]
        assert predicted in CATEGORIES, "unknown predicted category"
        submitted[volume] = predicted
        per_run[run].append(predicted == truth)
    assert set(submitted) == set(expected), "all nonrest source volumes required exactly once"
    assert set(per_run) == set(range(12)) and all(len(values) == 72 for values in per_run.values())

    if reference is not None:
        reference_rows = {}
        for volume, run, truth, predicted in zip(
            reference["volume_ids"], reference["prediction_runs"],
            reference["true_labels"], reference["predicted_labels"],
        ):
            volume = integer(volume)
            assert volume not in reference_rows, "duplicate volume in reference"
            assert expected.get(volume) == (integer(run), str(truth)), "reference/source membership mismatch"
            assert predicted in CATEGORIES, "unknown reference prediction"
            reference_rows[volume] = str(predicted)
        assert set(reference_rows) == set(expected), "incomplete reference source membership"
        assert submitted == reference_rows, "source-indexed predictions differ from the pinned SVC result"

    with (out / "per_fold.csv").open(newline="", encoding="utf-8") as stream:
        fold_rows = list(csv.DictReader(stream))
    folds = {}
    for row in fold_rows:
        run = integer(row["held_out_run"])
        assert run in per_run and run not in folds, "duplicate/unknown acquisition fold"
        assert integer(row["n_test_samples"]) == len(per_run[run]), "fold test count mismatch"
        score = finite_number(row["accuracy"])
        assert abs(score - np.mean(per_run[run])) <= FOLD_TOL, "fold score does not recompute"
        folds[run] = score
    assert set(folds) == set(per_run), "every source run must have a fold"
    result = json.loads((out / "decoding_results.json").read_text())
    assert integer(result["n_samples"]) == len(expected)
    assert integer(result["n_runs"]) == 12 and integer(result["n_categories"]) == 8
    headline = finite_number(result["cv_accuracy"])
    assert 0 <= headline <= 1
    assert abs(headline - np.mean(list(folds.values()))) <= HEADLINE_TOL, "headline does not recompute"
    return folds


def validate_metadata(out, reference):
    stats = reference["stats"]
    metadata = json.loads((out / "run_metadata.json").read_text())
    result = json.loads((out / "decoding_results.json").read_text())
    assert isinstance(metadata, dict) and isinstance(result, dict)
    for field, expected in {
        "task_id": "VTDECODE-001", "dataset_id": "haxby2001", "mask": "mask4_vt",
        "pipeline_id": "runwise-clean-loro-v2", "cross_validation": "leave-one-run-out",
    }.items():
        assert metadata[field] == expected, f"incorrect metadata: {field}"
    assert integer(metadata["subject"]) == 1
    for field in ("n_samples", "n_voxels", "n_runs"):
        assert integer(metadata[field]) == stats[field], f"incorrect metadata: {field}"
        assert integer(result[field]) == stats[field], f"incorrect result: {field}"
    assert integer(result["n_categories"]) == stats["n_categories"]
    assert abs(finite_number(result["chance"]) - stats["chance"]) <= 1e-12
    assert metadata["source_sha256"] == stats["source_sha256"], "input provenance does not match the frozen data"
    preprocessing = metadata["preprocessing"]
    assert preprocessing["detrend"] is True
    assert preprocessing["standardize"] == "zscore_sample"
    assert finite_number(preprocessing["t_r"]) == 2.5
    assert preprocessing["cleaning_unit"] == "acquisition_run"
    assert preprocessing["clean_before_rest_removal"] is True
    classifier = metadata["classifier"]
    assert classifier["name"] == "SVC" and classifier["kernel"] == "linear"
    assert finite_number(classifier["C"]) == 1.0
    assert finite_number(classifier["tol"]) == 0.001
    assert classifier["shrinking"] is True
