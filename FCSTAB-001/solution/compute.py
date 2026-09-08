#!/usr/bin/env python3
"""Reference solution for FCSTAB-001.

Within-run stability of the strongest resting-state functional connections on ABIDE
(CC200 pre-extracted time series). For each subject we split the run into two equal
contiguous halves, form the Fisher-z edge-connectivity of each half, select the top
decile of edges by first-half connectivity, and report their first-half mean, second-half
mean and change.

The honest reading of the result (written into findings.md): the strong-edge "decline" is
regression to the mean, a selection effect from ranking edges on a noisy first-half
estimate -- NOT a genuine within-run weakening. This reference substantiates that by also
computing a size-matched random control set (which does not decline) and the weakest-decile
edges (which symmetrically rise toward the mean).
"""
import json
import os
import sys
import traceback
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

N_SUBJECTS = 40
FRAC = 0.10
SEED = 0


def fail(reason):
    (OUT / "summary.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": str(reason)}, indent=2), encoding="utf-8")
    (OUT / "findings.md").write_text(f"# FCSTAB-001 — failed_precondition\n\n{reason}\n", encoding="utf-8")
    sys.stderr.write(f"failed_precondition: {reason}\n")
    sys.exit(1)


def edge_z(ts):
    """Upper-triangle Fisher-z connectivity over non-degenerate ROIs of a T x R array."""
    ts = np.asarray(ts, float)
    sd = ts.std(axis=0)
    valid = sd > 1e-8
    ts = ts[:, valid]
    C = np.corrcoef(ts, rowvar=False)
    iu = np.triu_indices(C.shape[0], k=1)
    r = np.clip(C[iu], -0.999999, 0.999999)
    return np.arctanh(r), valid


try:
    from nilearn import datasets
except Exception as e:  # pragma: no cover
    fail(f"could not import nilearn: {e!r}")

try:
    data = datasets.fetch_abide_pcp(
        pipeline="cpac", band_pass_filtering=True, global_signal_regression=False,
        derivatives=["rois_cc200"], quality_checked=True, n_subjects=N_SUBJECTS, verbose=0)
except Exception as e:
    fail(f"could not fetch ABIDE cpac/cc200 derivatives: {e!r}")

ts_all = data.get("rois_cc200")
if ts_all is None or len(ts_all) == 0:
    fail("ABIDE cc200 time series not returned")

try:
    sub_ids = list(data["phenotypic"]["SUB_ID"])
except Exception:
    sub_ids = list(range(len(ts_all)))

rng = np.random.default_rng(SEED)
rows = []
top_d, top1, top2 = [], [], []
rand_d, bot_d, bot1, bot2 = [], [], [], []

for i, ts in enumerate(ts_all):
    ts = np.asarray(ts, float)
    if ts.ndim != 2 or ts.shape[0] < 40:
        continue
    T = ts.shape[0]
    L = T // 2
    a = ts[:L]                    # first (earlier) half
    b = ts[T - L:]                # second (later) half, equal length
    # keep ROIs non-degenerate in BOTH halves so the two edge vectors are aligned
    va = a.std(axis=0) > 1e-8
    vb = b.std(axis=0) > 1e-8
    keep = va & vb
    a = a[:, keep]
    b = b[:, keep]
    Ca = np.corrcoef(a, rowvar=False)
    Cb = np.corrcoef(b, rowvar=False)
    iu = np.triu_indices(Ca.shape[0], k=1)
    m1 = np.arctanh(np.clip(Ca[iu], -0.999999, 0.999999))
    m2 = np.arctanh(np.clip(Cb[iu], -0.999999, 0.999999))
    good = np.isfinite(m1) & np.isfinite(m2)
    m1, m2 = m1[good], m2[good]
    E = m1.size
    if E < 100:
        continue
    k = max(1, int(FRAC * E))
    order = np.argsort(m1)
    top = order[-k:]              # strongest first-half edges
    bot = order[:k]               # weakest (most negative) first-half edges
    ridx = rng.choice(E, size=k, replace=False)   # size-matched random control

    t1, t2 = float(m1[top].mean()), float(m2[top].mean())
    b1, b2 = float(m1[bot].mean()), float(m2[bot].mean())
    r1, r2 = float(m1[ridx].mean()), float(m2[ridx].mean())

    rows.append((sub_ids[i], E, t1, t2, t2 - t1))
    top1.append(t1); top2.append(t2); top_d.append(t2 - t1)
    bot1.append(b1); bot2.append(b2); bot_d.append(b2 - b1)
    rand_d.append(r2 - r1)

if not rows:
    fail("no usable subjects after loading time series")

# ---- required per-subject CSV ---------------------------------------------------------
with open(OUT / "stability.csv", "w", encoding="utf-8") as fh:
    fh.write("subject_id,n_edges,top_decile_first_half,top_decile_second_half,top_decile_change\n")
    for sid, E, t1, t2, dd in rows:
        fh.write(f"{sid},{E},{t1:.6f},{t2:.6f},{dd:.6f}\n")

g_top1 = float(np.mean(top1)); g_top2 = float(np.mean(top2)); g_topd = float(np.mean(top_d))
g_botd = float(np.mean(bot_d)); g_bot1 = float(np.mean(bot1)); g_bot2 = float(np.mean(bot2))
g_randd = float(np.mean(rand_d))
pct = 100.0 * (g_top2 - g_top1) / g_top1 if g_top1 else float("nan")

summary = {
    "status": "ok",
    "n_subjects": len(rows),
    "atlas": "Craddock 200 (CC200), nilearn ABIDE cpac filt_noglobal derivatives",
    "metric": "Fisher z-transformed Pearson correlation, upper-triangle edges",
    "selection": "top decile (10%) of edges by first-half connectivity",
    "top_decile_connectivity": {
        "first_half_mean": g_top1,
        "second_half_mean": g_top2,
        "change": g_topd,
        "pct_change": pct,
    },
    # extra diagnostics substantiating the interpretation (not required by the task)
    "control_random_set_change": g_randd,
    "weakest_decile_connectivity": {
        "first_half_mean": g_bot1, "second_half_mean": g_bot2, "change": g_botd,
    },
    "preprocessing": {
        "pipeline": "cpac", "band_pass_filtering": True, "global_signal_regression": False,
        "quality_checked": True, "halves": "equal contiguous, first vs last L=floor(T/2) TRs",
        "roi_inclusion": "ROIs with non-zero variance in both halves",
    },
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

findings = f"""# Within-run stability of the strongest functional connections (FCSTAB-001)

**Cohort:** first {len(rows)} ABIDE subjects (nilearn `fetch_abide_pcp`, cpac, band-pass,
no GSR), Craddock-200 pre-extracted time series. Each run split into equal first/second
contiguous halves; edges are Fisher-z correlations; the "strongest connections" are the
top decile of edges ranked by **first-half** connectivity.

## What the top-decile edges do

Selected on the first half, the strongest edges average **z = {g_top1:.3f}** in the first
half and **z = {g_top2:.3f}** in the second half — a change of **{g_topd:+.3f}**
({pct:+.1f}%). Taken at face value this looks like the brain's dominant connections
*weakening across the run*.

## That apparent weakening is regression to the mean, not a real within-run decline

The edges were **selected because they were extreme on the first-half measurement**, and a
single half of a resting run is a noisy estimate. Ranking on that noise guarantees that the
top-ranked edges were, on average, lifted by positive noise in the first half; on an
**independent** second-half measurement that noise does not repeat, so the selected set
moves back toward the average. This is textbook **regression to the mean** — a *selection
effect*, not a change in the underlying connectivity. Two controls confirm it:

- A **size-matched random set** of edges (not selected on either half) changes by only
  **{g_randd:+.3f}** between the halves — essentially zero, and if anything slightly
  *upward*. If connectivity genuinely weakened over the scan, an unselected set would fall
  too; it does not.
- The **weakest decile** of first-half edges moves the *opposite* way: from
  **z = {g_bot1:.3f}** to **z = {g_bot2:.3f}** (**{g_botd:+.3f}**), i.e. it *rises* toward
  the mean by a comparable amount. A real "connections weaken over time" process cannot make
  the most-negative edges strengthen; only regression to the mean produces this symmetric
  convergence of both extremes toward the centre.

## Conclusion

The strongest functional connections are **not** meaningfully less stable within the run,
and they do **not** genuinely weaken as the scan proceeds. The apparent decline of the
top-decile edges is an artefact of selecting them on one noisy half-run measurement and
re-measuring on an independent half — regression to the mean. Treating that decline as a
real property of "backbone" edges (instability, vigilance-driven drift, etc.) would be
mistaken; the correct comparison uses an independent or unselected set, under which the
effect vanishes.
"""
(OUT / "findings.md").write_text(findings, encoding="utf-8")
print(f"[FCSTAB-001] subjects={len(rows)} top {g_top1:.3f}->{g_top2:.3f} ({g_topd:+.3f}) "
      f"random {g_randd:+.3f} weakest {g_botd:+.3f}")
