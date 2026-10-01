"""Reference solution for EYESTATE-001 — the correct, site-blocked cross-validated accuracy.

The task (un-cued) asks for the cross-validated balanced accuracy of an eyes-open vs
eyes-closed decoder trained on ABIDE resting-state functional connectivity, subject set,
atlas (CC200), connectivity (Pearson correlation), and classifier (linear SVM) pinned.
The one choice left free is the CROSS-VALIDATION SCHEME -- and it is decisive.

In ABIDE each acquisition SITE used a single eyes-open/closed protocol, so eye status is
almost perfectly aligned with the scanning site. Every site also leaves a strong,
site-specific fingerprint on functional connectivity. If the folds are drawn at RANDOM,
subjects from a given site appear in both train and test, and the classifier can read the
held-out subjects' eye status off their site fingerprint -- accuracy is inflated well above
what the eyes-open/closed effect itself supports. Blocking the cross-validation by SITE
(leave-one-site-out) forces the model to generalise to sites it never saw, so it can only
use the genuine, transferable eyes-open/closed connectivity effect.

Validated ground truth (nilearn 0.13.1 / scikit-learn 1.8.0, ABIDE cpac filt_noglobal
rois_cc200, N=1035, correlation connectivity, LinearSVC C=1, balanced accuracy):

    leave-one-site-out (CORRECT) : balanced_accuracy = 0.737
    random 10-fold     (LEAKY)   : balanced_accuracy = 0.867   (chance = 0.5)

So the honest cross-site number is ~0.74; the ~0.87 a random-fold pipeline reports is
inflated by site-fingerprint leakage.
"""
from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import numpy as np

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TASK_ID = "EYESTATE-001"
DATASET_ID = "ABIDE_pcp/cpac/filt_noglobal/rois_cc200"
CHANCE = 0.5


def wj(name: str, payload: dict) -> None:
    (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_failfast(reason: str) -> None:
    wj("eye_decoding_results.json", {"cv_balanced_accuracy": None, "n_subjects": 0,
                                     "chance": CHANCE, "status": "failed_precondition", "reason": reason})
    wj("run_metadata.json", {"task_id": TASK_ID, "dataset_id": DATASET_ID,
                             "status": "failed_precondition", "reason": reason})
    (OUTPUT_DIR / "findings.md").write_text(
        f"# Findings\n\nAnalysis did not complete: {reason}.\n", encoding="utf-8")


def main() -> None:
    from nilearn.datasets import fetch_abide_pcp
    from nilearn.connectome import ConnectivityMeasure
    from sklearn.svm import LinearSVC
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    from sklearn.model_selection import StratifiedKFold, LeaveOneGroupOut
    from sklearn.metrics import balanced_accuracy_score

    ab = fetch_abide_pcp(pipeline="cpac", band_pass_filtering=True, global_signal_regression=False,
                         derivatives=["rois_cc200"], quality_checked=False, verbose=0)
    ts_all = ab["rois_cc200"]
    ph = ab["phenotypic"]
    eye = np.asarray(ph["EYE_STATUS_AT_SCAN"])
    site = np.asarray(ph["SITE_ID"]).astype(str)

    ts, y, groups, subject_ids = [], [], [], []
    for t, e, s, subject in zip(ts_all, eye, site, ph["SUB_ID"]):
        if isinstance(t, np.ndarray) and t.ndim == 2 and t.shape[1] == 200 and t.shape[0] > 50 and e in (1, 2):
            ts.append(t); y.append(1 if e == 1 else 0); groups.append(s)  # 1 = eyes open
            subject_ids.append(str(subject))
    y = np.asarray(y); groups = np.asarray(groups)

    conn = ConnectivityMeasure(kind="correlation", vectorize=True, discard_diagonal=True)
    X = conn.fit_transform(ts)

    def clf():
        return make_pipeline(StandardScaler(), LinearSVC(C=1.0, dual="auto", max_iter=3000))

    def cv_bacc(splits):
        predictions = np.zeros(len(y), int)
        fold_ids = np.zeros(len(y), int)
        for fold, (tr, te) in enumerate(splits):
            c = clf().fit(X[tr], y[tr])
            predictions[te] = c.predict(X[te])
            fold_ids[te] = fold
        return float(balanced_accuracy_score(y, predictions)), predictions, fold_ids

    # CORRECT: leave-one-site-out (blocked by acquisition site -> no site-fingerprint leakage).
    # Capture the per-fold (per-held-out-site) balanced accuracy: the required intermediate table.
    per_fold = []
    loso_predictions = np.zeros(len(y), int)
    site_only_predictions = np.zeros(len(y), int)
    for tr, te in LeaveOneGroupOut().split(X, y, groups):
        site = str(groups[te][0])
        c = clf().fit(X[tr], y[tr])
        loso_predictions[te] = c.predict(X[te])
        site_only_predictions[te] = int(y[tr].mean() >= .5)  # Unseen site: training-majority fallback.
        ba = float(balanced_accuracy_score(y[te], loso_predictions[te]))
        per_fold.append({"fold_site": site, "n_test": int(len(te)),
                         "n_eyes_open_test": int((y[te] == 1).sum()),
                         "n_eyes_closed_test": int((y[te] == 0).sum()),
                         "balanced_accuracy": ba})
    loso_bacc = float(balanced_accuracy_score(y, loso_predictions))
    legacy_mean_fold_bacc = float(np.mean([f["balanced_accuracy"] for f in per_fold]))

    # NAIVE (leaky) random-fold scheme: what mixing each site across train/test would report.
    rand_bacc, random_predictions, random_folds = cv_bacc(list(StratifiedKFold(10, shuffle=True, random_state=0).split(X, y)))

    n_sub, n_feat = int(X.shape[0]), int(X.shape[1])
    n_sites = int(len(np.unique(groups)))

    # ---- required intermediate output: per-fold balanced accuracy (one row per CV fold) ----
    import csv as _csv
    with open(OUTPUT_DIR / "oof_predictions.csv", "w", newline="", encoding="utf-8") as f:
        writer = _csv.writer(f)
        writer.writerow(["subject_id", "site", "label", "fold_site", "prediction", "site_only_prediction", "random_fold", "random_prediction"])
        for i in range(n_sub):
            writer.writerow([subject_ids[i], groups[i], int(y[i]), groups[i], int(loso_predictions[i]), int(site_only_predictions[i]), int(random_folds[i]), int(random_predictions[i])])
    with open(OUTPUT_DIR / "per_fold.csv", "w", newline="", encoding="utf-8") as _f:
        w = _csv.writer(_f)
        w.writerow(["fold_site", "n_test", "n_eyes_open_test", "n_eyes_closed_test",
                    "balanced_accuracy"])
        for f in sorted(per_fold, key=lambda d: d["fold_site"]):
            w.writerow([f["fold_site"], f["n_test"], f["n_eyes_open_test"],
                        f["n_eyes_closed_test"], f"{f['balanced_accuracy']:.6f}"])

    wj("eye_decoding_results.json", {
        "cv_balanced_accuracy": round(loso_bacc, 4),
        "site_blocked_balanced_accuracy": round(loso_bacc, 4),
        "random_kfold_balanced_accuracy": round(rand_bacc, 4),
        "n_subjects": n_sub, "n_features": n_feat, "n_sites": n_sites,
        "n_eyes_open": int(y.sum()), "n_eyes_closed": int((y == 0).sum()),
        "chance": round(CHANCE, 4),
        "legacy_equal_site_mean_recall": legacy_mean_fold_bacc,
        "site_only_unseen_site_baseline": float(balanced_accuracy_score(y, site_only_predictions)),
        "always_open_pooled_balanced_accuracy": float(balanced_accuracy_score(y, np.ones(len(y), int))),
        "always_closed_pooled_balanced_accuracy": float(balanced_accuracy_score(y, np.zeros(len(y), int))),
        "single_class_sites": sum(f["n_eyes_open_test"] == 0 or f["n_eyes_closed_test"] == 0 for f in per_fold),
        # descriptive alias kept for back-compat (clearly NOT the reported estimate)
        "random_kfold_balanced_accuracy_leaky": round(rand_bacc, 4),
    })
    wj("run_metadata.json", {
        "task_id": TASK_ID, "status": "ok", "dataset_id": DATASET_ID,
        "atlas": "rois_cc200", "connectivity": "Pearson correlation (vectorized)",
        "classifier": "StandardScaler + LinearSVC(C=1.0)",
        "cross_validation": "leave-one-site-out over acquisition sites (SITE_ID)",
        "metric": "pooled out-of-fold balanced accuracy", "target": "EYE_STATUS_AT_SCAN (open=1 vs closed=2)",
        "scientific_target": "confounded protocol prediction on unseen sites, not biological eye-state effect",
        "permutation_status": "not performed; no null or eye-state attribution claim",
        "n_subjects": n_sub, "n_features": n_feat, "n_sites": n_sites,
    })
    (OUTPUT_DIR / "findings.md").write_text(
        f"# Confounded protocol prediction on unseen ABIDE sites\n\n"
        f"Pooled LOSO balanced accuracy is {loso_bacc:.3f}; pooled random-10-fold BA is "
        f"{rand_bacc:.3f}. The legacy equal-site mean recall is {legacy_mean_fold_bacc:.3f}, "
        "a different estimand with one-class folds. Always-open and always-closed pooled "
        "BA are both 0.5. Site-only prediction on an unseen site falls back to the training "
        "majority; its score is included in the results.\n\n"
        "Eye protocol and acquisition site are strongly associated. LOSO tests prediction "
        "on unseen sites but cannot identify a biological eye-state effect: site-related "
        "acquisition differences may align with protocol across sites. These are descriptive "
        "method sensitivities, not a causal transferable-eye claim. No label-permutation "
        "or clustered uncertainty analysis was performed, so no null inference is made.\n",
        encoding="utf-8")
    print(f"n={n_sub} feat={n_feat} sites={n_sites} | LOSO bAcc={loso_bacc:.4f} | random-kfold(leaky)={rand_bacc:.4f}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
