"""Source-index and score-preserving false-accept mechanics; no real model run."""
import numpy as np
import pytest
from test_contract import q, reference, emit, write_csv


@pytest.mark.parametrize("defect", ["duplicate", "missing", "class", "run", "wrong_prediction", "prefixed_id", "fractional_id"])
def test_source_membership_and_predictions(tmp_path, reference, defect):
    emit(tmp_path, reference)
    rows = q.read_csv(tmp_path / "predictions.csv", q.PREDICTION_FIELDS)
    if defect == "duplicate": rows.append(dict(rows[0]))
    elif defect == "missing": rows.pop()
    elif defect == "class": rows[0]["true_label"] = "face"
    elif defect == "run": rows[0]["held_out_run"] = "2"
    elif defect == "wrong_prediction": rows[0]["predicted_label"] = "shoe"
    elif defect == "prefixed_id": rows[0]["volume_id"] = "volume0"
    elif defect == "fractional_id": rows[0]["volume_id"] = ".5"
    write_csv(tmp_path / "predictions.csv", q.PREDICTION_FIELDS, rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(tmp_path, reference)


def test_same_accuracy_wrong_misclassification_rejected(tmp_path, reference):
    predicted = reference["predicted_label"].copy()
    assert predicted[0] != reference["true_label"][0]
    predicted[0] = "shoe"
    assert predicted[0] != reference["true_label"][0]
    emit(tmp_path, reference, predicted)
    assert q.summarize(reference, predicted)[0] == q.summarize(reference)[0]
    with pytest.raises(AssertionError, match="predicted label"):
        q.validate_output_directory(tmp_path, reference)


def test_coherent_perfect_guesses_are_not_source_fit(tmp_path, reference):
    emit(tmp_path, reference, reference["true_label"])
    with pytest.raises(AssertionError, match="predicted label"):
        q.validate_output_directory(tmp_path, reference)
