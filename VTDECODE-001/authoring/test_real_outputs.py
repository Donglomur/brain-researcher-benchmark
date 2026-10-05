"""Mutate actual retained oracle outputs and exercise the complete verifier.

Set REPAIR_ORACLE_OUTPUT to a real output directory after regenerating the bank.
No synthetic labels, predictions, or scientific reference are created here.
"""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = ("predictions.csv", "per_fold.csv", "decoding_results.json", "run_metadata.json", "findings.md")
CATEGORIES = ("bottle", "cat", "chair", "face", "house", "scissors", "scrambledpix", "shoe")


def verify(output):
    env = dict(os.environ, OUTPUT_DIR=str(output), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
    env.pop("DECODE_REFERENCE", None)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", str(ROOT / "tests/test_outputs.py")],
        env=env, capture_output=True, text=True, timeout=60,
    )


@pytest.fixture(scope="module")
def oracle():
    source = os.environ.get("REPAIR_ORACLE_OUTPUT")
    if not source:
        pytest.skip("requires retained real-data oracle outputs, not a fabricated reference")
    source = Path(source)
    for name in FILES:
        assert (source / name).is_file(), f"missing retained output: {name}"
    result = verify(source)
    assert result.returncode == 0, result.stdout + result.stderr
    return source


def copy_outputs(source, target):
    for name in FILES:
        shutil.copy2(source / name, target / name)


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def other_category(*excluded):
    return next(category for category in CATEGORIES if category not in excluded)


@pytest.mark.parametrize("defect", [
    "none", "row_order", "numeric_format", "free_prose", "empty", "missing", "duplicate",
    "source_run", "source_class", "score_preserving_wrong_category", "all_perfect", "constant_fabricated",
    "nan_fold", "nan_headline", "headline", "voxel_count", "chance", "missing_metadata",
    "global_metadata", "source_hash",
])
def test_actual_outputs_full_verifier(oracle, tmp_path, defect):
    copy_outputs(oracle, tmp_path)
    predictions = read_csv(tmp_path / "predictions.csv")
    folds = read_csv(tmp_path / "per_fold.csv")
    result = json.loads((tmp_path / "decoding_results.json").read_text())
    metadata = json.loads((tmp_path / "run_metadata.json").read_text())
    if defect == "row_order":
        predictions.reverse()
        folds.reverse()
    elif defect == "numeric_format":
        for row in predictions:
            row["volume_id"] = f'{float(row["volume_id"]):.1f}'
            row["held_out_run"] = f'{float(row["held_out_run"]):.1f}'
        for row in folds:
            row["held_out_run"] = f'{float(row["held_out_run"]):.1f}'
            row["n_test_samples"] = "72.0"
            row["accuracy"] = f'{float(row["accuracy"]):.6f}'
        result["cv_accuracy"] = round(result["cv_accuracy"], 4)
    elif defect == "free_prose":
        (tmp_path / "findings.md").write_text("逐次留出一个采集 run 的结果见输出表；仅分析一名被试。\n")
    elif defect == "missing":
        predictions.pop()
    elif defect == "duplicate":
        predictions.append(predictions[0])
    elif defect == "source_run":
        predictions[0]["held_out_run"] = str((int(predictions[0]["held_out_run"]) + 1) % 12)
    elif defect == "source_class":
        predictions[0]["true_label"] = other_category(predictions[0]["true_label"])
    elif defect == "score_preserving_wrong_category":
        row = next(row for row in predictions if row["predicted_label"] != row["true_label"])
        row["predicted_label"] = other_category(row["true_label"], row["predicted_label"])
        # Correct/incorrect status, all fold scores and headline are unchanged.
    elif defect == "all_perfect":
        for row in predictions:
            row["predicted_label"] = row["true_label"]
        for row in folds:
            row["accuracy"] = "1.0"
        result["cv_accuracy"] = 1.0
    elif defect == "constant_fabricated":
        for run in range(12):
            selected = [row for row in predictions if int(row["held_out_run"]) == run]
            for index, row in enumerate(selected):
                row["predicted_label"] = row["true_label"] if index < 52 else other_category(row["true_label"])
        for row in folds:
            row["accuracy"] = str(52 / 72)
        result["cv_accuracy"] = 52 / 72
    elif defect == "nan_fold":
        folds[0]["accuracy"] = "nan"
    elif defect == "nan_headline":
        result["cv_accuracy"] = float("nan")
    elif defect == "headline":
        result["cv_accuracy"] = 0.0 if result["cv_accuracy"] else 1.0
    elif defect == "voxel_count":
        result["n_voxels"] += 1
        metadata["n_voxels"] += 1
    elif defect == "chance":
        result["chance"] = 0.5
    elif defect == "global_metadata":
        metadata["preprocessing"]["cleaning_unit"] = "all_acquisitions"
    elif defect == "source_hash":
        metadata["source_sha256"]["subj1/bold.nii.gz"] = "0" * 64

    write_csv(tmp_path / "predictions.csv", predictions)
    write_csv(tmp_path / "per_fold.csv", folds)
    (tmp_path / "decoding_results.json").write_text(json.dumps(result))
    (tmp_path / "run_metadata.json").write_text(json.dumps(metadata))
    if defect == "missing_metadata":
        (tmp_path / "run_metadata.json").unlink()
    elif defect == "empty":
        for name in FILES:
            (tmp_path / name).unlink()

    checked = verify(tmp_path)
    expected = 0 if defect in ("none", "row_order", "numeric_format", "free_prose") else 1
    assert checked.returncode == expected, checked.stdout + checked.stderr
    if defect == "score_preserving_wrong_category":
        assert "source-indexed predictions differ" in checked.stdout


def test_actual_global_cleaning_output_is_rejected(oracle, tmp_path):
    source = os.environ.get("REPAIR_GLOBAL_OUTPUT")
    if not source:
        pytest.skip("requires retained real-data global-cleaning control")
    copy_outputs(oracle, tmp_path)
    for name in ("predictions.csv", "per_fold.csv", "decoding_results.json"):
        shutil.copy2(Path(source) / name, tmp_path / name)
    checked = verify(tmp_path)
    assert checked.returncode == 1, checked.stdout + checked.stderr
    assert "source-indexed predictions differ" in checked.stdout
