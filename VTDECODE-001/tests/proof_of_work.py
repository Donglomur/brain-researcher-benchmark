"""Read the measured reference for the public, pinned Haxby decoding recipe.

Matching retained predictions checks the numerical result; it cannot establish
how a submitted program was executed. No accuracy-strength or prose gate is used.
"""
import csv
import json
import os
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
REF_PATH = Path(os.environ.get("DECODE_REFERENCE", Path(__file__).with_name("reference.npz")))
PIPELINE_ID = "runwise-clean-loro-v2"
FOLD_TOL = 1e-6
HEADLINE_TOL = 0.000051
LABEL_SHA256 = "c805dac945488ad49685a186b77b344e46548beec2af5a57f41a4ae2eac8591e"


def load_reference():
    with np.load(REF_PATH, allow_pickle=False) as data:
        reference = {
            "run_ids": data["ref_run_ids"].astype(int),
            "fold_acc": data["ref_fold_acc"].astype(float),
            "volume_ids": data["ref_volume_ids"].astype(int),
            "prediction_runs": data["ref_prediction_runs"].astype(int),
            "true_labels": data["ref_true_labels"].astype(str),
            "predicted_labels": data["ref_predicted_labels"].astype(str),
            "stats": json.loads(str(data["ref_stats"])),
        }
    stats = reference["stats"]
    assert stats.get("pipeline_id") == PIPELINE_ID, "failed_precondition: stale decoding reference"
    assert stats["source_sha256"]["subj1/labels.txt"] == LABEL_SHA256
    assert stats["n_samples"] == 864 and stats["n_runs"] == 12 and stats["n_categories"] == 8
    assert stats["n_voxels"] > 0 and stats["chance"] == 0.125
    assert reference["run_ids"].shape == (12,)
    assert set(reference["run_ids"]) == set(range(12))
    assert reference["fold_acc"].shape == (12,)
    for key in ("volume_ids", "prediction_runs", "true_labels", "predicted_labels"):
        assert reference[key].shape == (864,), f"invalid reference array: {key}"
    assert len(set(reference["volume_ids"])) == 864
    assert set(reference["prediction_runs"]) == set(range(12))
    correct = reference["predicted_labels"] == reference["true_labels"]
    for run, accuracy in zip(reference["run_ids"], reference["fold_acc"]):
        selected = reference["prediction_runs"] == run
        assert selected.sum() == 72
        assert np.isfinite(accuracy) and abs(accuracy - correct[selected].mean()) <= 1e-12
    assert abs(stats["loro_accuracy"] - reference["fold_acc"].mean()) <= 1e-12
    return reference


def source_labels_path():
    source = Path("/app/data/subj1/labels.txt")
    if source.is_file():
        return source
    # Present in a source checkout for authoring tests, absent from Harbor's
    # mounted /tests directory. Container verification requires the baked data.
    return Path(__file__).resolve().parents[1] / "environment/data/source_labels.txt"


def read_json(name, output=OUT):
    with (output / name).open(encoding="utf-8") as stream:
        value = json.load(stream)
    assert isinstance(value, dict), f"{name} must contain a JSON object"
    return value


def load_per_fold(output=OUT):
    from prediction_contract import integer, finite_number

    with (output / "per_fold.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    folds = {}
    for row in rows:
        run = integer(row["held_out_run"])
        assert run not in folds, "duplicate acquisition fold"
        assert integer(row["n_test_samples"]) == 72
        accuracy = finite_number(row["accuracy"])
        assert 0 <= accuracy <= 1
        folds[run] = accuracy
    assert set(folds) == set(range(12)), "all twelve acquisition folds are required"
    return folds
