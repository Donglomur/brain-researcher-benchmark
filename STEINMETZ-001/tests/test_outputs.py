"""Declared single-session decoder reproduction, not independent biological truth."""
import pytest

from proof_of_work import OUT, load_reference, load_trial_predictions, load_folds, read_json
from decoding_contract import validate_predictions, validate_folds, validate_results, validate_metadata


@pytest.fixture(scope="module")
def reference():
    return load_reference()


@pytest.fixture(scope="module")
def predictions(reference):
    return validate_predictions(load_trial_predictions(OUT / "trial_predictions.csv"), reference)


def test_trial_identity_predictions_and_decisions(predictions):
    assert predictions


def test_all_twenty_fold_metrics(predictions, reference):
    validate_folds(load_folds(OUT / "folds.csv"), predictions, reference)


def test_full_factorial_and_training_majority_summaries(predictions, reference):
    validate_results(read_json(OUT / "results.json"), predictions, reference)


def test_public_source_metadata_and_findings(reference):
    validate_metadata(read_json(OUT / "run_metadata.json"), reference)
    assert (OUT / "findings.md").read_text(encoding="utf-8").strip(), "nonempty findings required"
