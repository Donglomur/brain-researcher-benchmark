"""Full-verifier mutations of retained real Sleep-EDF classifier outputs."""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = ("epoch_predictions.csv", "confusion_counts.csv", "per_subject.csv",
         "staging_results.json", "run_metadata.json", "findings.md")
CLASSES = ("W", "N1", "N2", "N3", "REM")


def verify(output):
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(ROOT / "tests/test_outputs.py")],
        env={**os.environ, "OUTPUT_DIR": str(output), "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"},
        capture_output=True, text=True, timeout=60,
    )


@pytest.fixture(scope="module")
def oracle():
    source = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not source:
        pytest.skip("requires retained real-data oracle output and regenerated reference")
    source = Path(source)
    for name in FILES:
        assert (source / name).is_file(), f"missing actual oracle output: {name}"
    result = verify(source)
    assert result.returncode == 0, result.stdout + result.stderr
    return source


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def other_class(*excluded):
    return next(value for value in CLASSES if value not in excluded)


@pytest.mark.parametrize("defect", [
    "none", "row_order", "numeric_format", "extra_columns", "free_prose", "optional_lower",
    "empty", "missing_epoch", "duplicate_epoch", "shifted_onset", "recording", "heldout_subject",
    "true_class", "wrong_category_same_accuracy", "class_permuted_counts", "missing_count_cell",
    "negative_count", "fractional_count", "subject_kappa", "mean_subject_kappa",
    "nan_accuracy", "epoch_count", "missing_metadata", "source_hash", "metadata_cv",
])
def test_actual_outputs_full_verifier(oracle, tmp_path, defect):
    for name in FILES:
        shutil.copy2(oracle / name, tmp_path / name)
    epochs = read_csv(tmp_path / "epoch_predictions.csv")
    counts = read_csv(tmp_path / "confusion_counts.csv")
    subjects = read_csv(tmp_path / "per_subject.csv")
    result = json.loads((tmp_path / "staging_results.json").read_text())
    metadata = json.loads((tmp_path / "run_metadata.json").read_text())
    if defect == "row_order":
        epochs.reverse()
        counts.reverse()
        subjects.reverse()
    elif defect == "numeric_format":
        for row in epochs:
            for field in ("subject", "recording", "onset_sample", "heldout_subject"):
                row[field] = f'{float(row[field]):.1f}'
        for row in counts:
            for field in ("subject", "n_epochs"):
                row[field] = f'{float(row[field]):.1f}'
        for row in subjects:
            for field in ("subject", "n_test_epochs"):
                row[field] = f'{float(row[field]):.1f}'
            for field in ("accuracy", "kappa"):
                row[field] = f'{float(row[field]):.6f}'
        result["accuracy"] = round(result["accuracy"], 5)
        result["cohen_kappa"] = round(result["cohen_kappa"], 5)
    elif defect == "extra_columns":
        for rows in (epochs, counts, subjects):
            for row in rows:
                row["description"] = "additional context"
        metadata["description"] = "additional context"
    elif defect == "free_prose":
        (tmp_path / "findings.md").write_text("每次留出一名被试。预测、混淆矩阵和汇总结果见输出表。\n")
    elif defect == "optional_lower":
        result["random_epoch_accuracy_for_sensitivity"] = 0.0
    elif defect == "missing_epoch":
        epochs.pop()
    elif defect == "duplicate_epoch":
        epochs.append(epochs[0])
    elif defect == "shifted_onset":
        epochs[0]["onset_sample"] = str(int(epochs[0]["onset_sample"]) + 1)
    elif defect == "recording":
        epochs[0]["recording"] = "2"
    elif defect == "heldout_subject":
        epochs[0]["heldout_subject"] = str((int(epochs[0]["subject"]) + 1) % 6)
    elif defect == "true_class":
        epochs[0]["true_class"] = other_class(epochs[0]["true_class"])
    elif defect == "wrong_category_same_accuracy":
        row = next(row for row in epochs if row["predicted_class"] != row["true_class"])
        row["predicted_class"] = other_class(row["true_class"], row["predicted_class"])
    elif defect == "class_permuted_counts":
        permutation = dict(zip(CLASSES, CLASSES[1:] + CLASSES[:1]))
        for row in counts:
            row["true_class"] = permutation[row["true_class"]]
            row["predicted_class"] = permutation[row["predicted_class"]]
        # Simultaneous row/column relabelling preserves accuracy and kappa.
    elif defect == "missing_count_cell":
        counts.pop()
    elif defect == "negative_count":
        counts[0]["n_epochs"] = "-1"
    elif defect == "fractional_count":
        counts[0]["n_epochs"] = "0.5"
    elif defect == "subject_kappa":
        subjects[0]["kappa"] = str(float(subjects[0]["kappa"]) + 0.01)
    elif defect == "mean_subject_kappa":
        mean = sum(float(row["kappa"]) for row in subjects) / len(subjects)
        assert abs(mean - result["cohen_kappa"]) > 1e-5, "control needs distinct pooled and mean kappa"
        result["cohen_kappa"] = mean
    elif defect == "nan_accuracy":
        result["accuracy"] = float("nan")
    elif defect == "epoch_count":
        result["n_epochs"] += 1
    elif defect == "source_hash":
        key = next(iter(metadata["source_sha256"]))
        metadata["source_sha256"][key] = "0" * 64
    elif defect == "metadata_cv":
        metadata["cv_scheme"] = "random-epoch-kfold"

    write_csv(tmp_path / "epoch_predictions.csv", epochs)
    write_csv(tmp_path / "confusion_counts.csv", counts)
    write_csv(tmp_path / "per_subject.csv", subjects)
    (tmp_path / "staging_results.json").write_text(json.dumps(result))
    (tmp_path / "run_metadata.json").write_text(json.dumps(metadata))
    if defect == "missing_metadata":
        (tmp_path / "run_metadata.json").unlink()
    elif defect == "empty":
        for name in FILES:
            (tmp_path / name).unlink()
    checked = verify(tmp_path)
    positive = defect in ("none", "row_order", "numeric_format", "extra_columns", "free_prose", "optional_lower")
    assert checked.returncode == (0 if positive else 1), checked.stdout + checked.stderr
    if defect == "wrong_category_same_accuracy":
        assert "source-indexed predictions differ" in checked.stdout
    if defect == "class_permuted_counts":
        assert "confusion cells do not recompute" in checked.stdout
