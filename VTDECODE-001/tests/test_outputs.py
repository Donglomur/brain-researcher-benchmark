"""Grade retained predictions for the publicly specified run-wise SVC recipe."""
import pytest

from proof_of_work import (
    OUT, FOLD_TOL, HEADLINE_TOL, load_reference, load_per_fold,
    read_json, source_labels_path,
)
from prediction_contract import finite_number, validate_metadata, validate_predictions


@pytest.fixture(scope="module")
def reference():
    return load_reference()


def test_source_predictions_and_score_arithmetic(reference):
    validate_predictions(
        OUT, source_labels_path(), reference["stats"]["source_sha256"]["subj1/labels.txt"], reference,
    )


def test_per_fold_and_headline_match_measured_reference(reference):
    folds = load_per_fold()
    for run, expected in zip(reference["run_ids"], reference["fold_acc"]):
        assert abs(folds[int(run)] - expected) <= FOLD_TOL, f"held-out run {run} accuracy differs"
    headline = finite_number(read_json("decoding_results.json")["cv_accuracy"])
    assert abs(headline - reference["stats"]["loro_accuracy"]) <= HEADLINE_TOL


def test_dataset_and_analysis_metadata(reference):
    validate_metadata(OUT, reference)


def test_findings_are_present():
    assert (OUT / "findings.md").read_text(encoding="utf-8").strip(), "findings.md is empty"
