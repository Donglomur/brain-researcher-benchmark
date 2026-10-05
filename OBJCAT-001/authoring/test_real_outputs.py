"""Actual-output positives and coherent adversaries; never refit source data.

REPAIR_ORACLE_OUTPUT must point to the parent's genuine retained output.
REPAIR_INDEPENDENT_OUTPUT optionally supplies another genuine implementation.
REPAIR_SELECT_ONCE_OUTPUT supplies the genuine globally selected negative control.
All mutations are temporary copies. No test alters the scientific bank.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import numpy as np
import pytest

from test_contract import TASK, q, emit, write_csv


@pytest.fixture(scope="module")
def reference():
    if not os.environ.get("REPAIR_ORACLE_OUTPUT"):
        pytest.skip("genuine original-source output not supplied")
    return q.load_reference()


@pytest.fixture
def output(tmp_path, reference):
    original = Path(os.environ["REPAIR_ORACLE_OUTPUT"])
    assert original.is_dir(), "configured genuine oracle output is missing"
    for name in q.FILES:
        shutil.copy2(original/name, tmp_path/name)
    return tmp_path


def test_genuine_full_output(output, reference):
    q.validate_output_directory(output, reference)


def test_genuine_independent_implementation(reference):
    path = os.environ.get("REPAIR_INDEPENDENT_OUTPUT")
    if not path:
        pytest.skip("genuine independent implementation output not supplied")
    q.validate_output_directory(Path(path), reference)


def test_genuine_select_once_control_rejected_despite_coherent_scores_and_metadata(reference):
    path = os.environ.get("REPAIR_SELECT_ONCE_OUTPUT")
    if not path:
        pytest.skip("genuine select-once classifier output not supplied")
    control = Path(path)
    metadata = q.load_json(control/"run_metadata.json")
    q.match_metadata(metadata, reference["stats"]["metadata_contract"])
    assert metadata["status"] == "ok", "negative must be a completed actual control"
    lookup = {int(volume): index for index, volume in enumerate(reference["volume_id"])}
    predicted = np.empty(len(lookup), dtype="U32")
    found = set()
    for row in q.read_csv(control/"predictions.csv", q.PREDICTION_FIELDS):
        volume = q.integer(row["volume_id"])
        assert volume in lookup and volume not in found
        found.add(volume)
        index = lookup[volume]
        assert q.integer(row["held_out_run"]) == reference["run"][index]
        assert row["true_label"] == reference["true_label"][index]
        assert row["predicted_label"] in q.CATEGORIES
        predicted[index] = row["predicted_label"]
    assert found == set(lookup)
    result, _ = q.summarize(reference, predicted)
    q.match_results(q.load_json(control/"decoding_results.json"), result)
    q.read_folds(control, reference, predicted)
    for key in ("n_samples", "n_voxels", "n_selected", "n_categories", "n_runs"):
        assert q.integer(metadata[key]) == result[key]
    assert q.integer(metadata["n_full_volumes"]) == reference["stats"]["n_full_volumes"]
    assert metadata["cleaned_dtype"] == "float64"
    feature_rows = q.read_csv(control/"selected_features.csv", q.FEATURE_FIELDS)
    control_features = {(q.integer(row["held_out_run"]), q.integer(row["feature_index"]))
                        for row in feature_rows}
    reference_features = {(int(run), int(feature)) for fold, run in enumerate(reference["run_ids"])
                          for feature in reference["selected_indices"][fold]}
    assert len(feature_rows) == len(control_features) == len(reference_features)
    assert control_features != reference_features, "actual negative must change selected membership"
    assert np.any(predicted != reference["predicted_label"]), "actual negative must change predictions"
    with pytest.raises(AssertionError, match="predicted label"):
        q.read_predictions(control, reference)
    with pytest.raises(AssertionError, match="selected feature|ANOVA F"):
        q.read_features(control, reference)
    with pytest.raises(AssertionError):
        q.validate_output_directory(control, reference)


def test_public_template_identity(reference):
    template = q.load_json(TASK/"environment/method_contract.json")
    assert template == reference["stats"]["metadata_contract"]


def test_minimal_public_template_metadata(output, reference):
    template = q.load_json(TASK/"environment/method_contract.json")
    original = q.load_json(output/"run_metadata.json")
    for key in ("status", "n_samples", "n_voxels", "n_selected", "n_categories", "n_runs", "n_full_volumes", "cleaned_dtype"):
        template[key] = original[key]
    (output/"run_metadata.json").write_text(json.dumps(template))
    q.validate_output_directory(output, reference)


def test_formatting_order_and_extra_columns(output, reference):
    integers = {"volume_id", "held_out_run", "fold", "n_train_samples", "n_test_samples", "feature_index", "i", "j", "k"}
    for filename, fields in (("predictions.csv", q.PREDICTION_FIELDS), ("per_fold.csv", q.FOLD_FIELDS),
                             ("selected_features.csv", q.FEATURE_FIELDS)):
        rows = q.read_csv(output/filename, fields)[::-1]
        for row in rows:
            row["annotation"] = "not graded"
            for key in integers & set(row):
                original = q.integer(row[key], key)
                row[key] = f"{original:.17e}"
                assert q.integer(row[key], key) == original, "fixture must preserve original IDs exactly"
        write_csv(output/filename, ["annotation", *fields[::-1]], rows)
    (output/"findings.md").write_text("A measurement on this one subject.\n")
    q.validate_output_directory(output, reference)


def test_private_fit_receipts_not_part_of_submission_contract(output, reference):
    (output/"analysis_arrays.npz").write_bytes(b"not a required artifact")
    q.validate_output_directory(output, reference)


@pytest.mark.parametrize("mutation", ["change_error_label_same_accuracy", "move_error_same_fold", "perfect_guess", "constant_category", "permute_predictions"])
def test_coherent_wrong_predictions_rejected(output, reference, mutation):
    predicted = reference["predicted_label"].copy()
    true = reference["true_label"]
    original_result = q.summarize(reference)[0]
    if mutation == "change_error_label_same_accuracy":
        indices = np.flatnonzero(predicted != true)
        assert len(indices), "negative requires an actual misclassification"
        index = indices[0]
        predicted[index] = next(label for label in q.CATEGORIES if label not in (true[index], predicted[index]))
    elif mutation == "move_error_same_fold":
        changed = False
        for run in reference["run_ids"]:
            wrong = np.flatnonzero((reference["run"] == run) & (predicted != true))
            correct = np.flatnonzero((reference["run"] == run) & (predicted == true))
            if len(wrong) and len(correct):
                predicted[wrong[0]] = true[wrong[0]]
                predicted[correct[0]] = next(label for label in q.CATEGORIES if label != true[correct[0]])
                changed = True
                break
        assert changed, "negative requires an actually mixed-accuracy fold"
    elif mutation == "perfect_guess":
        predicted = true.copy()
    elif mutation == "constant_category":
        predicted[:] = q.CATEGORIES[0]
    else:
        predicted = np.roll(predicted, 1)
    assert np.any(predicted != reference["predicted_label"]), "negative must actually change predictions"
    emit(output, reference, predicted)
    if mutation in ("change_error_label_same_accuracy", "move_error_same_fold"):
        assert q.summarize(reference, predicted)[0] == original_result
    with pytest.raises(AssertionError, match="predicted label"):
        q.validate_output_directory(output, reference)


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "foreign", "rest_volume", "wrong_run", "wrong_true", "wrong_predicted", "prefix_id", "fractional_id", "nonfinite_id"])
def test_prediction_mutations(output, reference, mutation):
    rows = q.read_csv(output/"predictions.csv", q.PREDICTION_FIELDS)
    if mutation == "drop": rows.pop()
    elif mutation == "duplicate": rows.append(dict(rows[0]))
    elif mutation == "foreign": rows[0]["volume_id"] = str(reference["stats"]["n_full_volumes"]+1)
    elif mutation == "rest_volume":
        source_ids = set(reference["volume_id"])
        rows[0]["volume_id"] = str(next(index for index in range(reference["stats"]["n_full_volumes"]) if index not in source_ids))
    elif mutation == "wrong_run": rows[0]["held_out_run"] = str((int(rows[0]["held_out_run"])+1)%12)
    elif mutation == "wrong_true": rows[0]["true_label"] = next(label for label in q.CATEGORIES if label != rows[0]["true_label"])
    elif mutation == "wrong_predicted": rows[0]["predicted_label"] = "imaginary"
    elif mutation == "prefix_id": rows[0]["volume_id"] = "volume"+rows[0]["volume_id"]
    elif mutation == "fractional_id": rows[0]["volume_id"] += ".01"
    else: rows[0]["volume_id"] = "NaN"
    write_csv(output/"predictions.csv", q.PREDICTION_FIELDS, rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output, reference)


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "foreign_run", "same_scores_wrong_run", "wrong_fold", "n_train", "n_test", "accuracy", "nan", "negative"])
def test_fold_mutations(output, reference, mutation):
    rows = q.read_csv(output/"per_fold.csv", q.FOLD_FIELDS)
    if mutation == "drop": rows.pop()
    elif mutation == "duplicate": rows.append(dict(rows[0]))
    elif mutation == "foreign_run": rows[0]["held_out_run"] = "100"
    elif mutation == "same_scores_wrong_run": rows[0]["held_out_run"], rows[1]["held_out_run"] = rows[1]["held_out_run"], rows[0]["held_out_run"]
    elif mutation == "wrong_fold": rows[0]["fold"] = "100"
    elif mutation == "n_train": rows[0]["n_train_samples"] = str(int(rows[0]["n_train_samples"])+1)
    elif mutation == "n_test": rows[0]["n_test_samples"] = str(int(rows[0]["n_test_samples"])+1)
    elif mutation == "accuracy": rows[0]["accuracy"] = str(float(rows[0]["accuracy"])+.01)
    elif mutation == "nan": rows[0]["accuracy"] = "NaN"
    else: rows[0]["accuracy"] = "-.1"
    write_csv(output/"per_fold.csv", q.FOLD_FIELDS, rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output, reference)


@pytest.mark.parametrize("mutation", ["drop", "duplicate", "foreign_run", "foreign_feature", "replace_feature_coherent_ijk", "wrong_i", "wrong_j", "wrong_k", "scaled_f", "shift_f", "nan_f", "inf_f", "negative_f", "all_f_equal", "reused_first_fold_features"])
def test_feature_mutations(output, reference, mutation):
    rows = q.read_csv(output/"selected_features.csv", q.FEATURE_FIELDS)
    if mutation == "drop": rows.pop()
    elif mutation == "duplicate": rows.append(dict(rows[0]))
    elif mutation == "foreign_run": rows[0]["held_out_run"] = "100"
    elif mutation == "foreign_feature": rows[0]["feature_index"] = str(len(reference["mask_ijk"]))
    elif mutation == "replace_feature_coherent_ijk":
        run = int(rows[0]["held_out_run"])
        fold = int(np.flatnonzero(reference["run_ids"] == run)[0])
        excluded = np.setdiff1d(np.arange(len(reference["mask_ijk"])), reference["selected_indices"][fold])
        index = int(excluded[0])
        rows[0]["feature_index"] = str(index)
        for key, value in zip(("i", "j", "k"), reference["mask_ijk"][index]):
            rows[0][key] = str(value)
    elif mutation in ("wrong_i", "wrong_j", "wrong_k"):
        key = mutation[-1]
        rows[0][key] = str(int(rows[0][key])+1)
    elif mutation == "scaled_f":
        for row in rows: row["f_statistic"] = str(float(row["f_statistic"])*2)
    elif mutation == "shift_f": rows[0]["f_statistic"] = str(float(rows[0]["f_statistic"])+1)
    elif mutation == "nan_f": rows[0]["f_statistic"] = "NaN"
    elif mutation == "inf_f": rows[0]["f_statistic"] = "inf"
    elif mutation == "negative_f": rows[0]["f_statistic"] = "-1"
    elif mutation == "all_f_equal":
        for row in rows: row["f_statistic"] = "1"
    else:
        first = [dict(row) for row in rows if int(row["held_out_run"]) == reference["run_ids"][0]]
        rows = [dict(row, held_out_run=int(run)) for run in reference["run_ids"] for row in first]
        assert any(not np.array_equal(reference["selected_indices"][0], values) for values in reference["selected_indices"][1:]), "negative must change real feature membership"
    write_csv(output/"selected_features.csv", q.FEATURE_FIELDS, rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(output, reference)


@pytest.mark.parametrize("field", ["n_samples", "n_voxels", "n_selected", "n_categories", "n_runs", "cv_accuracy", "chance", "status", "pipeline_id"])
def test_result_mutations(output, reference, field):
    result = q.load_json(output/"decoding_results.json")
    result[field] = "wrong" if isinstance(result[field], str) else result[field]+1
    (output/"decoding_results.json").write_text(json.dumps(result))
    with pytest.raises(AssertionError):
        q.validate_output_directory(output, reference)


@pytest.mark.parametrize("field", ["n_samples", "n_voxels", "n_selected", "n_categories", "n_runs", "n_full_volumes", "cleaned_dtype", "status", "pipeline_id", "source_sha256", "extra_source_hash"])
def test_metadata_mutations(output, reference, field):
    metadata = q.load_json(output/"run_metadata.json")
    if field == "source_sha256":
        key = next(iter(metadata[field]))
        metadata[field][key] = "0"*64
    elif field == "extra_source_hash":
        metadata["source_sha256"]["unprovided-source"] = "0"*64
    elif isinstance(metadata[field], str): metadata[field] = "wrong"
    else: metadata[field] += 1
    (output/"run_metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(AssertionError):
        q.validate_output_directory(output, reference)


@pytest.mark.parametrize("filename", q.FILES)
def test_required_artifacts_missing(output, reference, filename):
    (output/filename).unlink()
    with pytest.raises(AssertionError):
        q.validate_output_directory(output, reference)


def test_empty_findings_rejected(output, reference):
    (output/"findings.md").write_text(" \n")
    with pytest.raises(AssertionError, match="empty"):
        q.validate_output_directory(output, reference)
