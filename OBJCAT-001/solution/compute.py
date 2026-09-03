"""Reference solution for OBJCAT-001 — the correct, leakage-free reproduction.

The task (un-cued) asks for the leave-one-run-out cross-validated 8-way decoding accuracy
of a linear SVM on the eight Haxby object categories, subject 2, after reducing the
whole-brain mask to the 500 most category-selective voxels (highest ANOVA F). The subject,
mask, sample selection, masker, number of selected voxels, classifier and cross-validation
scheme are all pinned. The one choice left free is WHERE the 500-voxel feature selection is
performed relative to the cross-validation split -- and it is decisive.

If the 500 voxels are chosen once on the WHOLE dataset (using every volume, including the
held-out run's volumes) and the SVM is then cross-validated on those voxels, the selection
has already "seen" the test folds: the reported accuracy is inflated (circular / double
dipping, Kriegeskorte et al. 2009). The correct estimate re-runs the ANOVA voxel selection
INSIDE each cross-validation fold, on the training runs only, so the held-out run never
influences which voxels are used.

Validated ground truth (nilearn 0.13.1 / scikit-learn 1.8.0, subject 2, whole-brain mask,
drop rest, NiftiMasker per-run zscore_sample + detrend, SelectKBest(f_classif, k=500),
SVC linear C=1, leave-one-run-out):

    selection INSIDE each fold (CORRECT, nested) : cv_accuracy = 0.656
    selection on ALL data      (CIRCULAR)        : cv_accuracy = 0.757   (chance = 0.125)

So the honest number is ~0.66; the ~0.76 a select-once pipeline reports is a circularity
artifact. (The choice is invariant to the SVM C over 0.5-5.0.)
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

TASK_ID = "OBJCAT-001"
DATASET_ID = "haxby2001"
SUBJECT = 2
K = 500
CHANCE = 1.0 / 8.0
OBJECTS = ["bottle", "cat", "chair", "face", "house", "scissors", "scrambledpix", "shoe"]


def wj(name: str, payload: dict) -> None:
    (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_failfast(reason: str) -> None:
    wj("decoding_results.json", {"cv_accuracy": None, "n_samples": 0, "n_voxels": 0,
                                 "n_selected": K, "n_categories": 8, "n_runs": 0,
                                 "chance": CHANCE, "status": "failed_precondition", "reason": reason})
    wj("run_metadata.json", {"task_id": TASK_ID, "dataset_id": DATASET_ID, "subject": SUBJECT,
                             "status": "failed_precondition", "reason": reason})
    (OUTPUT_DIR / "findings.md").write_text(
        f"# Findings\n\nAnalysis did not complete: {reason}.\n", encoding="utf-8")


def main() -> None:
    from nilearn.datasets import fetch_haxby
    from nilearn.maskers import NiftiMasker
    from sklearn.svm import SVC
    from sklearn.feature_selection import SelectKBest, f_classif
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import LeaveOneGroupOut, cross_val_score

    hx = fetch_haxby(subjects=[SUBJECT])
    labels = pd.read_csv(hx.session_target[0], sep=r"\s+")
    y = labels["labels"].values
    runs = labels["chunks"].values

    keep = y != "rest"
    masker = NiftiMasker(mask_img=hx.mask, standardize="zscore_sample", detrend=True, runs=runs)
    X = masker.fit_transform(hx.func[0])                 # per-run standardized whole-brain voxels
    X, y, runs = X[keep], y[keep], runs[keep]

    n_samples, n_voxels = int(X.shape[0]), int(X.shape[1])
    n_runs = int(len(np.unique(runs)))
    logo = LeaveOneGroupOut()

    # CORRECT: ANOVA voxel selection is re-fit INSIDE each training fold (nested)
    pipe = Pipeline([("sel", SelectKBest(f_classif, k=K)),
                     ("svc", SVC(kernel="linear", C=1.0))])
    nested_scores = cross_val_score(pipe, X, y, cv=logo, groups=runs)
    cv_accuracy = float(nested_scores.mean())

    # For the write-up only: what a select-once (circular) pipeline would have reported.
    X_sel = SelectKBest(f_classif, k=K).fit(X, y).transform(X)
    circ_scores = cross_val_score(SVC(kernel="linear", C=1.0), X_sel, y, cv=logo, groups=runs)
    circular_accuracy = float(circ_scores.mean())

    wj("decoding_results.json", {
        "cv_accuracy": round(cv_accuracy, 4),
        "n_samples": n_samples, "n_voxels": n_voxels, "n_selected": K,
        "n_categories": 8, "n_runs": n_runs, "chance": round(CHANCE, 4),
        "cv_accuracy_per_run": [round(float(s), 4) for s in nested_scores],
        # named descriptively so it is clearly NOT the reported estimate
        "select_once_accuracy_circular": round(circular_accuracy, 4),
    })
    wj("run_metadata.json", {
        "task_id": TASK_ID, "status": "ok", "dataset_id": DATASET_ID, "subject": SUBJECT,
        "mask": "whole-brain mask", "categories": OBJECTS,
        "features": "NiftiMasker(mask), standardize=zscore_sample, detrend=True, runs=chunks",
        "feature_reduction": "500 voxels by highest ANOVA F (f_classif), refit within each CV fold",
        "classifier": "SVC(kernel=linear, C=1.0)",
        "cross_validation": "leave-one-run-out over acquisition runs (chunks)",
        "n_samples": n_samples, "n_voxels": n_voxels, "n_selected": K, "n_runs": n_runs,
    })
    (OUTPUT_DIR / "findings.md").write_text(
        "# Findings: object-category decoding across occipitotemporal cortex (Haxby, subject 2)\n\n"
        f"A linear SVM (C=1) was trained on the 500 most category-selective voxels (highest ANOVA F), "
        f"drawn from the {n_voxels}-voxel whole-brain mask of per-run z-scored, detrended activity, to "
        f"classify the eight object categories from {n_samples} volumes across {n_runs} acquisition runs.\n\n"
        f"**Cross-validated 8-way decoding accuracy: {cv_accuracy:.3f}** (chance = {CHANCE:.3f}).\n\n"
        "The 500-voxel selection is category-driven, so it must be estimated without seeing the test data. "
        "I therefore re-ran the ANOVA voxel selection **inside each leave-one-run-out fold, on the training "
        f"runs only**, so the held-out run never influenced which voxels were used. Evaluated this way the "
        f"accuracy is {cv_accuracy:.3f}. For comparison, selecting the 500 voxels once on the whole dataset "
        f"and then cross-validating reports {circular_accuracy:.3f}; that estimate is inflated because the "
        "feature selection has already seen the held-out folds (circular analysis / double dipping), so it "
        f"overstates true out-of-sample decoding. The nested {cv_accuracy:.3f} is the accuracy I report.\n",
        encoding="utf-8")

    print(f"n={n_samples} vox={n_voxels} runs={n_runs} | nested cv_accuracy={cv_accuracy:.4f} | "
          f"select-once(circular)={circular_accuracy:.4f}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
