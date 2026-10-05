"""Declared run-held-out SVM method case on Haxby subject-1 VT patterns.

Clean full runs separately before dropping rest, and report exact source-indexed
OOF predictions. Random-fold evaluation is a separately labeled within-run
sensitivity, not the unseen-run estimand. The old globally cleaned numeric bank
is stale and must not be treated as truth for this revised recipe.
"""
from __future__ import annotations

import json
import hashlib
import os
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TASK_ID = "VTDECODE-001"
DATASET_ID = "haxby2001"
SUBJECT = 1
CHANCE = 1.0 / 8.0
OBJECTS = ["bottle", "cat", "chair", "face", "house", "scissors", "scrambledpix", "shoe"]
PIPELINE_ID = "runwise-clean-loro-v2"


def source_inputs():
    data = Path(os.environ.get("DATA_DIR", "/app/data"))
    manifest = json.loads((data / "data_manifest.json").read_text())
    expected = {"subj1/bold.nii.gz", "subj1/mask4_vt.nii.gz", "subj1/labels.txt"}
    assert {record["path"] for record in manifest["files"]} == expected
    hashes = {}
    for record in manifest["files"]:
        path = data / record["path"]
        assert path.stat().st_size == record["size_bytes"], f"Source size changed: {path.name}"
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        assert digest == record["sha256"], f"Source checksum changed: {path.name}"
        hashes[record["path"]] = digest
    return data, hashes


def wj(name: str, payload: dict) -> None:
    (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_failfast(reason: str) -> None:
    wj("decoding_results.json", {"cv_accuracy": None, "n_samples": 0, "n_voxels": 0,
                                 "n_categories": 8, "chance": CHANCE, "status": "failed_precondition",
                                 "reason": reason})
    wj("run_metadata.json", {"task_id": TASK_ID, "dataset_id": DATASET_ID, "subject": SUBJECT,
                             "status": "failed_precondition", "reason": reason})
    (OUTPUT_DIR / "findings.md").write_text(
        f"# Findings\n\nAnalysis did not complete: {reason}.\n", encoding="utf-8")


def main() -> None:
    from nilearn.maskers import NiftiMasker
    from sklearn.svm import SVC
    from sklearn.base import clone
    from sklearn.model_selection import LeaveOneGroupOut, KFold, cross_val_score

    data, source_sha256 = source_inputs()
    func = data / "subj1/bold.nii.gz"
    mask_vt = data / "subj1/mask4_vt.nii.gz"
    labels = pd.read_csv(data / "subj1/labels.txt", sep=r"\s+")
    y = labels["labels"].values
    runs = labels["chunks"].values

    keep = y != "rest"
    masker = NiftiMasker(mask_img=mask_vt, standardize="zscore_sample", detrend=True, t_r=2.5,
                         runs=runs)
    X = masker.fit_transform(func)
    volume_ids = np.flatnonzero(keep)
    X, y, runs = X[keep], y[keep], runs[keep]

    clf = SVC(kernel="linear", C=1.0, tol=0.001, shrinking=True)

    # Public unseen-run estimand: no acquisition run contributes to both train and test.
    # Iterate the folds by hand so the per-fold held-out accuracy is keyed to the run held out.
    logo = LeaveOneGroupOut()
    per_run = {}
    predictions = []
    for tr, te in logo.split(X, y, groups=runs):
        held = int(np.unique(runs[te])[0])
        m = clone(clf)
        m.fit(X[tr], y[tr])
        predicted = m.predict(X[te])
        per_run[held] = (float(np.mean(predicted == y[te])), int(len(te)))
        predictions.extend(dict(volume_id=int(volume_ids[i]), held_out_run=held,
                                true_label=str(y[i]), predicted_label=str(p)) for i, p in zip(te, predicted))
    held_runs = sorted(per_run)
    loro_scores = np.array([per_run[r][0] for r in held_runs])
    cv_accuracy = float(loro_scores.mean())

    # For the write-up only: what the naive random-fold scheme would have reported.
    rand_scores = cross_val_score(clf, X, y, cv=KFold(n_splits=8, shuffle=True, random_state=0))
    random_kfold_accuracy = float(rand_scores.mean())

    n_samples, n_voxels = int(X.shape[0]), int(X.shape[1])
    n_runs = int(len(np.unique(runs)))

    # required intermediate: one row per cross-validation fold (held-out run + its accuracy),
    # so the single headline accuracy is backed by a validated per-fold breakdown.
    import csv as _csv
    with open(OUTPUT_DIR / "predictions.csv", "w", newline="", encoding="utf-8") as fh:
        w = _csv.DictWriter(fh, fieldnames=["volume_id", "held_out_run", "true_label", "predicted_label"])
        w.writeheader()
        w.writerows(predictions)
    with open(OUTPUT_DIR / "per_fold.csv", "w", newline="", encoding="utf-8") as fh:
        w = _csv.writer(fh)
        w.writerow(["fold", "held_out_run", "n_test_samples", "accuracy"])
        for i, r in enumerate(held_runs, start=1):
            acc, nte = per_run[r]
            w.writerow([i, r, nte, round(acc, 6)])

    wj("decoding_results.json", {
        "cv_accuracy": round(cv_accuracy, 4),
        "n_samples": n_samples, "n_voxels": n_voxels, "n_categories": 8,
        "n_runs": n_runs, "chance": round(CHANCE, 4),
        "cv_accuracy_per_run": [round(float(s), 4) for s in loro_scores],
        # named descriptively so it is clearly NOT the reported estimate
        "random_kfold_accuracy_leaky": round(random_kfold_accuracy, 4),
    })
    wj("run_metadata.json", {
        "task_id": TASK_ID, "status": "ok", "dataset_id": DATASET_ID, "subject": SUBJECT,
        "mask": "mask4_vt", "categories": OBJECTS, "pipeline_id": PIPELINE_ID,
        "preprocessing": {"detrend": True, "standardize": "zscore_sample", "t_r": 2.5,
                          "cleaning_unit": "acquisition_run", "clean_before_rest_removal": True},
        "features": "NiftiMasker(mask_vt), standardize=zscore_sample, detrend=True, t_r=2.5",
        "classifier": {"name": "SVC", "kernel": "linear", "C": 1.0, "tol": 0.001, "shrinking": True},
        "cross_validation": "leave-one-run-out", "source_sha256": source_sha256,
        "n_samples": n_samples, "n_voxels": n_voxels, "n_runs": n_runs,
    })
    (OUTPUT_DIR / "findings.md").write_text(
        "# Findings: decoding eight object categories from ventral-temporal cortex (Haxby, subject 1)\n\n"
        f"A linear SVM (C=1) was trained on the z-scored, detrended VT patterns ({n_voxels} voxels inside "
        f"`mask_vt`) to classify the eight object categories from {n_samples} volumes across {n_runs} "
        "acquisition runs. Each full run was cleaned independently, including its rest volumes; "
        "rest volumes were removed only after cleaning.\n\n"
        f"**Cross-validated decoding accuracy: {cv_accuracy:.3f}** (chance = {CHANCE:.3f}).\n\n"
        "Because each category is presented as a sustained block within a run, volumes from the same run are "
        "strongly temporally autocorrelated. I therefore evaluated the classifier with **leave-one-run-out** "
        "cross-validation (folds blocked by acquisition run), so that no run contributes samples to both "
        "training and testing. Evaluated this way the accuracy is "
        f"{cv_accuracy:.3f}. For comparison, a random {8}-fold split that ignores run structure reports "
        f"{random_kfold_accuracy:.3f}. It allows samples from the same run in training and testing, "
        "and therefore does not estimate unseen-run generalization. The run-blocked "
        f"{cv_accuracy:.3f} is the accuracy I report. This is a modern single-subject method case, "
        "not the original paper's pattern-correlation statistic or population-level evidence. "
        "Accuracy is conditional on the supplied fixed VT mask; independent ROI selection "
        "and an end-to-end ROI-discovery pipeline are not evaluated here.\n", encoding="utf-8")

    print(f"n={n_samples} vox={n_voxels} runs={n_runs} | LORO cv_accuracy={cv_accuracy:.4f} | "
          f"random-kfold(leaky)={random_kfold_accuracy:.4f}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
