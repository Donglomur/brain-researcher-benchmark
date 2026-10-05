"""Fold arithmetic mechanics; no invented reference-model performance."""
import json
import pytest
from test_contract import q, reference, emit, write_csv


@pytest.mark.parametrize("defect", ["drop", "duplicate", "foreign_run", "wrong_fold", "n_train", "n_test", "accuracy", "nan", "headline"])
def test_exact_fold_membership_and_arithmetic(tmp_path, reference, defect):
    emit(tmp_path, reference)
    rows = q.read_csv(tmp_path / "per_fold.csv", q.FOLD_FIELDS)
    if defect == "drop": rows.pop()
    elif defect == "duplicate": rows.append(dict(rows[0]))
    elif defect == "foreign_run": rows[0]["held_out_run"] = "100"
    elif defect == "wrong_fold": rows[0]["fold"] = "2"
    elif defect == "n_train": rows[0]["n_train_samples"] = "1"
    elif defect == "n_test": rows[0]["n_test_samples"] = "1"
    elif defect == "accuracy": rows[0]["accuracy"] = ".125"
    elif defect == "nan": rows[0]["accuracy"] = "NaN"
    elif defect == "headline":
        result = q.load_json(tmp_path / "decoding_results.json")
        result["cv_accuracy"] = .5
        (tmp_path / "decoding_results.json").write_text(json.dumps(result))
    write_csv(tmp_path / "per_fold.csv", q.FOLD_FIELDS, rows)
    with pytest.raises(AssertionError):
        q.validate_output_directory(tmp_path, reference)
