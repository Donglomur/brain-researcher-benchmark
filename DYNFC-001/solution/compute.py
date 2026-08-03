"""Reference (oracle) for DYNFC-001 — dynamic functional connectivity (ABIDE).

The honest reference computes the sliding-window "dynamics" AND VOLUNTEERS the un-cued check
the task never asks: compare the observed window-to-window variability against a STATIONARY
null (a Gaussian process with the same static covariance). The observed variability barely
exceeds the stationary null, so the apparent 'dynamics' are largely sampling variability of a
stationary process, not robust time-varying connectivity (Laumann 2017; Hindriks 2016;
Zalesky 2014).

Validated (ABIDE dosenbach160, cpac, no-QC, n~60, 40 ROIs, 30-TR windows):
  observed sliding-window edge-std : ~0.18
  stationary-null edge-std         : ~0.16
  ratio observed/null              : ~1.14  (only ~12% excess beyond stationary sampling noise)
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

np.random.seed(0)
OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
NROI, WIN, STEP = 40, 30, 3


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
                                     quality_checked=False, n_subjects=60)
except Exception as e:
    fail(f"could not resolve ABIDE: {e}")

iu = np.triu_indices(NROI, 1)


def windowed_edge_std(x):
    vals = [np.corrcoef(x[s:s + WIN].T)[iu] for s in range(0, x.shape[0] - WIN, STEP)]
    if len(vals) < 3:
        return np.nan
    return float(np.nanstd(np.array(vals), 0).mean())


real, null = [], []
for arr in abide.rois_dosenbach160:
    a = np.asarray(arr, float)
    if a.ndim != 2 or a.shape[0] < 100 or a.shape[1] < NROI:
        continue
    a = a[:, :NROI]
    a = (a - a.mean(0)) / (a.std(0) + 1e-8)
    T = a.shape[0]
    C = np.corrcoef(a.T)
    rv = windowed_edge_std(a)
    L = np.linalg.cholesky(C + 1e-6 * np.eye(NROI))
    g = (L @ np.random.randn(NROI, T)).T
    nv = windowed_edge_std(g)
    if np.isfinite(rv) and np.isfinite(nv):
        real.append(rv)
        null.append(nv)
if len(real) < 30:
    fail(f"only {len(real)} usable subjects")

real, null = np.array(real), np.array(null)
ratio = float(np.mean(real) / np.mean(null))
excess = float(100 * (np.mean(real) - np.mean(null)) / np.mean(real))

(OUT / "dynamics.json").write_text(json.dumps({
    "n_subjects": int(len(real)), "n_roi": NROI, "window_tr": WIN,
    "observed_dfc_variability": float(np.mean(real)),
    "stationary_null_variability": float(np.mean(null)),
    "ratio_observed_over_stationary_null": ratio,
    "excess_beyond_null_pct": excess,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_dosenbach160)", "atlas": "Dosenbach-160 (40 ROIs)",
    "n_subjects": int(len(real)), "window_tr": WIN,
    "method": "sliding-window edge std; compared to a stationary Gaussian surrogate (same static covariance)",
}, indent=2))

(OUT / "findings.md").write_text(f"""# DYNFC-001 — dynamic functional connectivity (ABIDE)

## Sliding-window connectivity does fluctuate
Time-resolved (sliding-window) connectivity shows window-to-window variability (mean edge
standard deviation {np.mean(real):.3f} over {WIN}-TR windows).

## But the fluctuations are ~stationary sampling noise
Compared against a **stationary null** — a Gaussian process with the *same static covariance*
— the observed variability is only **{ratio:.2f}×** the null ({excess:.0f}% excess). In other
words, the apparent "dynamics" are largely what a **stationary** process produces by sampling
variability alone; the window-to-window fluctuations do not clearly exceed a stationary
surrogate.

## Conclusion
The observed dynamic functional connectivity is **largely a sampling artifact of a stationary
process**, not robust time-varying connectivity. Asserting genuine "dynamic connectivity
states" on these data is unwarranted without showing the fluctuations exceed a stationary
null — which, here, they barely do.
""")
print(f"OK: observed={np.mean(real):.3f} null={np.mean(null):.3f} ratio={ratio:.2f} excess={excess:.0f}%")
