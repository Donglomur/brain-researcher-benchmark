"""Real label-table schema/arithmetic fixtures, not classifier/oracle execution."""
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import pytest
ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("haxby_oof_contract", ROOT / "tests/prediction_contract.py")
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)
SOURCE = ROOT / "environment/data/source_labels.txt"


@pytest.mark.parametrize("defect", [None, "duplicate", "missing", "class", "run", "fold_count", "fold_score", "headline", "missing_fold", "nan_fold", "nan_headline", "boolean_headline", "unknown_category", "duplicate_fold"])
def test_source_membership_and_metrics(tmp_path, defect):
    rows = []
    for volume, line in enumerate(SOURCE.read_text().splitlines()[1:]):
        label, run = line.split()
        if label != "rest":
            rows.append(dict(volume_id=volume, held_out_run=run, true_label=label, predicted_label=label))
    folds = [dict(held_out_run=run, n_test_samples=72, accuracy=1) for run in range(12)]
    report = dict(cv_accuracy=1, n_samples=864, n_runs=12, n_categories=8)
    if defect == "duplicate":
        rows.append(rows[0])
    elif defect == "missing":
        rows.pop()
    elif defect == "class":
        rows[0]["true_label"] = "face" if rows[0]["true_label"] != "face" else "cat"
    elif defect == "run":
        rows[0]["held_out_run"] = 11
    elif defect == "fold_count":
        folds[0]["n_test_samples"] = 73
    elif defect == "fold_score":
        folds[0]["accuracy"] = .5
    elif defect == "headline":
        report["cv_accuracy"] = .5
    elif defect == "missing_fold":
        folds.pop()
    elif defect == "nan_fold":
        folds[0]["accuracy"] = float("nan")
    elif defect == "nan_headline":
        report["cv_accuracy"] = float("nan")
    elif defect == "boolean_headline":
        report["cv_accuracy"] = True
    elif defect == "unknown_category":
        rows[0]["predicted_label"] = "unknown"
    elif defect == "duplicate_fold":
        folds.append(folds[0])
    for filename, values in (("predictions.csv", rows), ("per_fold.csv", folds)):
        with (tmp_path / filename).open("w", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=values[0])
            writer.writeheader()
            writer.writerows(values)
    (tmp_path / "decoding_results.json").write_text(json.dumps(report))
    sha = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if defect:
        with pytest.raises(AssertionError):
            contract.validate_predictions(tmp_path, SOURCE, sha)
    else:
        assert set(contract.validate_predictions(tmp_path, SOURCE, sha)) == set(range(12))
