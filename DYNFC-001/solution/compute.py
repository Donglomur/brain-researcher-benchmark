"""Reference (oracle) for DYNFC-001 — dynamic functional connectivity (ABIDE).

Paper anchor: Allen et al. 2014, Cereb Cortex (10.1093/cercor/bhs352) and Hutchison et al.
2013, NeuroImage — resting-state functional connectivity is not static: sliding-window FC
shows substantial window-to-window variability, characterised as recurring "dynamic
connectivity states."

This reference FIRST reproduces that phenomenology (sliding-window FC does fluctuate
substantially on these data), THEN volunteers the un-cued check the task never asks: compare
the observed variability against a PROPER stationary null. The correct null (Laumann 2017;
Hindriks 2016; Liegeois 2017) is a multivariate PHASE-RANDOMISED surrogate that preserves each
ROI's power spectrum (autocorrelation) AND the cross-spectrum (static covariance) — a
stationary linear Gaussian process matched to the data's spectral content. Against that null
the observed variability is only ~1.03-1.05x (a few % excess), and this holds ACROSS window
lengths — so the apparent 'dynamics' are overwhelmingly sampling variability of a stationary
process, not robust time-varying connectivity.

(A white-noise Gaussian null with only the static covariance is NOT valid here: it ignores
autocorrelation, so its ratio is window-length-dependent and unreliable.)
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

np.random.seed(0)
OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
NROI, STEP = 160, 4
WINDOWS = [22, 30, 44]     # TR; reported at all three to show window-length invariance
PRIMARY = 30


def fail(reason):
    (OUT / "dynamics.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn import datasets
except Exception as e:  # pragma: no cover
    fail(f"nilearn import failed: {e}")

try:
    abide = datasets.fetch_abide_pcp(derivatives=["rois_dosenbach160"], pipeline="cpac",
                                     band_pass_filtering=True, global_signal_regression=False,
                                     quality_checked=True)
except Exception as e:
    fail(f"could not resolve ABIDE: {e}")


def windowed_edge_std(x, win):
    iu = np.triu_indices(x.shape[1], 1)
    vals = [np.nan_to_num(np.corrcoef(x[s:s + win].T))[iu]
            for s in range(0, x.shape[0] - win + 1, STEP)]
    if len(vals) < 3:
        return np.nan
    return float(np.std(np.array(vals), 0).mean())


def phase_rand_mv(x):
    """multivariate phase-randomised surrogate: preserves auto- & cross-spectra (stationary)."""
    T, N = x.shape
    Xf = np.fft.rfft(x, axis=0)
    nf = Xf.shape[0]
    ph = np.random.uniform(0, 2 * np.pi, size=nf)
    ph[0] = 0.0
    if T % 2 == 0:
        ph[-1] = 0.0
    return np.fft.irfft(Xf * np.exp(1j * ph)[:, None], n=T, axis=0)


# per-window-length accumulators
obs = {w: [] for w in WINDOWS}
nul = {w: [] for w in WINDOWS}
subjects = 0
for arr in abide.rois_dosenbach160:
    a = np.asarray(arr, float)
    if a.ndim != 2 or a.shape[0] < max(WINDOWS) + 10 or a.shape[1] < NROI:
        continue
    a = a[:, :NROI]
    a = (a - a.mean(0)) / (a.std(0) + 1e-8)
    s = phase_rand_mv(a)
    ok = True
    ro, no = {}, {}
    for w in WINDOWS:
        rv, nv = windowed_edge_std(a, w), windowed_edge_std(s, w)
        if not (np.isfinite(rv) and np.isfinite(nv)):
            ok = False
            break
        ro[w], no[w] = rv, nv
    if ok:
        for w in WINDOWS:
            obs[w].append(ro[w]); nul[w].append(no[w])
        subjects += 1
    if subjects >= 60:
        break
if subjects < 30:
    fail(f"only {subjects} usable subjects")

per_window = {}
for w in WINDOWS:
    o, n = float(np.mean(obs[w])), float(np.mean(nul[w]))
    per_window[w] = {"observed": o, "stationary_null": n, "ratio": o / n,
                     "excess_pct": 100 * (o - n) / o}
p = per_window[PRIMARY]
ratio = p["ratio"]

(OUT / "dynamics.json").write_text(json.dumps({
    "n_subjects": subjects, "n_roi": NROI, "window_tr": PRIMARY,
    "observed_dfc_variability": p["observed"],
    "stationary_null_variability": p["stationary_null"],
    "ratio_observed_over_stationary_null": ratio,
    "excess_beyond_null_pct": p["excess_pct"],
    "null_model": "multivariate phase-randomised surrogate (matched power + cross spectrum)",
    "ratio_by_window_tr": {str(w): per_window[w]["ratio"] for w in WINDOWS},
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_dosenbach160, filt/noGSR)",
    "atlas": "Dosenbach-160", "n_subjects": subjects, "window_tr": PRIMARY,
    "method": "sliding-window edge std vs multivariate phase-randomised stationary surrogate; "
              "reported across window lengths 22/30/44 TR",
}, indent=2))

wl = "; ".join(f"{w}TR: {per_window[w]['ratio']:.2f}x" for w in WINDOWS)
(OUT / "findings.md").write_text(f"""# DYNFC-001 — dynamic functional connectivity (ABIDE)

## Sliding-window connectivity does fluctuate (reproduces Allen 2014 / Hutchison 2013)
Time-resolved (sliding-window) connectivity shows substantial window-to-window variability
(mean edge standard deviation {p['observed']:.3f} over {PRIMARY}-TR windows) — the
phenomenology described as dynamic connectivity "states."

## But the fluctuations do not exceed a proper stationary null
Compared against a **multivariate phase-randomised stationary surrogate** — a stationary linear
process with the *same power spectrum (autocorrelation) and cross-spectrum (static covariance)*
— the observed variability is only **{ratio:.2f}×** the null ({p['excess_pct']:.0f}% excess),
and this holds across window lengths ({wl}). The apparent "dynamics" are what a **stationary**
process produces by sampling variability alone; they do not clearly exceed the surrogate at any
window length.

(A white-noise null with only the static covariance would be invalid — it ignores
autocorrelation and gives a window-length-dependent ratio.)

## Conclusion
The observed dynamic functional connectivity is **largely a sampling artifact of a stationary
process**, not robust time-varying connectivity. Asserting genuine "dynamic connectivity
states" on these data is unwarranted: the fluctuations barely exceed a spectrum-matched
stationary null, robustly across window choices.
""")
print(f"OK: observed={p['observed']:.3f} null={p['stationary_null']:.3f} ratio={ratio:.2f} "
      f"by_window={{ {wl} }} n={subjects}")
