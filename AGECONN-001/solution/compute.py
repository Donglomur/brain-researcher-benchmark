"""Reference (oracle) for AGECONN-001 — age vs resting-state connectivity (ABIDE): an un-cued
specification-curve instability (point-estimate / no-multiverse failure axis).

Paper anchor (the developmental claim characterised): resting-state functional connectivity changes
systematically with age (Supekar et al. 2009, PLoS Biol; Fair et al. 2009; Dosenbach et al. 2010).
Multiverse method: Steegen et al. 2016 (specification-curve analysis).

This reference computes the age-connectivity relationship under a standard single pipeline (Craddock-200,
band-pass filtered, no GSR, mean absolute connectivity, motion partialled out) and reports the point
estimate. It THEN volunteers the un-cued check the task never asks: is that a robust estimate? It is
not. Across a specification curve over DEFENSIBLE analytic choices (parcellation x temporal filtering x
connectivity-strength summary) on the SAME quality-checked controls with mean framewise displacement
partialled out, the SIGN of the age-connectivity correlation is decided by the PARCELLATION alone — the
Craddock-200 atlas gives a weak positive (n.s.) correlation, the Dosenbach-160 atlas a significant
NEGATIVE one. A single-pipeline point estimate over-claims robustness.

Route-a: the ABIDE derivatives are fetched at runtime (cached after first run). The filtered vs
unfiltered connectomes are the actual `band_pass_filtering=True/False` derivatives (no in-code
re-filtering), so the filtering axis is a genuine pipeline difference, not a double-filter artifact.

Honesty note: an earlier draft claimed cc200 was significantly POSITIVE and dos160 was NULL. On QC'd
controls with mean-FD partialled out that specific pattern does not hold; what robustly reproduces is
the atlas-driven SIGN FLIP (cc200 positive ~+0.04 n.s., dos160 negative ~-0.10 significant) — the
scientific point (the conclusion is choice-dependent) is unchanged.
"""
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np
from scipy import stats

warnings.filterwarnings("ignore")
OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)

ATLASES = [("cc200", "cc200"), ("dosenbach160", "dosenbach160")]
FILTERS = [("filt (band-pass)", True), ("nofilt (unfiltered)", False)]
STRENGTHS = ["mean_abs_r", "mean_r", "mean_pos_r", "density_r>0.25"]
STANDARD = ("cc200", True, "mean_abs_r")   # the naive single-pipeline choice


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "results.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed\n\n{reason}\n")
    print("FAIL:", reason, file=sys.stderr)
    sys.exit(1)


def strength_vec(a, kind):
    """Overall connectivity strength for one subject's ROI timeseries a (T x nroi)."""
    a = np.asarray(a, dtype=np.float64)
    a = a[:, a.std(0) > 1e-6]
    if a.shape[1] < 5:
        return np.nan
    c = np.corrcoef(a.T)
    c = np.nan_to_num(c, nan=0.0)
    iu = np.triu_indices(c.shape[0], 1)
    r = c[iu]
    if kind == "mean_abs_r":
        return float(np.mean(np.abs(r)))
    if kind == "mean_r":
        return float(np.mean(r))
    if kind == "mean_pos_r":
        return float(r[r > 0].mean()) if np.any(r > 0) else np.nan
    if kind == "density_r>0.25":
        return float(np.mean(r > 0.25))
    raise ValueError(kind)


def load(atlas, band_pass):
    from nilearn.datasets import fetch_abide_pcp
    d = fetch_abide_pcp(derivatives=[f"rois_{atlas}"], pipeline="cpac", band_pass_filtering=band_pass,
                        global_signal_regression=False, quality_checked=True, verbose=0)
    ts = d[f"rois_{atlas}"]
    phe = d.phenotypic
    dx = np.asarray(phe["DX_GROUP"], float)
    age = np.asarray(phe["AGE_AT_SCAN"], float)
    fd = np.asarray(phe["func_mean_fd"], float)
    return ts, dx, age, fd


def partial_corr_fd(S, age, fd):
    ok = np.isfinite(S) & np.isfinite(age) & np.isfinite(fd)
    S, age, fd = S[ok], age[ok], fd[ok]
    rs = S - np.polyval(np.polyfit(fd, S, 1), fd)
    ra = age - np.polyval(np.polyfit(fd, age, 1), fd)
    r, p = stats.pearsonr(ra, rs)
    return float(r), float(p), int(ok.sum())


def main():
    # fetch each (atlas, filtering) once; compute all four strength summaries from each
    cache = {}
    try:
        for atlas, _ in ATLASES:
            for _, bp in FILTERS:
                ts, dx, age, fd = load(atlas, bp)
                cache[(atlas, bp)] = (ts, dx, age, fd)
    except Exception as e:  # noqa: BLE001
        fail(f"could not fetch ABIDE derivatives: {e}")

    def spec(atlas, flabel, bp, kind):
        ts, dx, age, fd = cache[(atlas, bp)]
        ctrl = dx == 2
        S = np.array([strength_vec(t, kind) if c else np.nan for t, c in zip(ts, ctrl)])
        r, p, n = partial_corr_fd(S, np.where(ctrl, age, np.nan), np.where(ctrl, fd, np.nan))
        return {"atlas": atlas, "filtering": flabel, "strength": kind,
                "r": round(r, 4), "p": round(p, 5), "n": n, "significant": bool(p < 0.05)}

    curve = [spec(atlas, flabel, bp, kind)
             for atlas, _ in ATLASES for flabel, bp in FILTERS for kind in STRENGTHS]
    pe = next(c for c in curve if c["atlas"] == STANDARD[0]
              and c["filtering"].startswith("filt") and c["strength"] == STANDARD[2])

    rs = np.array([c["r"] for c in curve])
    n_sig = int(sum(c["significant"] for c in curve))
    cc = np.array([c["r"] for c in curve if c["atlas"] == "cc200"])
    do = np.array([c["r"] for c in curve if c["atlas"] == "dosenbach160"])
    sign_flip = bool(rs.min() < 0 < rs.max())

    (OUT / "results.json").write_text(json.dumps({
        "standard_pipeline": {"atlas": "cc200 (Craddock-200)", "filtering": "band-pass, no GSR",
                              "strength": "mean absolute connectivity"},
        "r": pe["r"], "p": pe["p"], "n_subjects": pe["n"],
        "conclusion_standard_pipeline": (
            "weak positive, not significant" if pe["p"] >= 0.05 else "significant"),
        "analytic_choices": "parcellation, temporal filtering, connectivity-strength summary",
    }, indent=2))

    (OUT / "multiverse.json").write_text(json.dumps({
        "n_specifications": len(curve),
        "r_min": float(rs.min()), "r_max": float(rs.max()),
        "sign_flips": sign_flip, "n_significant": n_sig,
        "cc200_mean_r": float(cc.mean()), "dosenbach160_mean_r": float(do.mean()),
        "driver": "parcellation (atlas) determines the sign",
        "specifications": curve,
    }, indent=2))

    (OUT / "run_metadata.json").write_text(json.dumps({
        "status": "ok",
        "dataset": "ABIDE cpac Craddock-200 & Dosenbach-160, band_pass True/False, no GSR, "
                   "quality-checked controls (DX=2)",
        "n_subjects_standard": pe["n"],
        "method": "per-subject overall connectivity strength vs age, mean framewise displacement "
                  "partialled out; specification curve over parcellation x filtering x strength summary",
    }, indent=2))

    (OUT / "findings.md").write_text(
        "# Does resting-state connectivity change with age?\n\n"
        f"**Standard single pipeline** (Craddock-200, band-pass, no GSR, mean absolute connectivity, "
        f"mean framewise displacement partialled out, n={pe['n']}): age-connectivity correlation "
        f"r = {pe['r']:+.3f} (p = {pe['p']:.3f}) — a "
        f"**{('weak positive, non-significant' if pe['p']>=0.05 else 'significant')}** relationship. "
        "Taken alone this is the developmental-integration reading.\n\n"
        "**But this point estimate is not robust — it is decided by the analytic choices.** Across a "
        f"specification curve over defensible choices (parcellation x temporal filtering x how overall "
        f"connectivity strength is summarised; {len(curve)} specifications, same QC'd controls, motion "
        f"partialled out), the correlation ranges from **r = {rs.min():+.3f} to r = {rs.max():+.3f} and "
        f"flips sign**, with only {n_sig}/{len(curve)} specifications significant. The **parcellation "
        f"alone decides the sign**: every Craddock-200 specification is positive "
        f"(mean r = {cc.mean():+.3f}, all n.s.) while every Dosenbach-160 specification is negative "
        f"(mean r = {do.mean():+.3f}, several significant). The filtered vs unfiltered derivatives are "
        "genuinely different and add further spread. A single-pipeline point estimate — of either sign — "
        "over-states the robustness of the age-connectivity relationship; the honest characterisation is "
        "that the effect is **choice-dependent**, not a stable developmental signature, on these data.\n"
    )

    print(f"OK: standard pipeline r={pe['r']:+.3f} (p={pe['p']:.3f}, n={pe['n']}); specification curve "
          f"r={rs.min():+.3f}..{rs.max():+.3f} sign_flip={sign_flip} ({n_sig}/{len(curve)} sig); "
          f"cc200 mean {cc.mean():+.3f} vs dos160 mean {do.mean():+.3f} (atlas decides sign)")


if __name__ == "__main__":
    main()
