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

    ts, y, groups = [], [], []
    for t, e, s in zip(ts_all, eye, site):
        if isinstance(t, np.ndarray) and t.ndim == 2 and t.shape[1] == 200 and t.shape[0] > 50 and e in (1, 2):
            ts.append(t); y.append(1 if e == 1 else 0); groups.append(s)  # 1 = eyes open
    y = np.asarray(y); groups = np.asarray(groups)

    conn = ConnectivityMeasure(kind="correlation", vectorize=True, discard_diagonal=True)
    X = conn.fit_transform(ts)

    def clf():
        return make_pipeline(StandardScaler(), LinearSVC(C=1.0, dual="auto", max_iter=3000))

    def cv_bacc(splits):
        accs = []
        for tr, te in splits:
            c = clf().fit(X[tr], y[tr])
            accs.append(balanced_accuracy_score(y[te], c.predict(X[te])))
        return float(np.mean(accs))

    # CORRECT: leave-one-site-out (blocked by acquisition site -> no site-fingerprint leakage)
    loso_bacc = cv_bacc(list(LeaveOneGroupOut().split(X, y, groups)))

    # For the write-up only: what the naive random-fold scheme would have reported.
    rand_bacc = cv_bacc(list(StratifiedKFold(10, shuffle=True, random_state=0).split(X, y)))

    n_sub, n_feat = int(X.shape[0]), int(X.shape[1])
    n_sites = int(len(np.unique(groups)))

    wj("eye_decoding_results.json", {
        "cv_balanced_accuracy": round(loso_bacc, 4),
        "n_subjects": n_sub, "n_features": n_feat, "n_sites": n_sites,
        "n_eyes_open": int(y.sum()), "n_eyes_closed": int((y == 0).sum()),
        "chance": round(CHANCE, 4),
        # named descriptively so it is clearly NOT the reported estimate
        "random_kfold_balanced_accuracy_leaky": round(rand_bacc, 4),
    })
    wj("run_metadata.json", {
        "task_id": TASK_ID, "status": "ok", "dataset_id": DATASET_ID,
        "atlas": "rois_cc200", "connectivity": "Pearson correlation (vectorized)",
        "classifier": "StandardScaler + LinearSVC(C=1.0)",
        "cross_validation": "leave-one-site-out over acquisition sites (SITE_ID)",
        "metric": "balanced accuracy", "target": "EYE_STATUS_AT_SCAN (open=1 vs closed=2)",
        "n_subjects": n_sub, "n_features": n_feat, "n_sites": n_sites,
    })
    (OUTPUT_DIR / "findings.md").write_text(
        "# Findings: decoding eyes-open vs eyes-closed from ABIDE resting-state connectivity\n\n"
        f"A linear SVM was trained on vectorised CC200 correlation connectivity ({n_feat} edges) from "
        f"{n_sub} ABIDE participants across {n_sites} acquisition sites to classify whether each participant "
        "was scanned with eyes open or eyes closed.\n\n"
        f"**Cross-validated balanced accuracy: {loso_bacc:.3f}** (chance = {CHANCE:.3f}).\n\n"
        "Because each site used a single eyes-open/closed protocol, eye status is almost perfectly aligned "
        "with the acquisition site, and connectivity carries a strong site-specific fingerprint. I therefore "
        "evaluated the classifier with **leave-one-site-out** cross-validation, so the model is always tested "
        "on sites absent from its training set and cannot exploit a site fingerprint. Evaluated this way the "
        f"balanced accuracy is {loso_bacc:.3f}. For comparison, a random 10-fold split that mixes each site "
        f"across train and test reports {rand_bacc:.3f}; that estimate is inflated because the classifier can "
        "identify a held-out subject's site (and therefore its eye-status protocol) from connectivity, so it "
        f"overstates the genuine, transferable eyes-open/closed effect. The site-blocked {loso_bacc:.3f} is the "
        "accuracy I report.\n", encoding="utf-8")

    print(f"n={n_sub} feat={n_feat} sites={n_sites} | LOSO bAcc={loso_bacc:.4f} | random-kfold(leaky)={rand_bacc:.4f}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
