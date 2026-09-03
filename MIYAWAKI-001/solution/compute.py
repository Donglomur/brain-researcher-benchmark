"""Reference solution for MIYAWAKI-001 — the correct, leakage-free reproduction.

The task (un-cued) asks for the cross-validated mean pixel decoding accuracy of a
linear ridge decoder that reconstructs the 10x10 binary contrast pattern from
early-visual-cortex BOLD (Miyawaki 2008, random-image runs). The masker, hemodynamic
alignment, decoder and metric are all pinned. The one choice left free is the
CROSS-VALIDATION SCHEME — and it is decisive.

Each random contrast pattern is held on screen for several seconds, so a block of
consecutive BOLD volumes shares the SAME 100-pixel label, and neighbouring volumes are
strongly temporally autocorrelated. If the folds are drawn at RANDOM over volumes,
near-duplicate volumes from one stimulus block (identical target, correlated activity)
land in both train and test, and the decoder is scored partly on samples that leak
information from its training set -> the accuracy is inflated.

The correct, leakage-free estimate blocks the cross-validation by acquisition run
(leave-one-run-out); an equivalent leave-one-image-block-out grouping gives the same
answer. Then train and test never share a stimulus block.

Validated ground truth (nilearn 0.13.1 / scikit-learn 1.8.0, 20 random-image runs,
dataset.mask, per-run zscore_sample + detrend, label shifted +2 volumes, drop rest,
Ridge(alpha=1.0) thresholded at 0.5):

    leave-one-run-out (CORRECT) : mean_pixel_accuracy = 0.593
    random 10-fold  (LEAKY)     : mean_pixel_accuracy = 0.639   (chance ~ 0.50)

So the honest number is ~0.59; the ~0.64 a random-fold pipeline reports is a
temporal-leakage artifact.
"""
from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import numpy as np

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TASK_ID = "MIYAWAKI-001"
DATASET_ID = "miyawaki2008"
DELAY = 2          # pair BOLD volume t with the stimulus label at t-2 (hemodynamic lag)
ALPHA = 1.0        # ridge default
CHANCE = 0.5


def wj(name: str, payload: dict) -> None:
    (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_failfast(reason: str) -> None:
    wj("decoding_results.json", {"mean_pixel_accuracy": None, "n_samples": 0, "n_voxels": 0,
                                 "n_pixels": 100, "n_runs": 0, "chance": CHANCE,
                                 "status": "failed_precondition", "reason": reason})
    wj("run_metadata.json", {"task_id": TASK_ID, "dataset_id": DATASET_ID,
                             "status": "failed_precondition", "reason": reason})
    (OUTPUT_DIR / "findings.md").write_text(
        f"# Findings\n\nAnalysis did not complete: {reason}.\n", encoding="utf-8")


def main() -> None:
    from nilearn.datasets import fetch_miyawaki2008
    from nilearn.maskers import NiftiMasker
    from sklearn.linear_model import Ridge
    from sklearn.model_selection import LeaveOneGroupOut, KFold

    ds = fetch_miyawaki2008()
    base = os.path.basename
    rnd_func = sorted(f for f in ds.func if "random" in base(f))
    rnd_lab = sorted(l for l in ds.label if "random" in base(l))
    if not rnd_func or len(rnd_func) != len(rnd_lab):
        raise RuntimeError(f"unexpected random-run layout: {len(rnd_func)} func / {len(rnd_lab)} label")

    Xs, Ys, groups = [], [], []
    for ri, (f, l) in enumerate(zip(rnd_func, rnd_lab)):
        masker = NiftiMasker(mask_img=ds.mask, detrend=True, standardize="zscore_sample")
        X = masker.fit_transform(f)                        # per-run standardized voxels
        y = np.loadtxt(l, dtype=int, delimiter=",")        # (n_vol, 100) in {-1,0,1}
        n = X.shape[0]
        X = X[DELAY:]                                       # hemodynamic alignment: BOLD t <- label t-DELAY
        y = y[: n - DELAY]
        keep = y.min(axis=1) >= 0                           # drop rest volumes (label row all -1)
        X = np.nan_to_num(X[keep].astype(np.float64))
        y = (y[keep] > 0).astype(int)                       # binary {0,1} target pattern
        Xs.append(X)
        Ys.append(y)
        groups.append(np.full(X.shape[0], ri))

    X = np.vstack(Xs)
    Y = np.vstack(Ys)
    g = np.concatenate(groups)
    n_samples, n_voxels = int(X.shape[0]), int(X.shape[1])
    n_runs = int(len(np.unique(g)))

    def mean_pixel_accuracy(splits) -> float:
        accs = []
        for tr, te in splits:
            m = Ridge(alpha=ALPHA).fit(X[tr], Y[tr])
            pred = (m.predict(X[te]) >= 0.5).astype(int)
            accs.append(float((pred == Y[te]).mean()))
        return float(np.mean(accs))

    # CORRECT: leave-one-run-out (blocked by acquisition run -> no within-block leakage)
    correct = mean_pixel_accuracy(LeaveOneGroupOut().split(X, Y, g))
    # For the write-up only: what a naive random-fold scheme would have reported.
    random_kfold = mean_pixel_accuracy(KFold(n_splits=10, shuffle=True, random_state=0).split(X))

    wj("decoding_results.json", {
        "mean_pixel_accuracy": round(correct, 4),
        "n_samples": n_samples, "n_voxels": n_voxels, "n_pixels": 100,
        "n_runs": n_runs, "chance": round(CHANCE, 4),
        # named descriptively so it is clearly NOT the reported estimate
        "random_kfold_accuracy_leaky": round(random_kfold, 4),
    })
    wj("run_metadata.json", {
        "task_id": TASK_ID, "status": "ok", "dataset_id": DATASET_ID,
        "runs": "20 random-image runs (data_random_run*)", "mask": "dataset.mask (early visual cortex)",
        "features": "NiftiMasker(dataset.mask), per-run standardize=zscore_sample, detrend=True",
        "alignment": "label shifted +2 volumes (BOLD t matched to stimulus t-2)",
        "target": "100 binary pixels (0/1); rest volumes dropped",
        "decoder": "Ridge(alpha=1.0) multi-output, threshold 0.5",
        "metric": "mean pixel decoding accuracy over all pixels and held-out samples",
        "cross_validation": "leave-one-run-out over acquisition runs",
        "n_samples": n_samples, "n_voxels": n_voxels, "n_runs": n_runs,
    })
    (OUTPUT_DIR / "findings.md").write_text(
        "# Findings: decoding binary contrast patterns from early visual cortex (Miyawaki 2008)\n\n"
        f"A multi-output ridge decoder (alpha=1.0) was trained on the per-run z-scored, detrended "
        f"early-visual-cortex patterns ({n_voxels} voxels inside `dataset.mask`) to predict the 100-pixel "
        f"binary contrast pattern from {n_samples} stimulus volumes across {n_runs} random-image runs. Each "
        "predicted pixel is the ridge output thresholded at 0.5.\n\n"
        f"**Cross-validated mean pixel decoding accuracy: {correct:.3f}** (chance = {CHANCE:.3f}).\n\n"
        "Because each contrast pattern is held on screen for several seconds, a block of consecutive BOLD "
        "volumes shares the same 100-pixel label and neighbouring volumes are strongly temporally "
        "autocorrelated. I therefore evaluated the decoder with **leave-one-run-out** cross-validation "
        "(folds blocked by acquisition run), so that no stimulus block contributes samples to both training "
        f"and testing. Evaluated this way the accuracy is {correct:.3f}. For comparison, a random 10-fold "
        f"split over volumes reports {random_kfold:.3f}; that estimate is inflated by within-block temporal "
        "leakage (near-duplicate volumes from one stimulus block appearing in both train and test), so it "
        f"overstates true out-of-sample decoding. The run-blocked {correct:.3f} is the accuracy I report.\n",
        encoding="utf-8")

    print(f"n={n_samples} vox={n_voxels} runs={n_runs} | LORO mean_pixel_accuracy={correct:.4f} | "
          f"random-kfold(leaky)={random_kfold:.4f}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
