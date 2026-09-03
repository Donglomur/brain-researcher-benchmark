"""Reference solution for CONNSTAB-001 -- the correct within-run reproducibility of the
resting-state functional connectome.

The task (un-cued) asks how reproducible the functional connectome is between two halves of
a single resting run, with the dataset, atlas, connectivity and nuisance regression pinned.
The one thing left free is HOW the run is split into its two halves -- and it is decisive.

The BOLD signal is strongly autocorrelated in time (neighbouring frames are nearly
identical). If the two halves are formed by INTERLEAVING frames (odd frames vs even frames,
or any random per-frame split), the two subsets sample essentially the same slow
fluctuations, so their connectomes are near-duplicates and the "reproducibility" is
inflated. Splitting the run into two CONTIGUOUS, non-overlapping halves (first half vs second
half) makes the two estimates temporally independent, so the correlation between the two
half-run connectomes reflects genuine within-run reproducibility -- and it is markedly lower.

Validated ground truth (nilearn 0.13.1, fetch_adhd n_subjects=40, MSDL atlas, Pearson
correlation connectivity, Fisher-z edge vectors, mean over subjects):

    contiguous halves (CORRECT)   : reproducibility r = 0.712
    interleaved odd/even (INFLATED): reproducibility r = 0.876

Across all 40 participants the interleaved split gives a higher value than the contiguous
split, so the ~0.88 an interleaved pipeline reports is a temporal-autocorrelation artifact,
not the honest between-halves reproducibility (~0.71).
"""
from __future__ import annotations

import json
import os
import traceback
from pathlib import Path

import numpy as np

OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

TASK_ID = "CONNSTAB-001"
DATASET_ID = "ADHD-200 sample (nilearn fetch_adhd, N=40) / MSDL atlas"


def wj(name: str, payload: dict) -> None:
    (OUTPUT_DIR / name).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def write_failfast(reason: str) -> None:
    wj("reproducibility_results.json", {"connectome_reproducibility": None, "n_subjects": 0,
                                        "status": "failed_precondition", "reason": reason})
    wj("run_metadata.json", {"task_id": TASK_ID, "dataset_id": DATASET_ID,
                             "status": "failed_precondition", "reason": reason})
    (OUTPUT_DIR / "findings.md").write_text(
        f"# Findings\n\nAnalysis did not complete: {reason}.\n", encoding="utf-8")


def _edge_vector(ts: np.ndarray) -> np.ndarray:
    """Fisher-z transformed upper-triangle of the ROI x ROI correlation connectome."""
    c = np.corrcoef(ts.T)
    iu = np.triu_indices_from(c, 1)
    return np.arctanh(np.clip(c[iu], -0.9999, 0.9999))


def main() -> None:
    from nilearn.datasets import fetch_adhd, fetch_atlas_msdl
    from nilearn.maskers import NiftiMapsMasker

    adhd = fetch_adhd(n_subjects=40, verbose=0)
    msdl = fetch_atlas_msdl(verbose=0)
    masker = NiftiMapsMasker(maps_img=msdl.maps, standardize="zscore_sample", verbose=0)

    contig, interleaved = [], []
    for func, conf in zip(adhd.func, adhd.confounds):
        ts = masker.fit_transform(func, confounds=conf)     # time x regions
        T = ts.shape[0]
        h = T // 2
        # CORRECT: two contiguous, temporally-independent halves
        a, b = _edge_vector(ts[:h]), _edge_vector(ts[h:2 * h])
        contig.append(float(np.corrcoef(a, b)[0, 1]))
        # For the write-up only: an interleaved odd/even split of the same frames
        e, o = _edge_vector(ts[0:2 * h:2]), _edge_vector(ts[1:2 * h:2])
        interleaved.append(float(np.corrcoef(e, o)[0, 1]))

    repro = float(np.mean(contig))
    repro_interleaved = float(np.mean(interleaved))
    n_sub = len(contig)

    wj("reproducibility_results.json", {
        "connectome_reproducibility": round(repro, 4),
        "n_subjects": int(n_sub),
        "reproducibility_sd_across_subjects": round(float(np.std(contig)), 4),
        # named so it is unambiguously NOT the reported estimate
        "interleaved_split_reproducibility_inflated": round(repro_interleaved, 4),
    })
    wj("run_metadata.json", {
        "task_id": TASK_ID, "status": "ok", "dataset_id": DATASET_ID,
        "atlas": "MSDL", "connectivity": "Pearson correlation (Fisher-z edge vectors)",
        "split": "two contiguous non-overlapping halves of each run (first half vs second half)",
        "quantity": "correlation between the two half-run connectome edge vectors, mean over subjects",
        "n_subjects": int(n_sub),
    })
    (OUTPUT_DIR / "findings.md").write_text(
        "# Findings: within-run reproducibility of the resting-state functional connectome\n\n"
        f"For each of {n_sub} ADHD-200 participants, the MSDL functional connectome was estimated "
        "separately from the two halves of the resting run and the two half-run connectomes were "
        "correlated (Fisher-z edge vectors).\n\n"
        f"**Within-run reproducibility (correlation between half-run connectomes): {repro:.3f}** "
        f"(mean over participants).\n\n"
        "The two halves were taken as **contiguous, non-overlapping** portions of the run (first "
        "half vs second half) so that the two connectome estimates are temporally independent. "
        "For comparison, splitting the same frames into an interleaved odd/even pair gives "
        f"{repro_interleaved:.3f}; that value is inflated because BOLD frames are strongly "
        "autocorrelated, so odd and even frames sample the same fluctuations and the two "
        f"connectomes are near-duplicates. The contiguous-split {repro:.3f} is the value I report.\n",
        encoding="utf-8")

    print(f"n={n_sub} | contiguous reproducibility={repro:.4f} | interleaved(inflated)={repro_interleaved:.4f}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001
        write_failfast(f"{type(exc).__name__}: {str(exc)[:200]} | {traceback.format_exc()[-300:]}")
        raise
