"""Source-bound complete OOF predictions and train-fold feature receipts.

The public recipe is fixed. No performance, variation, correlation, select-once
contrast or prose-keyword gate is part of verification.
"""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import numpy as np

PIPELINE_ID = "haxby2-runwise-anova500-loro-v2"
CATEGORIES = ("bottle", "cat", "chair", "face", "house", "scissors", "scrambledpix", "shoe")
F_ATOL, F_RTOL, SCORE_ATOL = 1e-8, 1e-6, 1e-6
PREDICTION_FIELDS = ("volume_id", "held_out_run", "true_label", "predicted_label")
FOLD_FIELDS = ("fold", "held_out_run", "n_train_samples", "n_test_samples", "accuracy")
FEATURE_FIELDS = ("held_out_run", "feature_index", "i", "j", "k", "f_statistic")
FILES = ("predictions.csv", "per_fold.csv", "selected_features.csv",
         "decoding_results.json", "run_metadata.json", "findings.md")


def finite(value, name="number"):
    assert not isinstance(value, (bool, np.bool_)), f"{name}: boolean is not numeric"
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise AssertionError(f"{name}: finite number required") from error
    assert np.isfinite(result), f"{name}: finite number required"
    return result


def integer(value, name="integer"):
    assert not isinstance(value, (bool, np.bool_)), f"{name}: boolean is not an integer"
    try:
        result = Decimal(str(value).strip())
    except (InvalidOperation, ValueError) as error:
        raise AssertionError(f"{name}: exact integer required") from error
    assert result.is_finite() and result == result.to_integral_value(), f"{name}: exact integer required"
    assert abs(result) <= 2**63 - 1, f"{name}: outside int64"
    return int(result)


def load_json(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as error:
        raise AssertionError(f"cannot read {path}") from error
    assert isinstance(value, dict), f"{path}: object required"
    return value


def read_csv(path, fields):
    try:
        with Path(path).open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            assert reader.fieldnames is not None, "CSV header required"
            reader.fieldnames = [name.strip() for name in reader.fieldnames]
            assert len(set(reader.fieldnames)) == len(reader.fieldnames), "duplicate CSV column"
            assert set(fields) <= set(reader.fieldnames), f"required columns missing: {Path(path).name}"
            rows = []
            for row in reader:
                assert None not in row, "unlabelled CSV cells"
                if not any(str(value or "").strip() for value in row.values()):
                    continue
                assert all(row.get(key) is not None for key in fields), "truncated CSV row"
                rows.append({key: value.strip() if isinstance(value, str) else value
                             for key, value in row.items()})
    except OSError as error:
        raise AssertionError(f"cannot read {path}") from error
    return rows


def close(actual, expected, name, atol=SCORE_ATOL, rtol=0):
    actual, expected = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    assert actual.shape == expected.shape, f"{name}: shape mismatch"
    assert np.isfinite(actual).all() and np.isfinite(expected).all(), f"{name}: nonfinite values"
    assert np.allclose(actual, expected, atol=atol, rtol=rtol), f"{name}: numeric mismatch"


def match_metadata(actual, expected, name="metadata"):
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{name}: object required"
        if name.endswith("source_sha256") or name.endswith("input_hashes"):
            assert actual == expected, f"{name}: source identity mismatch"
            return
        for key, value in expected.items():
            assert key in actual, f"{name}: missing {key}"
            match_metadata(actual[key], value, name + "." + key)
    elif isinstance(expected, list):
        assert isinstance(actual, list) and len(actual) == len(expected), f"{name}: list mismatch"
        for index, value in enumerate(expected):
            match_metadata(actual[index], value, f"{name}[{index}]")
    elif expected is None or isinstance(expected, (str, bool)):
        assert type(actual) is type(expected) and actual == expected, f"{name}: public contract mismatch"
    elif isinstance(expected, int):
        assert integer(actual, name) == expected, f"{name}: public contract mismatch"
    else:
        tolerance = 1e-6 if any(part in name for part in ("affine", "voxel_size", "header_zooms")) else 1e-12 * abs(expected)
        assert abs(finite(actual, name) - expected) <= tolerance, f"{name}: public contract mismatch"


def summarize(reference, predicted=None):
    predicted = reference["predicted_label"] if predicted is None else np.asarray(predicted)
    truth, runs = reference["true_label"], reference["run"]
    assert predicted.shape == truth.shape and np.isin(predicted, CATEGORIES).all()
    fold_rows = []
    for fold, run in enumerate(reference["run_ids"], 1):
        test = runs == run
        fold_rows.append(dict(fold=fold, held_out_run=int(run), n_train_samples=int((~test).sum()),
                              n_test_samples=int(test.sum()), accuracy=float(np.mean(predicted[test] == truth[test]))))
    result = dict(status="ok", pipeline_id=PIPELINE_ID,
                  cv_accuracy=float(np.mean([row["accuracy"] for row in fold_rows])),
                  n_samples=len(truth), n_voxels=len(reference["mask_ijk"]),
                  n_selected=int(reference["selected_indices"].shape[1]),
                  n_categories=len(CATEGORIES), n_runs=len(reference["run_ids"]), chance=1 / len(CATEGORIES))
    return result, fold_rows


def require_success_status(value, name):
    assert isinstance(value, str) and value in ("ok", "success"), f"{name}: success status required"


def match_results(actual, expected):
    for key, value in expected.items():
        assert key in actual, f"results missing {key}"
        if key == "status" and value == "ok":
            require_success_status(actual[key], "results status")
        elif isinstance(value, int):
            assert integer(actual[key], key) == value, f"results {key}: count mismatch"
        elif isinstance(value, str):
            assert actual[key] == value, f"results {key}: mismatch"
        else:
            close(finite(actual[key], key), value, "results " + key)


def read_predictions(output, reference):
    rows = read_csv(Path(output) / "predictions.csv", PREDICTION_FIELDS)
    expected = {int(value): index for index, value in enumerate(reference["volume_id"])}
    found, predicted = set(), np.empty(len(expected), dtype="U32")
    for row in rows:
        volume = integer(row["volume_id"], "volume_id")
        assert volume in expected and volume not in found, "unknown or duplicate source volume"
        found.add(volume)
        index = expected[volume]
        assert integer(row["held_out_run"], "held_out_run") == reference["run"][index], "wrong source run"
        assert row["true_label"] == reference["true_label"][index], "wrong source category"
        assert row["predicted_label"] in CATEGORIES, "unknown predicted category"
        assert row["predicted_label"] == reference["predicted_label"][index], "predicted label differs from source-bound fit"
        predicted[index] = row["predicted_label"]
    assert found == set(expected), "every source nonrest volume required exactly once"
    return predicted


def read_folds(output, reference, predicted=None):
    _, expected_rows = summarize(reference, predicted)
    expected = {row["held_out_run"]: row for row in expected_rows}
    found = set()
    for row in read_csv(Path(output) / "per_fold.csv", FOLD_FIELDS):
        run = integer(row["held_out_run"], "held_out_run")
        assert run in expected and run not in found, "unknown or duplicate acquisition fold"
        found.add(run)
        for key in FOLD_FIELDS[:-1]:
            assert integer(row[key], key) == expected[run][key], f"fold {key}: mismatch"
        close(finite(row["accuracy"], "fold accuracy"), expected[run]["accuracy"], "fold accuracy")
    assert found == set(expected), "every acquisition fold required"
    return expected_rows


def read_features(output, reference):
    expected = {}
    for fold_index, run in enumerate(reference["run_ids"]):
        for column, feature in enumerate(reference["selected_indices"][fold_index]):
            expected[(int(run), int(feature))] = (reference["mask_ijk"][feature],
                                                   reference["selected_f"][fold_index, column])
    found = set()
    for row in read_csv(Path(output) / "selected_features.csv", FEATURE_FIELDS):
        key = (integer(row["held_out_run"], "held_out_run"), integer(row["feature_index"], "feature_index"))
        assert key in expected and key not in found, "unknown, wrong-fold or duplicate selected feature"
        found.add(key)
        coordinates, score = expected[key]
        submitted = [integer(row[axis], axis) for axis in ("i", "j", "k")]
        assert np.array_equal(submitted, coordinates), "selected feature coordinate/index mismatch"
        value = finite(row["f_statistic"], "f_statistic")
        close(value, score, "training-fold ANOVA F", atol=F_ATOL, rtol=F_RTOL)
    assert found == set(expected), "complete selected feature receipt required"


def validate_output_directory(output, reference):
    output = Path(output)
    for filename in FILES:
        assert (output / filename).is_file(), f"missing {filename}"
    predicted = read_predictions(output, reference)
    read_folds(output, reference, predicted)
    read_features(output, reference)
    result, _ = summarize(reference, predicted)
    match_results(load_json(output / "decoding_results.json"), result)
    metadata = load_json(output / "run_metadata.json")
    match_metadata(metadata, reference["stats"]["metadata_contract"])
    require_success_status(metadata.get("status"), "metadata status")
    for key in ("n_samples", "n_voxels", "n_selected", "n_categories", "n_runs"):
        assert integer(metadata.get(key), key) == result[key], f"metadata {key}: count mismatch"
    assert integer(metadata.get("n_full_volumes"), "n_full_volumes") == reference["stats"]["n_full_volumes"], "metadata n_full_volumes: mismatch"
    assert metadata.get("cleaned_dtype") == "float64", "metadata cleaned_dtype: mismatch"
    assert (output / "findings.md").read_text(encoding="utf-8-sig").strip(), "findings.md is empty"
    return result


def validate_reference(reference):
    stats = reference["stats"]
    assert stats.get("pipeline_id") == PIPELINE_ID, "obsolete reference; genuine source-derived fit required"
    contract = stats["metadata_contract"]
    assert contract["pipeline_id"] == PIPELINE_ID
    assert contract["source_sha256"] == stats["source_sha256"], "bank source identity mismatch"
    for key in ("volume_id", "run", "run_ids"):
        values = reference[key]
        assert values.ndim == 1 and values.dtype.kind in "iu" and (values >= 0).all(), f"bank {key}: invalid IDs"
    n = len(reference["volume_id"])
    assert n > 0 and len(set(reference["volume_id"])) == n
    assert reference["run"].shape == (n,)
    assert np.array_equal(reference["run_ids"], np.unique(reference["run"])), "bank runs must be source-sorted"
    for key in ("true_label", "predicted_label"):
        assert reference[key].shape == (n,) and np.isin(reference[key], CATEGORIES).all(), f"bank {key}: invalid labels"
    coordinates = reference["mask_ijk"]
    assert coordinates.ndim == 2 and coordinates.shape[1] == 3 and coordinates.dtype.kind in "iu"
    assert np.all(coordinates >= 0) and len(set(map(tuple, coordinates))) == len(coordinates)
    assert list(map(tuple, coordinates)) == sorted(map(tuple, coordinates)), "bank mask ordering must be C-order"
    selected = reference["selected_indices"]
    assert selected.ndim == 2 and selected.shape[0] == len(reference["run_ids"]) and selected.dtype.kind in "iu"
    assert selected.shape[1] > 0 and np.all((selected >= 0) & (selected < len(coordinates)))
    assert np.all(np.diff(selected, axis=1) > 0), "bank selected feature IDs must be unique ascending"
    assert reference["selected_f"].shape == selected.shape and np.isfinite(reference["selected_f"]).all()
    result, _ = summarize(reference)
    match_results(stats["results"], result)
    return reference


def validate_production_reference(reference):
    """The tiny arithmetic fixtures are not eligible as a production bank."""
    assert len(reference["volume_id"]) == 864, "production bank must have 864 source volumes"
    assert np.array_equal(reference["run_ids"], np.arange(12)), "production bank must have all 12 runs"
    assert reference["selected_indices"].shape == (12, 500), "production bank must have 6000 selected features"
    assert integer(reference["stats"]["n_full_volumes"], "full source volumes") == 1452
    assert np.all(reference["volume_id"] < 1452) and np.all(np.diff(reference["volume_id"]) > 0)
    for run in range(12):
        labels = reference["true_label"][reference["run"] == run]
        assert len(labels) == 72 and all(np.count_nonzero(labels == label) == 9 for label in CATEGORIES)
    fingerprint = reference["stats"].get("public_template_sha256")
    assert isinstance(fingerprint, str) and len(fingerprint) == 64, "bank lacks public template identity"
    candidates = (Path("/app/method_contract.json"), Path(__file__).resolve().parents[1]/"environment/method_contract.json")
    template = next((path for path in candidates if path.is_file()), None)
    assert template is not None, "public method template missing"
    assert hashlib.sha256(template.read_bytes()).hexdigest() == fingerprint, "bank/public template fingerprint mismatch"
    assert load_json(template) == reference["stats"]["metadata_contract"], "bank/public metadata contract mismatch"
    return reference


def load_reference(path=None):
    path = Path(path) if path else Path(__file__).with_name("reference.npz")
    try:
        with np.load(path, allow_pickle=False) as archive:
            stats = json.loads(str(archive["ref_stats"].item()))
            assert stats.get("pipeline_id") == PIPELINE_ID, "obsolete reference; genuine source-derived fit required"
            keys = ("volume_id", "run", "true_label", "predicted_label", "run_ids",
                    "mask_ijk", "selected_indices", "selected_f")
            reference = {key: archive["ref_" + key] for key in keys}
            reference["stats"] = stats
    except (OSError, ValueError, KeyError) as error:
        raise AssertionError("missing, corrupt or obsolete genuine reference") from error
    return validate_production_reference(validate_reference(reference))
