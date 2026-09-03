"""Reference solution for MOVIESYNC-001 -- the correct inter-subject correlation
(ISC) of the movie-evoked BOLD response in visual cortex.

The task (un-cued) asks for the inter-subject correlation of the movie response in visual
cortex, with the dataset, atlas, region set, nuisance regression and band-pass all pinned.
The one thing left free is HOW the "inter-subject correlation" is computed -- and it is
decisive.

Inter-subject correlation can be estimated two ways that give materially different numbers:

  * PAIRWISE ISC (CORRECT): the average Pearson correlation between the time courses of every
    PAIR of participants. This is literally "the correlation between participants" and is the
    convention-invariant measure of between-subject similarity.

  * LEAVE-ONE-OUT ISC (INFLATED): correlate each participant's time course with the MEAN of
    all the OTHER participants, then average. Averaging N-1 subjects suppresses idiosyncratic
    noise and builds a high-SNR template, so each subject correlates much more strongly with
    that average than with any single other subject. LOO-ISC is therefore systematically
    higher than the pairwise value (here about 2.4x) and is NOT comparable to it
    (Nastase et al. 2019, SCAN).

Validated ground truth (nilearn 0.13.1, fetch_development_fmri n_subjects=40, MSDL atlas,
confound-cleaned, band-pass 0.01-0.1 Hz, mean over the three visual-cortex regions
["Vis","Striate","Occ post"]):

    pairwise ISC (CORRECT) : 0.152
    leave-one-out ISC      : 0.365   (chance ~ 0.0)

So the honest between-subject synchrony in visual cortex is ~0.15; the ~0.37 a
leave-one-out pipeline reports is the high-SNR-template artifact, not the correlation
between two participants.
"""
from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import numpy as np

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TASK_ID = "MOVIESYNC-001"
DATASET_ID = "development_fmri (ds000228, Richardson et al. 2018)"
N_SUBJECTS = 40
VISUAL_REGIONS = ["Vis", "Striate", "Occ post"]
CHANCE = 0.0


def wj(name: str, payload: dict) -> None:
    (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_failfast(reason: str) -> None:
    wj("isc_results.json", {"visual_isc": None, "n_subjects": 0, "chance": CHANCE,
                            "status": "failed_precondition", "reason": reason})
    wj("run_metadata.json", {"task_id": TASK_ID, "dataset_id": DATASET_ID,
                             "status": "failed_precondition", "reason": reason})
    (OUTPUT_DIR / "findings.md").write_text(
        f"# Findings\n\nAnalysis did not complete: {reason}.\n", encoding="utf-8")


def _zscore_rows(x: np.ndarray) -> np.ndarray:
    return (x - x.mean(1, keepdims=True)) / (x.std(1, keepdims=True) + 1e-9)


def main() -> None:
    from nilearn.datasets import fetch_development_fmri, fetch_atlas_msdl
    from nilearn.maskers import NiftiMapsMasker

    dev = fetch_development_fmri(n_subjects=N_SUBJECTS, verbose=0)
    msdl = fetch_atlas_msdl(verbose=0)
    labels = list(msdl.labels)

    masker = NiftiMapsMasker(maps_img=msdl.maps, standardize="zscore_sample",
                             low_pass=0.1, high_pass=0.01, t_r=2.0, verbose=0)
    ts = [masker.fit_transform(f, confounds=c) for f, c in zip(dev.func, dev.confounds)]

    T = min(t.shape[0] for t in ts)
    M = np.stack([t[:T] for t in ts], axis=0)          # subjects x time x regions
    n_sub = M.shape[0]
    vis_idx = [labels.index(name) for name in VISUAL_REGIONS]

    pairwise_per_region = []
    loo_per_region = []
    for r in vis_idx:
        x = _zscore_rows(M[:, :, r])                   # subjects x time (z-scored per subject)
        # PAIRWISE: mean off-diagonal correlation between subjects (CORRECT)
        C = np.corrcoef(x)
        iu = np.triu_indices(n_sub, 1)
        pairwise_per_region.append(float(C[iu].mean()))
        # LEAVE-ONE-OUT: each subject vs mean of the others (recorded for the write-up only)
        loo = [np.corrcoef(x[i], np.delete(x, i, axis=0).mean(0))[0, 1] for i in range(n_sub)]
        loo_per_region.append(float(np.mean(loo)))

    isc_pairwise = float(np.mean(pairwise_per_region))
    isc_loo = float(np.mean(loo_per_region))

    wj("isc_results.json", {
        "visual_isc": round(isc_pairwise, 4),
        "isc_per_region": {name: round(v, 4) for name, v in zip(VISUAL_REGIONS, pairwise_per_region)},
        "n_subjects": int(n_sub),
        "n_timepoints": int(T),
        "chance": CHANCE,
        # named so it is unambiguously NOT the reported estimate
        "leave_one_out_isc_inflated": round(isc_loo, 4),
    })
    wj("run_metadata.json", {
        "task_id": TASK_ID, "status": "ok", "dataset_id": DATASET_ID,
        "atlas": "MSDL", "regions": VISUAL_REGIONS,
        "preprocessing": "NiftiMapsMasker, confound-cleaned, band-pass 0.01-0.1 Hz, zscore_sample",
        "isc_estimator": "pairwise (mean Pearson correlation between every pair of participants)",
        "n_subjects": int(n_sub), "n_timepoints": int(T),
    })
    (OUTPUT_DIR / "findings.md").write_text(
        "# Findings: inter-subject correlation of the movie response in visual cortex\n\n"
        f"Using {n_sub} participants of the development_fmri cohort (Pixar *Partly Cloudy* movie), "
        "MSDL visual-cortex time series were confound-cleaned and band-passed (0.01-0.1 Hz).\n\n"
        f"**Inter-subject correlation (visual cortex): {isc_pairwise:.3f}** (chance ~ 0).\n\n"
        "This is the *pairwise* ISC: the mean Pearson correlation between the movie time courses of "
        "every pair of participants, i.e. the correlation between two participants. For reference, "
        f"correlating each participant with the mean of all the others (leave-one-out) gives "
        f"{isc_loo:.3f}; that value is inflated because averaging N-1 participants builds a high-SNR "
        "template that suppresses idiosyncratic noise, so it overstates the genuine between-subject "
        f"similarity. The pairwise {isc_pairwise:.3f} is the value I report.\n", encoding="utf-8")

    print(f"n={n_sub} T={T} | pairwise ISC={isc_pairwise:.4f} | leave-one-out ISC={isc_loo:.4f}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
