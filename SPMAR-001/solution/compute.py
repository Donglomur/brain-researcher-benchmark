"""Reference (oracle) for SPMAR-001 — temporal autocorrelation inflates first-level fMRI GLM
significance (the SPM/FSL prewhitening problem).

Paper anchor: Friston et al. 2000, NeuroImage (10.1006/nimg.2000.0630, "To smooth or not to smooth"
/ serial correlations in fMRI); Woolrich et al. 2001, NeuroImage (10.1006/nimg.2001.0931, temporal
autocorrelation and prewhitening in FMRIB/FSL). fMRI BOLD time series are strongly temporally
autocorrelated (AR(1) ~ 0.4 even unfiltered). Ordinary least squares GLM assumes independent
residuals, so it underestimates the regression-slope variance and INFLATES the t-statistic — giving
far more "significant" activations than the nominal false-positive rate. Prewhitening (fitting and
removing an AR model) restores calibration.

The task (un-cued) asks the analyst to fit a standard per-ROI OLS GLM of the ABIDE resting-state
time series on a synthetic block-design regressor and report how many regions are "significant" at
p<0.05 and how much they trust the count. Because the data are resting-state and the regressor is
arbitrary, the TRUE number of associated regions is ~0, so a calibrated test should flag ~5%. This
reference VOLUNTEERS the check the task never asks: the OLS false-positive rate is ~20% (~4x nominal)
— the fingerprint of unmodeled temporal autocorrelation — and AR(1) prewhitening restores it to ~8%.
"""
import json
import os
import sys
import glob
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)


def fail(reason):
    (OUT / "glm.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn.datasets import fetch_abide_pcp
    from scipy.stats import gamma
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

# Populate the nilearn cache (may partially fail on a flaky mirror), then read whatever cc200 time
# series are present directly — robust to individual missing files. Unfiltered (nofilt) time series
# so the autocorrelation is the intrinsic hemodynamic AR, not a band-pass artifact.
try:
    fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                    band_pass_filtering=False, global_signal_regression=False, quality_checked=False)
except Exception:
    pass
base = os.path.expanduser("~/nilearn_data/ABIDE_pcp")
ddir = os.path.join(base, "cpac", "nofilt_noglobal")
files = sorted(glob.glob(os.path.join(ddir, "*_rois_cc200.1D")))[:120]
if len(files) < 40:
    fail(f"only {len(files)} usable ABIDE cc200 time-series files (need the cache)")


def hrf(tr=2.0, n=32):
    t = np.arange(0, n * tr, tr)
    h = gamma.pdf(t, 6) - 0.35 * gamma.pdf(t, 16)
    return h / np.abs(h).sum()


def boxcar_regressor(T, rng, tr=2.0):
    """A synthetic block design (~20 s blocks), HRF-convolved — NOT linked to any real task."""
    x = np.zeros(T); state = 0; i = 0
    while i < T:
        blk = int(rng.integers(8, 14))
        if state:
            x[i:i + blk] = 1
        i += blk; state ^= 1
    xc = np.convolve(x, hrf(tr), mode="full")[:T]
    return xc - xc.mean()


def ar1_prewhiten(y, x):
    b = np.polyfit(x, y, 1); r = y - (b[0] * x + b[1])
    rho = float(np.clip(np.corrcoef(r[:-1], r[1:])[0, 1], -0.99, 0.99))
    return y[1:] - rho * y[:-1], x[1:] - rho * x[:-1], rho


rng = np.random.default_rng(0)
ols_hits = ols_tot = aw_hits = aw_tot = 0
ar1s = []
per_subj_counts = []
for f in files:
    ts = np.loadtxt(f)
    if ts.ndim != 2 or ts.shape[0] < 60 or ts.shape[1] < 200:
        continue
    ts = ts[:, :200]; T = ts.shape[0]
    xreg = boxcar_regressor(T, rng)
    subj_sig = 0
    for j in range(ts.shape[1]):
        y = ts[:, j]
        if y.std() < 1e-6:
            continue
        ar1s.append(float(np.corrcoef(y[:-1], y[1:])[0, 1]))
        b, cov = np.polyfit(xreg, y, 1, cov=True)
        t_ols = b[0] / np.sqrt(cov[0, 0])
        ols_tot += 1; hit = abs(t_ols) > 1.96; ols_hits += hit; subj_sig += hit
        yw, xw, _ = ar1_prewhiten(y, xreg)
        bw, covw = np.polyfit(xw, yw, 1, cov=True)
        t_aw = bw[0] / np.sqrt(covw[0, 0])
        aw_tot += 1; aw_hits += abs(t_aw) > 1.96
    per_subj_counts.append(subj_sig)

if ols_tot == 0:
    fail("no usable region tests computed")
ols_fpr = ols_hits / ols_tot
aw_fpr = aw_hits / aw_tot
mean_ar1 = float(np.mean(ar1s))
mean_count = float(np.mean(per_subj_counts))

(OUT / "glm.json").write_text(json.dumps({
    "dataset": "ABIDE resting-state (rois_cc200, unfiltered)", "n_subjects": len(per_subj_counts),
    "n_regions": 200, "alpha": 0.05,
    "mean_significant_regions_per_subject_OLS": mean_count,
    "false_positive_rate_OLS": ols_fpr,
    "false_positive_rate_AR1_prewhitened": aw_fpr,
    "nominal_rate": 0.05,
    "OLS_inflation_vs_nominal": ols_fpr / 0.05,
    "data_mean_AR1": mean_ar1,
    "method": "per-ROI OLS GLM on a synthetic block regressor vs AR(1)-prewhitened GLM",
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200, nofilt_noglobal)",
    "n_subjects": len(per_subj_counts),
    "method": "first-level per-ROI GLM (OLS vs AR(1) prewhitening) on a synthetic block-design regressor",
}, indent=2))

(OUT / "findings.md").write_text(f"""# SPMAR-001 — first-level fMRI GLM and temporal autocorrelation

Data: {len(per_subj_counts)} ABIDE **resting-state** subjects, cc200 (200 regions), unfiltered. The
regressor is a synthetic HRF-convolved block design unrelated to the data, so the **true** number of
task-responsive regions is ≈ 0 and a calibrated test should flag ≈ 5% by chance.

## The naive OLS count is inflated ~4× by temporal autocorrelation
- OLS GLM at p<0.05: **{ols_fpr*100:.1f}%** of region tests are "significant"
  (≈ **{mean_count:.0f} of 200** regions per subject) — about **{ols_fpr/0.05:.1f}× the nominal 5%**.
- The time series are strongly autocorrelated (mean AR(1) = **{mean_ar1:.2f}**). OLS assumes
  independent residuals, so it underestimates the slope variance and **inflates the t-statistic** —
  producing far more "activations" than chance.
- **AR(1) prewhitening** (fit and remove the serial correlation, as SPM/FSL do) restores the
  false-positive rate to **{aw_fpr*100:.1f}%** — close to the nominal 5%.

## Conclusion
The OLS count of "significant" regions is **not trustworthy**: it is inflated ~{ols_fpr/0.05:.0f}×
by **unmodeled temporal autocorrelation** in the fMRI time series (Friston 2000; Woolrich 2001), not
by real task response. First-level fMRI GLMs must **prewhiten** (model the AR structure) before
thresholding; reporting the raw OLS significance count over-states the evidence.
""")
print(f"OK: n={len(per_subj_counts)} AR1={mean_ar1:.2f}; OLS FPR={ols_fpr:.3f} ({ols_fpr/0.05:.1f}x) "
      f"AR1-prewhitened={aw_fpr:.3f}")
