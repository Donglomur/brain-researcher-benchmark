"""Tiny parser/algebra fixtures; neither scientific data nor a reference bank."""
import copy
import csv
import json
from pathlib import Path
import sys
import numpy as np
import pytest

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK / "tests"))
import proof_of_work as q


def mechanical_reference():
    truth = np.array(q.CATEGORIES * 3)
    predicted = truth.copy()
    predicted[[0, 9, 18]] = ["cat", "chair", "face"]
    reference = dict(volume_id=np.arange(24) * 2, run=np.repeat([0, 1, 2], 8),
                     true_label=truth, predicted_label=predicted, run_ids=np.arange(3),
                     mask_ijk=np.array([[0, 0, k] for k in range(6)]),
                     selected_indices=np.array([[0, 2], [1, 4], [3, 5]]),
                     selected_f=np.array([[1., 2.], [3., 4.], [5., 6.]]))
    contract = {"pipeline_id": q.PIPELINE_ID, "source_sha256": {"tiny-parser-fixture": "0"*64},
                "feature_selection": {"n_selected": 2, "fit_on": "training_runs_only"}}
    reference["stats"] = dict(pipeline_id=q.PIPELINE_ID, source_sha256=contract["source_sha256"],
                              metadata_contract=contract, n_full_volumes=48)
    reference["stats"]["results"] = q.summarize(reference)[0]
    return q.validate_reference(reference)


def write_csv(path, fields, rows):
    with Path(path).open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def emit(output, reference, predicted=None):
    """Serialize in-memory mechanics or retained genuine outputs, never a bank."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    predicted = reference["predicted_label"] if predicted is None else np.asarray(predicted)
    result, folds = q.summarize(reference, predicted)
    write_csv(output / "predictions.csv", q.PREDICTION_FIELDS, [
        dict(volume_id=int(volume), held_out_run=int(reference["run"][index]),
             true_label=str(reference["true_label"][index]), predicted_label=str(predicted[index]))
        for index, volume in enumerate(reference["volume_id"])])
    write_csv(output / "per_fold.csv", q.FOLD_FIELDS, folds)
    write_csv(output / "selected_features.csv", q.FEATURE_FIELDS, [
        dict(held_out_run=int(run), feature_index=int(feature), i=int(reference["mask_ijk"][feature, 0]),
             j=int(reference["mask_ijk"][feature, 1]), k=int(reference["mask_ijk"][feature, 2]),
             f_statistic=float(reference["selected_f"][fold, column]))
        for fold, run in enumerate(reference["run_ids"])
        for column, feature in enumerate(reference["selected_indices"][fold])])
    metadata = copy.deepcopy(reference["stats"]["metadata_contract"])
    metadata.update(status="ok", cleaned_dtype="float64", n_full_volumes=reference["stats"]["n_full_volumes"],
                    **{key: result[key] for key in ("n_samples", "n_voxels", "n_selected", "n_categories", "n_runs")})
    (output / "decoding_results.json").write_text(json.dumps(result, allow_nan=False))
    (output / "run_metadata.json").write_text(json.dumps(metadata, allow_nan=False))
    (output / "findings.md").write_text("A single-subject offline method control.\n")
    return result


@pytest.fixture
def reference():
    return mechanical_reference()


def test_complete_mechanical_receipt(tmp_path, reference):
    emit(tmp_path, reference)
    q.validate_output_directory(tmp_path, reference)


@pytest.mark.parametrize("value", ["7", "7.0", "7e0", " 7.000 "])
def test_equivalent_integer_notation(value):
    assert q.integer(value) == 7


@pytest.mark.parametrize("value", [True, False, "run7", "7.1", "7.0000000000000000001", "NaN", "inf", "", 2**64])
def test_integer_rejects_aliases_rounding_and_boolean(value):
    with pytest.raises(AssertionError):
        q.integer(value)


@pytest.mark.parametrize("value", [True, False, "NaN", "inf", "-inf", ""])
def test_finite_numbers_reject_invalid(value):
    with pytest.raises(AssertionError):
        q.finite(value)


def test_legacy_bank_rejected_without_reading_real_bank(tmp_path):
    path = tmp_path / "obsolete.npz"
    np.savez(path, ref_stats=np.array(json.dumps({"pipeline_id": "legacy"})))
    with pytest.raises(AssertionError, match="obsolete"):
        q.load_reference(path)


def test_mechanical_fixture_never_qualifies_as_production_bank(reference):
    with pytest.raises(AssertionError, match="864 source volumes"):
        q.validate_production_reference(reference)


def test_constant_performance_and_below_chance_not_forbidden(tmp_path, reference):
    reference = copy.deepcopy(reference)
    reference["predicted_label"] = np.array([q.CATEGORIES[(q.CATEGORIES.index(label)+1)%8] for label in reference["true_label"]])
    reference["stats"]["results"] = q.summarize(reference)[0]
    q.validate_reference(reference)
    emit(tmp_path, reference)
    assert q.validate_output_directory(tmp_path, reference)["cv_accuracy"] == 0


def test_order_and_extra_fields_are_not_requirements(tmp_path, reference):
    emit(tmp_path, reference)
    for filename, fields in (("predictions.csv", q.PREDICTION_FIELDS), ("per_fold.csv", q.FOLD_FIELDS),
                             ("selected_features.csv", q.FEATURE_FIELDS)):
        rows = q.read_csv(tmp_path / filename, fields)[::-1]
        for row in rows:
            row["comment"] = "extra"
        write_csv(tmp_path / filename, ["comment", *fields[::-1]], rows)
    (tmp_path / "findings.md").write_text("Measured.\n")
    q.validate_output_directory(tmp_path, reference)


@pytest.mark.parametrize("defect", ["drop", "duplicate", "unknown", "wrong_coordinate", "wrong_f", "nonfinite_f", "negative_f"])
def test_feature_receipts_are_complete_and_source_bound(tmp_path, reference, defect):
    emit(tmp_path, reference)
    rows = q.read_csv(tmp_path / "selected_features.csv", q.FEATURE_FIELDS)
    if defect == "drop": rows.pop()
    elif defect == "duplicate": rows.append(dict(rows[0]))
    elif defect == "unknown": rows[0]["feature_index"] = "100"
    elif defect == "wrong_coordinate": rows[0]["k"] = "5"
    elif defect == "wrong_f": rows[0]["f_statistic"] = "999"
    elif defect == "nonfinite_f": rows[0]["f_statistic"] = "NaN"
    elif defect == "negative_f": rows[0]["f_statistic"] = "-1"
    write_csv(tmp_path / "selected_features.csv", q.FEATURE_FIELDS, rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(tmp_path, reference)


def test_f_tolerance_does_not_relax_feature_membership(tmp_path, reference):
    emit(tmp_path, reference)
    rows = q.read_csv(tmp_path / "selected_features.csv", q.FEATURE_FIELDS)
    rows[0]["f_statistic"] = str(float(rows[0]["f_statistic"])+q.F_ATOL*.5)
    write_csv(tmp_path / "selected_features.csv", q.FEATURE_FIELDS, rows)
    q.validate_output_directory(tmp_path, reference)
    rows[0]["feature_index"] = "1"
    rows[0]["k"] = "1"
    write_csv(tmp_path / "selected_features.csv", q.FEATURE_FIELDS, rows)
    with pytest.raises(AssertionError, match="selected feature"):
        q.validate_output_directory(tmp_path, reference)


def test_metadata_requires_public_contract_not_prose_claim(tmp_path, reference):
    emit(tmp_path, reference)
    metadata = q.load_json(tmp_path / "run_metadata.json")
    metadata["feature_selection"]["fit_on"] = "all_runs"
    (tmp_path / "run_metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(AssertionError, match="public contract"):
        q.validate_output_directory(tmp_path, reference)


@pytest.mark.parametrize("result_status", ["ok", "success"])
@pytest.mark.parametrize("metadata_status", ["ok", "success"])
def test_equivalent_success_statuses(tmp_path, reference, result_status, metadata_status):
    emit(tmp_path, reference)
    for filename, status in (("decoding_results.json", result_status),
                             ("run_metadata.json", metadata_status)):
        document = q.load_json(tmp_path / filename)
        document["status"] = status
        (tmp_path / filename).write_text(json.dumps(document))
    q.validate_output_directory(tmp_path, reference)


@pytest.mark.parametrize("filename", ["decoding_results.json", "run_metadata.json"])
@pytest.mark.parametrize("status", [None, "", "partial", "failed_precondition", "SUCCESS", True, 1, [], {}])
def test_success_alias_does_not_accept_invalid_status(tmp_path, reference, filename, status):
    emit(tmp_path, reference)
    document = q.load_json(tmp_path / filename)
    document["status"] = status
    (tmp_path / filename).write_text(json.dumps(document))
    with pytest.raises(AssertionError, match="status"):
        q.validate_output_directory(tmp_path, reference)


@pytest.mark.parametrize("filename", ["decoding_results.json", "run_metadata.json"])
def test_success_status_is_still_required(tmp_path, reference, filename):
    emit(tmp_path, reference)
    document = q.load_json(tmp_path / filename)
    del document["status"]
    (tmp_path / filename).write_text(json.dumps(document))
    with pytest.raises(AssertionError, match="status"):
        q.validate_output_directory(tmp_path, reference)


@pytest.mark.parametrize("defect", ["accuracy", "source_hash", "pipeline_id", "prediction", "feature", "count"])
def test_success_alias_does_not_relax_scientific_or_identity_checks(tmp_path, reference, defect):
    emit(tmp_path, reference)
    result = q.load_json(tmp_path / "decoding_results.json")
    metadata = q.load_json(tmp_path / "run_metadata.json")
    result["status"] = metadata["status"] = "success"
    if defect == "accuracy": result["cv_accuracy"] += .1
    elif defect == "source_hash": metadata["source_sha256"]["tiny-parser-fixture"] = "1" * 64
    elif defect == "pipeline_id": result["pipeline_id"] = "wrong"
    elif defect == "count": metadata["n_samples"] += 1
    elif defect == "prediction":
        rows = q.read_csv(tmp_path / "predictions.csv", q.PREDICTION_FIELDS)
        rows[0]["predicted_label"] = "shoe"
        write_csv(tmp_path / "predictions.csv", q.PREDICTION_FIELDS, rows)
    elif defect == "feature":
        rows = q.read_csv(tmp_path / "selected_features.csv", q.FEATURE_FIELDS)
        rows[0]["f_statistic"] = "999"
        write_csv(tmp_path / "selected_features.csv", q.FEATURE_FIELDS, rows)
    (tmp_path / "decoding_results.json").write_text(json.dumps(result))
    (tmp_path / "run_metadata.json").write_text(json.dumps(metadata))
    with pytest.raises(AssertionError):
        q.validate_output_directory(tmp_path, reference)


def test_explicit_anova_arithmetic():
    from build_reference import anova_scores
    x = np.array([[1., 10.], [2., 20.], [3., 30.], [4., 40.]])
    scores = anova_scores(x, np.array(["a", "a", "b", "b"]))
    np.testing.assert_allclose(scores, [8., 8.], atol=1e-12)


def test_stable_anova_ties_prefer_larger_feature_index():
    from build_reference import selected_indices
    np.testing.assert_array_equal(selected_indices(np.array([1., 2., 2., 2., np.nan]), 2), [2, 3])


def test_selected_nonfinite_anova_fails_precondition():
    from build_reference import selected_indices
    with pytest.raises(AssertionError, match="finite"):
        selected_indices(np.array([1., np.inf]), 1)


def test_raw_libsvm_votes_and_ovr_display_zero_tie_differ():
    from build_reference import pairwise_outputs
    labels, scores = pairwise_outputs(np.array([[0.], [1.], [-1.]]), np.array(["a", "b"]))
    assert labels.tolist() == ["b", "a", "b"]
    assert np.argmax(scores, axis=1).tolist() == [0, 0, 1]
