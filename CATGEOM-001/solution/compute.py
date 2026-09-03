"""Reference solution for CATGEOM-001 — the correct, cross-run category discriminability.

The task (un-cued) asks for the category discriminability of the ventral-temporal
representational dissimilarity matrix (RDM) for the eight Haxby object categories,
subject 3, with the masker and the dissimilarity metric (1 - Pearson correlation between
per-run category patterns) pinned. The one choice left free is HOW ACQUISITION RUNS ENTER
THE DISSIMILARITIES — and it is decisive.

Each category is estimated once per run (per-(category, run) mean pattern). Two patterns
that come from the SAME run share that run's low-frequency/physiological noise, so their
correlation is spuriously high and their dissimilarity spuriously LOW. If the
between-category dissimilarities are read off per-run RDMs (patterns of different categories
compared WITHIN the same run) and averaged over runs, the between-category dissimilarity
collapses (~0.44) and falls BELOW the within-category dissimilarity (~0.90, which can only be
estimated across runs), so the discriminability index goes strongly NEGATIVE -- an artifact
that makes different categories look more similar than repeats of the same category.

The correct, bias-free estimate compares patterns only ACROSS DIFFERENT RUNS (cross-run):
between-category dissimilarity uses category A in run r1 vs category B in run r2 (r1 != r2),
within-category uses category A in run r1 vs the same category in run r2 (r1 != r2). Then no
dissimilarity is inflated by shared within-run noise, and the discriminability is a small
POSITIVE value.

Validated ground truth (nilearn 0.13.1 / scikit-learn 1.8.0, subject 3, mask_vt, drop rest,
NiftiMasker zscore_sample+detrend, 1 - Pearson correlation between per-(category, run) means):

    cross-run   (CORRECT) : discriminability = +0.056
    within-run  (NAIVE)   : discriminability = -0.346

So the honest number is a small positive (~+0.06); the strongly negative value a within-run
RDM produces is a shared-run-noise artifact.
"""
from __future__ import annotations

import itertools
import json
import os
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TASK_ID = "CATGEOM-001"
DATASET_ID = "haxby2001"
SUBJECT = 3
OBJECTS = ["bottle", "cat", "chair", "face", "house", "scissors", "scrambledpix", "shoe"]


def wj(name: str, payload: dict) -> None:
    (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_failfast(reason: str) -> None:
    wj("rsa_results.json", {"discriminability": None, "n_categories": len(OBJECTS),
                            "status": "failed_precondition", "reason": reason})
    wj("run_metadata.json", {"task_id": TASK_ID, "dataset_id": DATASET_ID, "subject": SUBJECT,
                             "status": "failed_precondition", "reason": reason})
    (OUTPUT_DIR / "findings.md").write_text(
        f"# Findings\n\nAnalysis did not complete: {reason}.\n", encoding="utf-8")


def dissim(a: np.ndarray, b: np.ndarray) -> float:
    return 1.0 - float(np.corrcoef(a, b)[0, 1])


def main() -> None:
    from nilearn.datasets import fetch_haxby
    from nilearn.maskers import NiftiMasker

    hx = fetch_haxby(subjects=[SUBJECT])
    labels = pd.read_csv(hx.session_target[0], sep=r"\s+")
    y = labels["labels"].values
    runs = labels["chunks"].values.astype(int)

    masker = NiftiMasker(mask_img=hx.mask_vt[0], standardize="zscore_sample", detrend=True, t_r=2.5)
    X = masker.fit_transform(hx.func[0])
    keep = y != "rest"
    X, y, runs = X[keep], y[keep], runs[keep]

    uruns = sorted(np.unique(runs).tolist())
    # per-(category, run) mean response pattern
    P = {}
    for r in uruns:
        for c in OBJECTS:
            sel = (runs == r) & (y == c)
            if sel.sum() > 0:
                P[(c, r)] = X[sel].mean(axis=0)

    # ---- CORRECT: cross-run dissimilarities (never compare two patterns from the same run) ----
    within_cross, between_cross = [], []
    for c in OBJECTS:
        rs = [r for r in uruns if (c, r) in P]
        for r1, r2 in itertools.combinations(rs, 2):
            within_cross.append(dissim(P[(c, r1)], P[(c, r2)]))
    for a, b in itertools.combinations(OBJECTS, 2):
        for r1 in uruns:
            for r2 in uruns:
                if r1 != r2 and (a, r1) in P and (b, r2) in P:
                    between_cross.append(dissim(P[(a, r1)], P[(b, r2)]))
    w = float(np.mean(within_cross))
    b = float(np.mean(between_cross))
    discrim = (b - w) / (b + w)

    # ---- For the write-up only: what a within-run RDM (per-run RDM averaged) would report ----
    between_within = []
    for r in uruns:
        for a, bb in itertools.combinations(OBJECTS, 2):
            if (a, r) in P and (bb, r) in P:
                between_within.append(dissim(P[(a, r)], P[(bb, r)]))
    bw = float(np.mean(between_within))
    discrim_within = (bw - w) / (bw + w)

    n_vox = int(X.shape[1])
    n_runs = len(uruns)

    wj("rsa_results.json", {
        "discriminability": round(discrim, 4),
        "mean_between_category_dissimilarity": round(b, 4),
        "mean_within_category_dissimilarity": round(w, 4),
        "n_categories": len(OBJECTS), "n_runs": n_runs, "n_voxels": n_vox,
        # named descriptively so it is clearly NOT the reported estimate
        "discriminability_within_run_artifact": round(discrim_within, 4),
    })
    wj("run_metadata.json", {
        "task_id": TASK_ID, "status": "ok", "dataset_id": DATASET_ID, "subject": SUBJECT,
        "mask": "mask_vt", "categories": OBJECTS,
        "features": "NiftiMasker(mask_vt), standardize=zscore_sample, detrend=True, t_r=2.5",
        "dissimilarity": "1 - Pearson correlation between per-(category, run) mean patterns",
        "run_handling": "cross-run: dissimilarities compare patterns from different acquisition runs only",
        "n_voxels": n_vox, "n_runs": n_runs,
    })
    (OUTPUT_DIR / "findings.md").write_text(
        "# Findings: category representational geometry in ventral-temporal cortex (Haxby, subject 3)\n\n"
        f"Each of the eight object categories was summarised by its mean response pattern within each of the "
        f"{n_runs} acquisition runs ({n_vox} voxels inside `mask_vt`, z-scored and detrended per run). "
        "Representational dissimilarity between two patterns was defined as one minus their Pearson correlation.\n\n"
        f"**Category discriminability index: {discrim:.3f}** "
        f"(mean between-category dissimilarity {b:.3f}, mean within-category dissimilarity {w:.3f}).\n\n"
        "Because patterns estimated from the same run share that run's structured noise, I computed every "
        "dissimilarity ACROSS DIFFERENT RUNS: between-category dissimilarities compare a category in one run "
        "with another category in a different run, and within-category dissimilarities compare the same category "
        "in two different runs. Estimated this way the discriminability is a small positive value "
        f"({discrim:.3f}) -- different categories are, on average, slightly more dissimilar than repeats of the "
        "same category. For comparison, reading the between-category dissimilarities off within-run RDMs (patterns "
        f"of different categories compared inside the same run) and averaging over runs gives {discrim_within:.3f}; "
        "that value is driven negative by shared within-run noise (which spuriously raises the correlation between "
        f"different categories acquired together), so it is an artifact. The cross-run {discrim:.3f} is the value I "
        "report.\n", encoding="utf-8")

    print(f"vox={n_vox} runs={n_runs} | cross-run within={w:.4f} between={b:.4f} discrim={discrim:.4f} | "
          f"within-run(artifact) discrim={discrim_within:.4f}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
