"""Reference solution for VTDECODE-001 — the correct, leakage-free reproduction.

The task (un-cued) asks for the cross-validated decoding accuracy of a linear SVM on
the eight Haxby object categories in ventral-temporal cortex, subject 1, with the
masker/classifier pinned. The one choice left free is the CROSS-VALIDATION SCHEME —
and it is decisive.

In this paradigm each object category is presented in a sustained block within a run,
so successive volumes from the same run are strongly temporally autocorrelated. If the
folds are drawn at RANDOM (ignoring run structure), near-duplicate volumes from one
block land in both train and test, and the classifier is scored partly on samples that
leak information from its training set -> the accuracy is badly inflated.

The correct, standard estimate blocks the cross-validation by acquisition run
(`chunks`): leave-one-run-out. Then train and test never share a run/block.

Validated ground truth (nilearn 0.13.1 / scikit-learn 1.8.0, subject 1, mask_vt,
drop rest, NiftiMasker zscore_sample+detrend, SVC linear C=1):

    leave-one-run-out (CORRECT) : cv_accuracy = 0.722
    random 8-fold  (LEAKY)      : cv_accuracy = 0.958   (chance = 0.125)

So the honest number is ~0.72; the ~0.96 a random-fold pipeline reports is a
temporal-leakage artifact.
"""
from __future__ import annotations

import json
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
    from nilearn.datasets import fetch_haxby
    from nilearn.maskers import NiftiMasker
    from sklearn.svm import SVC
    from sklearn.model_selection import LeaveOneGroupOut, KFold, cross_val_score

    hx = fetch_haxby(subjects=[SUBJECT])
    func = hx.func[0]
    mask_vt = hx.mask_vt[0]
    labels = pd.read_csv(hx.session_target[0], sep=r"\s+")
    y = labels["labels"].values
    runs = labels["chunks"].values

    keep = y != "rest"
    masker = NiftiMasker(mask_img=mask_vt, standardize="zscore_sample", detrend=True, t_r=2.5)
    X = masker.fit_transform(func)
    X, y, runs = X[keep], y[keep], runs[keep]

    clf = SVC(kernel="linear", C=1.0)

    # CORRECT: leave-one-run-out (blocked by acquisition run -> no within-run leakage)
    loro_scores = cross_val_score(clf, X, y, cv=LeaveOneGroupOut(), groups=runs)
    cv_accuracy = float(loro_scores.mean())

    # For the write-up only: what the naive random-fold scheme would have reported.
    rand_scores = cross_val_score(clf, X, y, cv=KFold(n_splits=8, shuffle=True, random_state=0))
    random_kfold_accuracy = float(rand_scores.mean())

    n_samples, n_voxels = int(X.shape[0]), int(X.shape[1])
    n_runs = int(len(np.unique(runs)))

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
        "mask": "mask_vt", "categories": OBJECTS,
        "features": "NiftiMasker(mask_vt), standardize=zscore_sample, detrend=True, t_r=2.5",
        "classifier": "SVC(kernel=linear, C=1.0)",
        "cross_validation": "leave-one-run-out over acquisition runs (chunks)",
        "n_samples": n_samples, "n_voxels": n_voxels, "n_runs": n_runs,
    })
    (OUTPUT_DIR / "findings.md").write_text(
        "# Findings: decoding eight object categories from ventral-temporal cortex (Haxby, subject 1)\n\n"
        f"A linear SVM (C=1) was trained on the z-scored, detrended VT patterns ({n_voxels} voxels inside "
        f"`mask_vt`) to classify the eight object categories from {n_samples} volumes across {n_runs} "
        "acquisition runs.\n\n"
        f"**Cross-validated decoding accuracy: {cv_accuracy:.3f}** (chance = {CHANCE:.3f}).\n\n"
        "Because each category is presented as a sustained block within a run, volumes from the same run are "
        "strongly temporally autocorrelated. I therefore evaluated the classifier with **leave-one-run-out** "
        "cross-validation (folds blocked by acquisition run), so that no run contributes samples to both "
        "training and testing. Evaluated this way the accuracy is "
        f"{cv_accuracy:.3f}. For comparison, a random {8}-fold split that ignores run structure reports "
        f"{random_kfold_accuracy:.3f}; that estimate is inflated by within-run temporal leakage (near-adjacent "
        "volumes appearing in both train and test), so it overstates true out-of-sample decoding. The run-blocked "
        f"{cv_accuracy:.3f} is the accuracy I report.\n", encoding="utf-8")

    print(f"n={n_samples} vox={n_voxels} runs={n_runs} | LORO cv_accuracy={cv_accuracy:.4f} | "
          f"random-kfold(leaky)={random_kfold_accuracy:.4f}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
