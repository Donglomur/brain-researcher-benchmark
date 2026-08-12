"""Reference (oracle) for DYNCONN-001 — dynamic functional connectivity (ABIDE, offline).

Paper anchor: Allen et al. 2014, Cereb Cortex (10.1093/cercor/bhs352) and Hutchison et al.
2013, NeuroImage — resting-state functional connectivity is not static: sliding-window FC
shows substantial window-to-window variability, characterised as recurring "dynamic
connectivity states."

This reference reads ONLY the packaged Dosenbach-160 ROI timeseries bundle (no network). It
FIRST reproduces that phenomenology (sliding-window FC does fluctuate substantially on these
data), THEN volunteers the un-cued check the task never asks: is that variability more than a
spectrum-matched STATIONARY process produces by sampling alone?

The correct null (Laumann 2017; Hindriks 2016; Liegeois 2017) is a multivariate PHASE-RANDOMISED
surrogate that preserves each ROI's power spectrum (autocorrelation) AND the cross-spectrum
(static covariance) — a stationary linear Gaussian process matched to the data's spectral
content. Per subject we draw MANY such surrogates (100) to build the null distribution, and test
the observed edge-variability against the null PAIRED across subjects (Wilcoxon signed-rank,
observed vs each subject's mean surrogate), reporting a p-value, at each of three window lengths.

Result (see receipt): the observed variability is only ~1.03-1.05x the null (a few % excess),
window-length-invariant, and ~96% of the apparent 'dynamics' is exactly what the stationary
surrogate reproduces. The small excess is statistically detectable (paired p is tiny with many
subjects) yet negligible in magnitude — so the fluctuations are overwhelmingly sampling
variability of a stationary process, NOT robust time-varying connectivity.

(A white-noise Gaussian null with only the static covariance is NOT valid here: it ignores
autocorrelation, so its ratio is window-length-dependent and unreliable.)

Validated numbers are written by this run and echoed to stdout (the receipt).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

RNG = np.random.RandomState(0)
OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "dos160_dynfc.npz"
NROI, STEP = 160, 4
WINDOWS = [22, 30, 44]     # TR; reported at all three to show window-length invariance
PRIMARY = 30
N_SURR = 100               # repeated phase-randomised surrogates per subject
IU = np.triu_indices(NROI, 1)


def fail(reason):
    (OUT / "dynamics.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from scipy import stats
except Exception as e:  # pragma: no cover
    fail(f"scipy import failed: {e}")

try:
    d = np.load(DATA, allow_pickle=True)
    ts = d["ts"]
except Exception as e:
    fail(f"could not load packaged timeseries bundle: {e}")


def mean_edge_std(x, win):
    """Mean over edges of the SD across sliding windows of the ROIxROI correlation matrix.
    (Batched; identical to per-window np.corrcoef with nan->0 for zero-variance windows.)"""
    T = x.shape[0]
    n_win = len(range(0, T - win + 1, STEP))
    if n_win < 3:
        return np.nan
    W = np.stack([x[s:s + win] for s in range(0, T - win + 1, STEP)])   # (M, win, N)
    W = W - W.mean(1, keepdims=True)
    nrm = np.linalg.norm(W, axis=1, keepdims=True)
    W = W / np.where(nrm > 1e-9, nrm, 1.0)                               # zero-var col -> ~0 (like nan->0)
    with np.errstate(all="ignore"):    # some BLAS backends flag spurious FP status on a finite matmul
        C = np.matmul(np.transpose(W, (0, 2, 1)), W)                     # (M, N, N) corr matrices
    E = C[:, IU[0], IU[1]]                                               # (M, edges)
    return float(E.std(0).mean())


def phase_rand_mv(x, rng):
    """Multivariate phase-randomised surrogate: one random phase per frequency shared across
    ROIs, preserving auto- AND cross-spectra -> a stationary process with the same covariance."""
    T = x.shape[0]
    Xf = np.fft.rfft(x, axis=0)
    ph = rng.uniform(0, 2 * np.pi, size=Xf.shape[0])
    ph[0] = 0.0
    if T % 2 == 0:
        ph[-1] = 0.0
    return np.fft.irfft(Xf * np.exp(1j * ph)[:, None], n=T, axis=0)


# per-subject observed edge-SD, per-subject mean surrogate edge-SD, per-subject empirical p
obs = {w: [] for w in WINDOWS}
nul_mean = {w: [] for w in WINDOWS}
emp_p = {w: [] for w in WINDOWS}
subjects = 0
for arr in ts:
    a = np.asarray(arr, float)
    if a.ndim != 2 or a.shape[0] < max(WINDOWS) + 10 or a.shape[1] < NROI:
        continue
    a = a[:, :NROI]
    a = (a - a.mean(0)) / (a.std(0) + 1e-8)           # z-score each ROI over time
    ro = {w: mean_edge_std(a, w) for w in WINDOWS}
    if not all(np.isfinite(v) for v in ro.values()):
        continue
    surr = {w: [] for w in WINDOWS}
    for _ in range(N_SURR):
        s = phase_rand_mv(a, RNG)
        for w in WINDOWS:
            surr[w].append(mean_edge_std(s, w))
    for w in WINDOWS:
        sv = np.asarray(surr[w], float)
        obs[w].append(ro[w])
        nul_mean[w].append(float(sv.mean()))
        emp_p[w].append(float((sv >= ro[w]).mean()))   # fraction of surrogates >= observed
    subjects += 1

if subjects < 30:
    fail(f"only {subjects} usable subjects in the packaged bundle")

per_window = {}
for w in WINDOWS:
    o = np.asarray(obs[w]); n = np.asarray(nul_mean[w])
    stat, p = stats.wilcoxon(o, n)                      # paired across subjects
    per_window[w] = {
        "observed_mean_edge_sd": float(o.mean()),
        "stationary_null_mean_edge_sd": float(n.mean()),
        "ratio_observed_over_null": float(o.mean() / n.mean()),
        "excess_over_null_pct": float(100 * (o.mean() - n.mean()) / o.mean()),
        "paired_wilcoxon_p": float(p),
        "n_subjects_observed_gt_null": int((o > n).sum()),
        "median_per_subject_empirical_p": float(np.median(emp_p[w])),
    }
pw = per_window[PRIMARY]
ratio = pw["ratio_observed_over_null"]
frac_explained = 100.0 * pw["stationary_null_mean_edge_sd"] / pw["observed_mean_edge_sd"]

(OUT / "dynamics.json").write_text(json.dumps({
    "n_subjects": subjects, "n_roi": NROI, "window_tr": PRIMARY, "step_tr": STEP,
    "n_surrogates_per_subject": N_SURR,
    "null_model": "multivariate phase-randomised surrogate (matched power + cross spectrum; stationary)",
    "observed_dfc_variability": pw["observed_mean_edge_sd"],
    "stationary_null_variability": pw["stationary_null_mean_edge_sd"],
    "ratio_observed_over_stationary_null": ratio,
    "excess_beyond_null_pct": pw["excess_over_null_pct"],
    "paired_null_test": "Wilcoxon signed-rank, observed vs per-subject mean surrogate, across subjects",
    "paired_wilcoxon_p": pw["paired_wilcoxon_p"],
    "n_subjects_observed_gt_null": pw["n_subjects_observed_gt_null"],
    "median_per_subject_empirical_p": pw["median_per_subject_empirical_p"],
    "per_window": {str(w): per_window[w] for w in WINDOWS},
    "ratio_by_window_tr": {str(w): per_window[w]["ratio_observed_over_null"] for w in WINDOWS},
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset": "ABIDE (ABIDE_pcp, cpac, rois_dosenbach160), packaged bundle dos160_dynfc.npz",
    "preprocessing": "band-pass filtered, no global-signal regression (cpac filt_noglobal), ROI z-scored",
    "atlas": "Dosenbach-160", "n_subjects": subjects,
    "window_tr": WINDOWS, "primary_window_tr": PRIMARY, "step_tr": STEP,
    "n_surrogates_per_subject": N_SURR,
    "method": "sliding-window mean edge SD vs 100 multivariate phase-randomised stationary surrogates "
              "per subject; paired Wilcoxon signed-rank (observed vs mean surrogate) across subjects; "
              "reported across window lengths 22/30/44 TR",
}, indent=2))

wl = "; ".join(f"{w}TR {per_window[w]['ratio_observed_over_null']:.2f}x" for w in WINDOWS)
(OUT / "findings.md").write_text(f"""# DYNCONN-001 — dynamic functional connectivity (ABIDE)

## Sliding-window connectivity does fluctuate (reproduces Allen 2014 / Hutchison 2013)
Time-resolved (sliding-window) connectivity shows substantial window-to-window variability
(mean edge standard deviation **{pw['observed_mean_edge_sd']:.3f}** over {PRIMARY}-TR windows,
step {STEP} TR) — the phenomenology described as dynamic connectivity "states." A naive analysis
stops here and declares time-varying connectivity states.

## But it barely exceeds a proper stationary null
Compared against **{N_SURR} multivariate phase-randomised surrogates per subject** — a stationary
linear process with the *same power spectrum (autocorrelation) and cross-spectrum (static
covariance)* as each subject — the observed variability is only **{ratio:.2f}x** the null
({pw['excess_over_null_pct']:.0f}% excess), and this ratio is essentially **invariant to window
length** ({wl}). About **{frac_explained:.0f}%** of the observed fluctuation is reproduced by the
stationary surrogate: the apparent "dynamics" barely exceed the null.

That small excess is statistically detectable — paired across subjects (Wilcoxon signed-rank,
observed vs each subject's mean surrogate) the observed edge-SD is systematically a few percent
above the null (p = {pw['paired_wilcoxon_p']:.1e}, {pw['n_subjects_observed_gt_null']}/{subjects}
subjects above their null). But statistical detectability is not magnitude: the excess is only a
few percent, so the observed dynamics are **overwhelmingly a sampling artifact of a stationary
process**, with at most a tiny genuine component.

(A white-noise null with only the static covariance would be invalid — it ignores autocorrelation
and gives a window-length-dependent ratio; the phase-randomised null used here is stable across
window lengths.)

## Conclusion
The observed dynamic functional connectivity is **largely sampling variability of a stationary
process**, not robust time-varying connectivity. Asserting genuine "dynamic connectivity states"
on these data over-claims: the fluctuations barely exceed a spectrum-matched stationary null
({ratio:.2f}x, ~{100-frac_explained:.0f}% excess), robustly across window choices — even though
that small excess is statistically reliable, its magnitude is negligible.
""")

print(f"OK: observed={pw['observed_mean_edge_sd']:.3f} null={pw['stationary_null_mean_edge_sd']:.3f} "
      f"ratio={ratio:.2f} by_window={{ {wl} }} paired_p={pw['paired_wilcoxon_p']:.1e} "
      f"n_obs>null={pw['n_subjects_observed_gt_null']}/{subjects} n={subjects} surr={N_SURR}")
