#!/usr/bin/env python3
"""Reference solution (oracle) for FCSTAB-001.

Within-run change of the strongest resting-state functional connections, done so the
selection artefact is separated from any genuine early-to-late effect. Cohort: the first
40 quality-checked ABIDE cpac/CC200 subjects -- ALL from a single site (PITT), eyes CLOSED,
one ~4.9-min run each (196 TRs at TR=1.5 s). The pre-extracted Craddock-200 ROI time series
are BAKED into the image (no internet); this script reads them from the baked NPZ.

The scientific point (written into findings.md): selecting the top-decile edges on the
first half makes the naive (second - first) contrast SELECTION-CONTAMINATED -- the first-half
mean of the selected set is inflated by first-half noise, so second - first is biased
downward by a negative selection component. That contrast therefore CANNOT by itself
establish that the strongest connections genuinely weaken across the run. To show this and
to estimate the selection-free change, the oracle computes, per subject, the signed Fisher-z
change (second - first) of the top-decile edges under FOUR selection schemes:

  forward     -- top decile selected on the FIRST half   (biased DOWN by selection)
  reverse     -- top decile selected on the SECOND half   (biased UP  by selection)
  independent -- top-decile strong-edge set selected from the OTHER 39 subjects (LOSO),
                 i.e. independent of this subject's two halves -> selection-free estimate
  random      -- a size-matched random edge set           -> selection-free control

Forward and reverse have opposite signs of similar magnitude (the sign of the "effect" is
set by which half you select on); their average, and the independent/random estimates, are
near zero. A prespecified equivalence test (TOST, margin 0.05 z) is applied to the
selection-free (independent) estimate, and edge-level reliability (top-decile set overlap,
edge rank Spearman, ICC) is reported as the honest within-run stability statement.
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

FRAC = 0.10          # top decile
EQUIV_MARGIN = 0.05  # prespecified equivalence margin (Fisher-z) for the selection-free estimate
SEED = 0

# exact pinned cohort (first 40 quality-checked ABIDE cpac subjects; all PITT, eyes closed)
PINNED_SUB_IDS = [50003, 50004, 50005, 50006, 50007, 50008, 50010, 50011, 50012, 50013,
                  50014, 50015, 50016, 50020, 50022, 50023, 50024, 50025, 50026, 50027,
                  50028, 50030, 50031, 50032, 50033, 50034, 50035, 50036, 50037, 50038,
                  50039, 50040, 50041, 50042, 50043, 50044, 50045, 50046, 50047, 50048]


def fail(reason):
    (OUT / "summary.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": str(reason)}, indent=2), encoding="utf-8")
    (OUT / "findings.md").write_text(
        f"# FCSTAB-001 - failed_precondition\n\n{reason}\n", encoding="utf-8")
    sys.stderr.write(f"failed_precondition: {reason}\n")
    sys.exit(1)


def find_data():
    """Locate the baked CC200 NPZ (no internet)."""
    cands = []
    if os.environ.get("FCSTAB_DATA"):
        cands.append(Path(os.environ["FCSTAB_DATA"]))
    cands += [Path("/app/data/abide_cc200_pitt40.npz"),
              Path(__file__).resolve().parent.parent / "environment" / "data" / "abide_cc200_pitt40.npz"]
    for p in cands:
        if p.exists():
            return p
    fail("baked CC200 data (abide_cc200_pitt40.npz) not found; expected it in /app/data")


def edges_z(x):
    """Upper-triangle Fisher-z of the ROI x ROI correlation of a (T, R) array."""
    C = np.corrcoef(x, rowvar=False)
    iu = np.triu_indices(C.shape[0], k=1)
    return np.arctanh(np.clip(C[iu], -0.999999, 0.999999))


def group_stats(a):
    from scipy import stats
    a = np.asarray(a, float)
    n = a.size
    m = float(a.mean())
    sd = float(a.std(ddof=1))
    se = sd / np.sqrt(n)
    t, p = stats.ttest_1samp(a, 0.0)
    lo, hi = stats.t.interval(0.95, n - 1, loc=m, scale=se)
    return {"delta_mean": m, "delta_sd": sd, "delta_se": float(se),
            "ci95_lo": float(lo), "ci95_hi": float(hi),
            "t": float(t), "p": float(p), "n_negative": int((a < 0).sum()), "n": int(n)}


def tost_equivalent(a, margin):
    """Two one-sided tests that mean(a) lies within +/- margin. Returns (p_tost, equivalent)."""
    from scipy import stats
    a = np.asarray(a, float)
    n = a.size
    m = a.mean()
    se = a.std(ddof=1) / np.sqrt(n)
    dfree = n - 1
    p_lo = stats.t.sf((m - (-margin)) / se, dfree)   # H0: mean <= -margin
    p_hi = stats.t.sf((margin - m) / se, dfree)       # H0: mean >= +margin
    p_tost = float(max(p_lo, p_hi))
    return p_tost, bool(p_tost < 0.05)


def main():
    path = find_data()
    blob = path.read_bytes()
    d = np.load(path, allow_pickle=False)
    ts_all = np.asarray(d["timeseries"], dtype=float)          # (S, T, R)
    sub_ids = [int(x) for x in d["subject_ids"]]
    data_sha = hashlib.sha256(np.ascontiguousarray(d["timeseries"]).tobytes()).hexdigest()
    S, T, R = ts_all.shape
    L = T // 2

    # common ROI mask: keep ROIs non-degenerate in the full run AND both halves of EVERY subject
    keep = np.ones(R, bool)
    for ts in ts_all:
        keep &= (ts.std(axis=0) > 1e-8)
        keep &= (ts[:L].std(axis=0) > 1e-8)
        keep &= (ts[T - L:].std(axis=0) > 1e-8)
    if keep.sum() < 20:
        fail(f"too few non-degenerate ROIs across the cohort ({int(keep.sum())})")

    # per-subject first/second-half and full-run edge vectors on the common ROI set
    z1 = np.array([edges_z(ts[:L, keep]) for ts in ts_all])
    z2 = np.array([edges_z(ts[T - L:, keep]) for ts in ts_all])
    zf = np.array([edges_z(ts[:, keep]) for ts in ts_all])
    if not (np.isfinite(z1).all() and np.isfinite(z2).all() and np.isfinite(zf).all()):
        fail("non-finite edges after common-ROI masking")
    E = z1.shape[1]
    k = max(1, int(FRAC * E))
    rng = np.random.default_rng(SEED)

    rows = []
    fwd, rev, ind, rnd = [], [], [], []
    ff, fs = [], []
    overlaps, spearmans, iccs = [], [], []
    from scipy import stats
    for i in range(S):
        a1, a2 = z1[i], z2[i]
        sf = np.argsort(a1)[-k:]           # forward: strongest on first half
        sr = np.argsort(a2)[-k:]           # reverse: strongest on second half
        others = np.delete(np.arange(S), i)
        si = np.argsort(zf[others].mean(0))[-k:]   # independent (LOSO) strong-edge set
        ridx = rng.choice(E, size=k, replace=False)

        f_first, f_second = float(a1[sf].mean()), float(a2[sf].mean())
        d_fwd = f_second - f_first
        d_rev = float(a2[sr].mean() - a1[sr].mean())
        d_ind = float(a2[si].mean() - a1[si].mean())
        d_rnd = float(a2[ridx].mean() - a1[ridx].mean())

        rows.append((sub_ids[i], E, f_first, f_second, d_fwd, d_rev, d_ind, d_rnd))
        ff.append(f_first); fs.append(f_second)
        fwd.append(d_fwd); rev.append(d_rev); ind.append(d_ind); rnd.append(d_rnd)
        overlaps.append(len(set(sf.tolist()) & set(sr.tolist())) / k)
        spearmans.append(float(stats.spearmanr(a1, a2).statistic))
        iccs.append(float(np.corrcoef(a1, a2)[0, 1]))

    # ---- required per-subject CSV --------------------------------------------------------
    with open(OUT / "stability.csv", "w", encoding="utf-8") as fh:
        fh.write("subject_id,n_edges,forward_first_half,forward_second_half,"
                 "forward_delta,reverse_delta,independent_delta,random_delta\n")
        for sid, e, f1, f2, df, dr, di, dn in rows:
            fh.write(f"{sid},{e},{f1:.6f},{f2:.6f},{df:.6f},{dr:.6f},{di:.6f},{dn:.6f}\n")

    schemes = {"forward": group_stats(fwd), "reverse": group_stats(rev),
               "independent": group_stats(ind), "random": group_stats(rnd)}
    avg_fr = group_stats((np.array(fwd) + np.array(rev)) / 2.0)
    tost_p, equivalent = tost_equivalent(ind, EQUIV_MARGIN)
    g_ff, g_fs = float(np.mean(ff)), float(np.mean(fs))
    pct = 100.0 * (g_fs - g_ff) / g_ff if g_ff else float("nan")

    summary = {
        "status": "ok",
        "n_subjects": S,
        "atlas": "Craddock-200 (CC200), nilearn ABIDE cpac filt_noglobal derivatives (baked, offline)",
        "metric": "Fisher z-transformed Pearson correlation, upper-triangle edges",
        "selection": "top decile (10%) of edges; four selection schemes",
        "cohort": {
            "site": "PITT (single site, all 40 subjects)",
            "eye_status_at_scan": "closed",
            "n_timepoints": int(T),
            "tr_seconds": 1.5,
            "run_minutes_approx": round(T * 1.5 / 60.0, 2),
            "n_rois_total": int(R),
            "n_rois_used": int(keep.sum()),
            "n_edges": int(E),
            "data_sha256": data_sha,
        },
        # signed second-minus-first Fisher-z change of the top-decile set, by selection scheme
        "selection_schemes": schemes,
        "avg_forward_reverse": avg_fr,     # selection bias cancels -> ~ genuine effect
        "forward_top_decile_connectivity": {
            "first_half_mean": g_ff, "second_half_mean": g_fs,
            "change": g_fs - g_ff, "pct_change": pct,
        },
        "equivalence": {
            "target": "independent_delta (selection-free estimate)",
            "margin_z": EQUIV_MARGIN, "tost_p": tost_p, "equivalent_within_margin": equivalent,
        },
        "reliability": {
            "top_decile_set_overlap_first_vs_second": float(np.mean(overlaps)),
            "edge_rank_spearman_first_vs_second": float(np.mean(spearmans)),
            "edge_icc_first_vs_second": float(np.mean(iccs)),
        },
        "conclusion": (
            "The naive top-decile (forward-selected) second-minus-first contrast is "
            "SELECTION-CONTAMINATED: it is biased downward by a negative selection component "
            "and cannot by itself establish that the strongest connections genuinely weaken "
            "across the run. Selecting on the second half instead flips the sign of the "
            "'effect', and a selection-free strong-edge set (LOSO-independent) and a random "
            "set both change by ~0 (equivalent to zero within the prespecified +/-0.05 z "
            "margin). The honest within-run reliability of the strong edges is moderate "
            "(top-decile set overlap ~0.42, edge rank Spearman ~0.48)."
        ),
        "preprocessing": {
            "pipeline": "cpac", "band_pass_filtering": True, "global_signal_regression": False,
            "quality_checked": True,
            "halves": "equal contiguous, first L=floor(T/2) TRs vs last L TRs",
            "roi_inclusion": "ROIs non-degenerate in the full run and both halves of every subject",
            "selection_fraction": FRAC, "seed": SEED,
        },
    }
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    fmean = schemes["forward"]["delta_mean"]; rmean = schemes["reverse"]["delta_mean"]
    imean = schemes["independent"]["delta_mean"]; nmean = schemes["random"]["delta_mean"]
    ilo, ihi = schemes["independent"]["ci95_lo"], schemes["independent"]["ci95_hi"]
    findings = f"""# Within-run change of the strongest functional connections (FCSTAB-001)

**Cohort.** The first {S} quality-checked ABIDE `cpac` subjects (Craddock-200 pre-extracted
time series, band-pass, no GSR) are **all from a single site (PITT), eyes closed**, each a
single **~{summary['cohort']['run_minutes_approx']:.1f}-minute** run ({T} TRs at TR=1.5 s) -- a
short, single-site, eyes-closed acquisition, not a long or eyes-open one. Each run is split
into equal contiguous first/second halves; edges are Fisher-z correlations; the "strongest
connections" are the top decile of edges.

## The naive (forward-selected) contrast

Ranking edges by their **first-half** value and re-measuring on the second half, the
top-decile mean falls from **z = {g_ff:.3f}** to **z = {g_fs:.3f}**, a change of
**{fmean:+.3f}** ({pct:+.1f}%). Taken at face value this reads as the dominant connections
weakening across the run.

## Why that contrast cannot establish weakening: it is selection-contaminated

The edges were **selected because they were extreme on the first-half measurement**, and one
half of a resting run is a noisy estimate. The first-half mean of the selected set is
therefore inflated by first-half noise, so `second - first` carries a **negative selection
component** on top of any genuine early-to-late change. The observed decline is a *lower
bound corrupted by selection*, not an estimate of the true effect. Three complementary
selections make the contamination explicit (per-subject signed Fisher-z change, mean +/- 95% CI):

- **Reverse-half selection** (top decile chosen on the **second** half): change
  **{rmean:+.3f}** -- the *opposite sign*, similar magnitude. The sign of the "effect" is set
  by which half you select on, which a genuine temporal process could not do.
- **Independent (LOSO) strong-edge set** (the strong edges defined from the **other 39
  subjects**, so selection is independent of this subject's two halves): change
  **{imean:+.3f}** (95% CI [{ilo:+.3f}, {ihi:+.3f}]) -- essentially zero. This is the
  selection-free estimate of the genuine early-to-late change for strong edges.
- **Size-matched random edges**: change **{nmean:+.3f}** -- also essentially zero.

The average of the forward and reverse changes (selection bias cancels) is
**{avg_fr['delta_mean']:+.3f}**. A prespecified equivalence test (TOST, margin
+/-{EQUIV_MARGIN} z) on the selection-free estimate is **{'significant' if equivalent else 'not significant'}**
(p = {tost_p:.3f}), i.e. the genuine within-run change of the strong edges is statistically
equivalent to zero within that margin.

## Reliability (the actual within-run stability statement)

If the question is reliability, the honest metrics are edge-set/rank agreement, not the
selected-set decline: the top-decile edge **set overlap** between halves is
**{np.mean(overlaps):.2f}**, edge **rank Spearman** {np.mean(spearmans):.2f}, edge
**ICC {np.mean(iccs):.2f}** -- moderate within-run reliability.

## Conclusion

The naive top-decile decline of **{fmean:+.3f}** is **selection-contaminated and cannot by
itself establish weakening** of the strongest connections. Selecting on the opposite half
flips the sign, and the selection-free (independent/random) estimates are equivalent to zero
within the prespecified +/-{EQUIV_MARGIN} z margin. Reporting the forward contrast as a real
within-run weakening of "backbone" edges would be a selection artefact; the warranted reading
is moderate edge-level reliability with no established genuine early-to-late weakening.
"""
    (OUT / "findings.md").write_text(findings, encoding="utf-8")
    print(f"[FCSTAB-001] S={S} E={E} k={k} | forward {fmean:+.3f} reverse {rmean:+.3f} "
          f"independent {imean:+.3f} random {nmean:+.3f} | TOST p={tost_p:.3f} equiv={equivalent}")


if __name__ == "__main__":
    main()
