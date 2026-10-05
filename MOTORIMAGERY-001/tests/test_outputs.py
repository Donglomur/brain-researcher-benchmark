"""Four groups: source membership, OOF models, inference and metadata."""
import os
from pathlib import Path
import pytest
import proof_of_work as q

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


@pytest.fixture(scope="session")
def reference(): return q.load_reference()


@pytest.fixture(scope="session")
def predictions(reference): return q.load_predictions(OUT/"oof_predictions.csv", reference)[1]


def test_source_epochs_and_required_files(reference):
    q.require_files(OUT)
    q.validate_source_ledger(OUT/"source_epochs.csv", reference)


def test_complete_source_bound_oof_scores_and_permutation_targets(predictions, reference):
    assert predictions.shape == reference["targets"].shape


def test_fold_subject_and_group_statistics(predictions, reference):
    subjects, folds, result = q.statistics_from_predictions(reference["subject"], reference["run"], reference["targets"], predictions)
    q.validate_folds(OUT/"fold_receipts.csv", folds)
    q.validate_subjects(OUT/"per_subject.csv", subjects)
    q.match_values(q.load_json(OUT/"decoding_results.json"), result, "group")


def test_public_metadata_and_complete_run_inventory(reference):
    q.validate_metadata(OUT/"run_metadata.json", reference)
