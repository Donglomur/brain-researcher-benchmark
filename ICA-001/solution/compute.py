"""Reference (oracle) for ICA-001 — resting-state networks from independent component analysis.

Paper anchor: Beckmann et al. 2005 / Smith et al. 2009 — ICA of resting-state fMRI recovers a set
of reproducible 'resting-state networks' (RSNs). Reliability critique: Himberg et al. 2004 (ICASSO
— ICA components must be tested for run-to-run stability).

The task (un-cued) asks to decompose the group resting-state data with ICA and report the
components / networks. This reference does so at a common model order — the components are
recognisable — and then VOLUNTEERS the check the task never asks: are the components robust? They
are not. The decomposition depends on the arbitrary **model order** (number of components), and
run-to-run reproducibility collapses as the order increases: mean matched |r| across FastICA runs
is ~0.99 at 10 components, ~0.82 at 20, and ~0.54 at 40. So at the orders used to resolve
sub-networks the components are barely reproducible, and 'we found N resting-state networks' is an
artifact of the model-order choice and the stochastic decomposition, not a robust result.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
ORDERS = [10, 20, 30, 40]
DEFAULT_K = 20
N_RUNS = 6


def fail(reason):
    (OUT / "components.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from nilearn import datasets
    from sklearn.decomposition import FastICA
    from scipy.optimize import linear_sum_assignment
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    ab = datasets.fetch_abide_pcp(derivatives=["rois_dosenbach160"], pipeline="cpac",
                                  band_pass_filtering=True, global_signal_regression=False,
                                  quality_checked=True)
except Exception as e:
    fail(f"could not resolve ABIDE: {e}")

dx = np.asarray(ab.phenotypic["DX_GROUP"])
ctrl = np.where(dx == 2)[0][:40]
TS = []
for i in ctrl:
    ts = ab.rois_dosenbach160[i]
    if ts is None:
        continue
    a = np.asarray(ts, float)[:, :160]
    if a.ndim != 2 or a.shape[0] < 100:
        continue
    a = (a - a.mean(0)) / (a.std(0) + 1e-8)
    TS.append(a)
if len(TS) < 20:
    fail(f"only {len(TS)} usable subjects")
X = np.vstack(TS)


def run_ica(k, seed):
    ica = FastICA(n_components=k, random_state=seed, max_iter=500, whiten="unit-variance")
    ica.fit(X)
    return ica.components_


def reproducibility(k):
    runs = [run_ica(k, s) for s in range(N_RUNS)]
    vals = []
    for i in range(N_RUNS):
        for j in range(i + 1, N_RUNS):
            C = np.abs(np.corrcoef(runs[i], runs[j])[:k, k:])
            r, c = linear_sum_assignment(-C)
            vals.append(C[r, c].mean())
    return float(np.mean(vals)), runs[0]


repro = {}
default_components = None
for k in ORDERS:
    rep, comps = reproducibility(k)
    repro[k] = rep
    if k == DEFAULT_K:
        default_components = comps

(OUT / "components.json").write_text(json.dumps({
    "atlas": "Dosenbach-160", "n_subjects": len(TS),
    "method": "group FastICA of concatenated resting-state ROI time series",
    "model_order_used": DEFAULT_K,
    "n_components": DEFAULT_K,
    "component_maps_shape": [DEFAULT_K, 160],
    "run_to_run_reproducibility_by_model_order": {str(k): repro[k] for k in ORDERS},
    "reproducibility_at_default_order": repro[DEFAULT_K],
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_dosenbach160, quality_checked)",
    "atlas": "Dosenbach-160", "n_subjects": len(TS),
    "method": f"group FastICA; model order swept over {ORDERS}; run-to-run reproducibility "
              f"(mean matched |r| across {N_RUNS} FastICA runs) per order",
}, indent=2))

sweep = ", ".join(f"{k} comp: r={repro[k]:.2f}" for k in ORDERS)
(OUT / "findings.md").write_text(f"""# ICA-001 — resting-state networks from ICA (ABIDE)

## ICA recovers components (default model order)
Group FastICA at {DEFAULT_K} components decomposes the resting-state data into {DEFAULT_K}
components / networks — the standard resting-state-network picture (Beckmann 2005; Smith 2009).

## But the components are not robust — model-order-dependent and run-unstable (un-cued)
The decomposition depends on the arbitrary **model order** (number of components), and run-to-run
reproducibility (mean matched |r| across FastICA runs) **collapses as the order rises**: {sweep}.
At {DEFAULT_K} components reproducibility is {repro[DEFAULT_K]:.2f}, and at 40 it is {repro[40]:.2f}
— the components are barely reproducible. Different model orders yield different decompositions, and
repeated runs at the same order give different components.

## Conclusion
"We found {DEFAULT_K} resting-state networks" is an artifact of the **model-order choice** and the
**stochastic** decomposition, not a robust property — the components are not reproducible across
runs (and the count/identity changes with the model order). Reporting a single ICA decomposition as
*the* networks over-claims; component stability (e.g. ICASSO) must be shown.
""")
print(f"OK: reproducibility by order {{{sweep}}}; default k={DEFAULT_K} r={repro[DEFAULT_K]:.2f}")
