"""Four concise checks; the reference is measured from original source data."""
import os
from pathlib import Path
import proof_of_work as q

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))


def test_source_indexed_oof_predictions():
    q.read_predictions(OUT, q.load_reference())


def test_every_fold_score_recomputes():
    reference = q.load_reference()
    q.read_folds(OUT, reference, q.read_predictions(OUT, reference))


def test_all_training_fold_feature_receipts():
    q.read_features(OUT, q.load_reference())


def test_results_metadata_and_findings():
    q.validate_output_directory(OUT, q.load_reference())
