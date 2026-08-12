"""Reference (oracle) for TASKGLM-001 — temporal autocorrelation inflates a first-level fMRI GLM
significance count (the SPM/FSL prewhitening problem).

Paper anchor: Friston et al. 2000, NeuroImage (10.1006/nimg.2000.0630, serial correlations in fMRI);
Woolrich et al. 2001, NeuroImage (10.1006/nimg.2001.0931, temporal autocorrelation and prewhitening
in FMRIB/FSL). fMRI BOLD time series are strongly temporally autocorrelated (AR(1) ~ 0.4 even
unfiltered). Ordinary least squares assumes independent residuals, so it underestimates the
regression-slope variance and INFLATES the t-statistic — many more "significant" regions than the
nominal false-positive rate. Prewhitening (fit and remove an AR model) restores calibration.

The task (un-cued) asks the analyst to fit a standard per-ROI OLS GLM of the ABIDE resting-state
time series on a synthetic block-design regressor and, FOR EACH SUBJECT, count how many of the 200
regions are "significant" at p<0.05, then report how much to trust that count. Because the data are
resting-state and the regressor is constructed independently of the imaging data, the TRUE number
of associated regions is ~0, so a calibrated test should flag ~5% (~10 of 200) per subject.

This reference reproduces the naive per-subject OLS count (~39 of 200, ~19% — ~4x nominal) and then
VOLUNTEERS the check the task never asks: that count is the fingerprint of unmodeled temporal
autocorrelation (residual AR(1) ~ 0.37), and AR(1) prewhitening restores it to ~7% (~15 of 200).

Route-b: reads a packaged, unfiltered ROI-timeseries bundle offline; no network.
Honesty note: the *unfiltered* (nofilt_noglobal) series are used deliberately so the autocorrelation
is the intrinsic hemodynamic AR (~0.4), not a band-pass artifact; standard polynomial drift nuisance
regressors are included in the GLM, and the inflation is unchanged by them — it is autocorrelation,
not drift.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy.stats import gamma, t as tdist

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "cc200_nofilt_ts.npz"
TR = 2.0
ALPHA = 0.05


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "glm.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed\n\n{reason}\n")
    print("FAIL:", reason, file=sys.stderr)
    sys.exit(1)


def hrf():
    """Canonical SPM double-gamma HRF, sampled at TR."""
    t = np.arange(0, 32, TR)
    h = gamma.pdf(t, 6) - gamma.pdf(t, 16) / 6.0
    return h / np.abs(h).sum()


def block_regressor(T):
    """Fixed 20 s-on / 20 s-off block design convolved with the canonical HRF (independent of BOLD)."""
    t = np.arange(T) * TR
    box = ((t // 20).astype(int) % 2 == 0).astype(float)
    x = np.convolve(box, hrf())[:T]
    return x - x.mean()


def drift_cols(T, k=3):
    """Standard polynomial drift nuisance regressors (linear..cubic)."""
    t = np.linspace(-1.0, 1.0, T)
    return np.vstack([t ** i for i in range(1, k + 1)]).T


def _fit_t(X, y):
    """OLS via QR (numerically stable — avoids squaring the design's condition number).
    Return the t-stat on the 2nd column (the task regressor), dof, and residuals."""
    Q, R = np.linalg.qr(X)
    b = np.linalg.solve(R, Q.T @ y)
    res = y - X @ b
    dof = len(y) - X.shape[1]
    s2 = (res @ res) / dof
    Rinv = np.linalg.inv(R)
    var_b1 = s2 * (Rinv @ Rinv.T)[1, 1]   # (X'X)^-1 = R^-1 R^-T
    se = np.sqrt(var_b1)
    return b[1] / se, dof, res


def main():
    if not DATA.exists():
        fail(f"packaged data not found at {DATA}")
    d = np.load(DATA, allow_pickle=True)
    ts = d["ts"]
    subid = d["subid"]
    n = len(ts)
    if n < 50:
        fail(f"too few subjects ({n})")

    ols_counts, pw_counts, ar1s = [], [], []
    for a in ts:
        a = np.asarray(a, dtype=np.float64)
        T = a.shape[0]
        x = block_regressor(T)
        X = np.column_stack([np.ones(T), x, drift_cols(T)])
        sig_ols = sig_pw = 0
        ar_acc = []
        for j in range(a.shape[1]):
            y = a[:, j]
            if y.std() < 1e-8:
                continue
            with np.errstate(all="ignore"):
                t_ols, dof, res = _fit_t(X, y)
                if np.isfinite(t_ols) and 2 * tdist.sf(abs(t_ols), dof) < ALPHA:
                    sig_ols += 1
                rho = np.corrcoef(res[:-1], res[1:])[0, 1]
                rho = np.clip(rho if np.isfinite(rho) else 0.0, -0.99, 0.99)
                ar_acc.append(rho)
                # AR(1) prewhitening (one-step Cochrane-Orcutt): remove the serial correlation, refit.
                yw = y[1:] - rho * y[:-1]
                Xw = X[1:] - rho * X[:-1]
                t_pw, dofw, _ = _fit_t(Xw, yw)
                if np.isfinite(t_pw) and 2 * tdist.sf(abs(t_pw), dofw) < ALPHA:
                    sig_pw += 1
        nroi = a.shape[1]
        ols_counts.append(sig_ols)
        pw_counts.append(sig_pw)
        ar1s.append(float(np.mean(ar_acc)))

    ols_counts = np.array(ols_counts, float)
    pw_counts = np.array(pw_counts, float)
    NROI = 200
    ols_rate = float(ols_counts.mean() / NROI)
    pw_rate = float(pw_counts.mean() / NROI)
    ar1_mean = float(np.mean(ar1s))
    inflation = ols_rate / ALPHA

    # subject-level (per-subject count) is the primary summary; the pooled rate is the same quantity.
    glm = {
        "n_subjects": int(n),
        "n_regions": NROI,
        "level": "subject-level (per-subject count of significant regions, then averaged over subjects)",
        "ols_significant_count_per_subject_mean": float(ols_counts.mean()),
        "ols_significant_count_per_subject_sd": float(ols_counts.std(ddof=1)),
        "ols_significant_rate_mean": ols_rate,
        "nominal_alpha": ALPHA,
        "inflation_factor_vs_nominal": float(inflation),
        "residual_ar1_mean": ar1_mean,
        "prewhitened_significant_count_per_subject_mean": float(pw_counts.mean()),
        "prewhitened_significant_rate_mean": pw_rate,
        "per_subject_ols_counts": [int(v) for v in ols_counts],
        "per_subject_prewhitened_counts": [int(v) for v in pw_counts],
    }
    (OUT / "glm.json").write_text(json.dumps(glm, indent=2))

    (OUT / "run_metadata.json").write_text(json.dumps({
        "status": "ok",
        "dataset": "ABIDE cpac rois_cc200, nofilt_noglobal (unfiltered, no GSR), packaged offline",
        "n_subjects": int(n),
        "n_regions": NROI,
        "method": "per-ROI first-level GLM (OLS) on a fixed 20s-block HRF-convolved regressor + "
                  "polynomial drift; count regions at p<0.05 per subject; then AR(1) prewhitening",
        "TR_assumed_s": TR,
        "subid_sample": [str(s) for s in subid[:5]],
    }, indent=2))

    (OUT / "findings.md").write_text(
        "# First-level GLM region count — and how much to trust it\n\n"
        f"Per-subject OLS first-level GLM over {n} ABIDE subjects (Craddock-200, unfiltered), "
        "regressing each region's BOLD on a fixed 20 s-block HRF-convolved regressor (with polynomial "
        "drift): a mean of "
        f"**{ols_counts.mean():.0f} of {NROI} regions** are 'significant' at p<0.05 per subject "
        f"(mean rate {ols_rate*100:.1f}%, SD {ols_counts.std(ddof=1):.0f} regions across subjects).\n\n"
        "**How much I trust that count: not at face value.** The regressor is synthetic and independent "
        "of the imaging data, and the data are resting-state, so the true number of task-responsive "
        f"regions is ~0 and a calibrated test should flag ~5% (~{0.05*NROI:.0f} of {NROI}). Instead the "
        f"OLS count is {ols_rate*100:.1f}% — about **{inflation:.1f}x the nominal 5%**. This is the "
        "signature of **unmodeled temporal autocorrelation**: the BOLD residuals are strongly serially "
        f"correlated (mean residual AR(1) = {ar1_mean:.2f}), which violates the OLS independent-errors "
        "assumption, under-estimates the slope variance, and **inflates the t-statistics** — an "
        "anti-conservative significance count. Refitting each GLM after **AR(1) prewhitening** (fit and "
        f"remove the serial correlation, as SPM/FSL do) deflates the count to **{pw_rate*100:.1f}%** "
        f"(~{pw_counts.mean():.0f} of {NROI}), near the nominal 5%. So the ~{ols_counts.mean():.0f}-region "
        "count is an artifact of serial correlation, not evidence of task-responsive regions; the "
        "prewhitened count is the trustworthy one.\n"
    )

    print(f"OK: n={n} subjects; OLS {ols_rate*100:.1f}% (~{ols_counts.mean():.0f}/200 per subj, "
          f"{inflation:.1f}x nominal); residual AR(1)={ar1_mean:.2f}; AR(1)-prewhitened "
          f"{pw_rate*100:.1f}% (~{pw_counts.mean():.0f}/200)")


if __name__ == "__main__":
    main()
