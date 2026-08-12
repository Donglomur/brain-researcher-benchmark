"""Reference (oracle) for RESTNETS-001 — resting-state networks from independent component analysis.

Paper anchor: Beckmann et al. 2005 / Smith et al. 2009 (PNAS) — ICA of resting-state fMRI recovers
a canonical set of 'resting-state networks' (RSNs). Reliability critique: Himberg et al. 2004
(ICASSO — ICA components must be tested for run-to-run stability).

Route b (offline): reads ONLY the packaged bundle `data/dos160_ica.npz` (ABIDE control-subject
Dosenbach-160 ROI time series, float16, + diagnosis phenotype). No network, no nilearn.

The task (un-cued) asks to decompose the group resting-state data with ICA and REPORT THE
COMPONENTS. This reference does exactly that — it emits the ACTUAL ICA result: the component
spatial maps / loadings (n_components x 160) and a short description of each component — and then
VOLUNTEERS the check the task never asks: are those components reproducible? They are not. The
decomposition is governed by the arbitrary **model order** and a **stochastic** algorithm, so:
  * run-to-run reproducibility (mean matched |r| across FastICA seeds) COLLAPSES as the order rises
    — ~0.93 at 10 components, ~0.76 at 20, ~0.63 at 30, ~0.53 at 40;
  * a split-half decomposition at the default order matches only ~0.46.
So 'we found N resting-state networks' is an artifact of the model-order choice and the random
initialisation, not a robust result. The honest answer volunteers the reproducibility gap.

Emitted for the verifier to CHECK the actual data (not just prose):
  component_maps.csv  — the n_components x 160 component loadings (the real ICA result)
  components.json     — the maps, per-component descriptions, reproducibility by model order /
                        across seeds / split-half, n_subjects
  run_metadata.json   — dataset, atlas, method, n_subjects
  findings.md         — recovers the components + the reproducibility gap + conclusion

Validated numbers are written by this run and echoed to stdout (the receipt).
"""
import csv
import json
import os
import sys
import warnings
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")
OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "dos160_ica.npz"
ORDERS = [10, 20, 30, 40]   # model-order sweep for the reproducibility check
DEFAULT_K = 20              # common RSN model order — the reported decomposition
N_RUNS = 6                  # FastICA seeds per order (run-to-run reproducibility)
N_ROIS = 160


def fail(reason):
    (OUT / "components.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    from sklearn.decomposition import FastICA
    from scipy.optimize import linear_sum_assignment
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    d = np.load(DATA, allow_pickle=True)
    ts = d["ts"]
except Exception as e:
    fail(f"could not load packaged time series: {e}")

# z-score each subject's ROI time series, then concatenate into one group data matrix
TS = []
for a in ts:
    a = np.asarray(a, float)[:, :N_ROIS]
    if a.ndim != 2 or a.shape[0] < 100 or a.shape[1] < N_ROIS:
        continue
    a = (a - a.mean(0)) / (a.std(0) + 1e-8)
    TS.append(a)
if len(TS) < 20:
    fail(f"only {len(TS)} usable subjects")
X = np.vstack(TS)


def run_ica(Xm, k, seed):
    """Group FastICA -> component spatial maps (k x N_ROIS)."""
    ica = FastICA(n_components=k, random_state=seed, max_iter=1000, tol=1e-3, whiten="unit-variance")
    ica.fit(Xm)
    return ica.components_


def matched_r(A, B, k):
    """Mean |correlation| of best-matched component pairs (Hungarian) between two decompositions."""
    C = np.abs(np.corrcoef(A, B)[:k, k:])
    r, c = linear_sum_assignment(-C)
    return float(C[r, c].mean())


# ---- the reported decomposition: the ACTUAL ICA result at the default model order ----
comps = run_ica(X, DEFAULT_K, 0)                       # DEFAULT_K x 160 component maps
descriptions = []
for i, m in enumerate(comps):
    top = np.argsort(np.abs(m))[::-1][:5]
    descriptions.append({
        "component": i,
        "top_rois": [int(j) for j in top],
        "peak_abs_loading": float(np.abs(m).max()),
        "summary": f"spatial map peaks on Dosenbach-160 ROIs {list(int(j) for j in top[:3])} "
                   f"(|loading| up to {float(np.abs(m).max()):.3f})",
    })

# ---- the volunteered reproducibility check (un-cued) ----
# (a) run-to-run reproducibility across random seeds, per model order
repro_by_order = {}
for k in ORDERS:
    runs = [run_ica(X, k, s) for s in range(N_RUNS)]
    vals = [matched_r(runs[i], runs[j], k)
            for i in range(N_RUNS) for j in range(i + 1, N_RUNS)]
    repro_by_order[k] = float(np.mean(vals))
seed_repro_default = repro_by_order[DEFAULT_K]        # across-seed reproducibility at default order

# (b) split-half reproducibility at the default order (independent subject halves)
rng = np.random.RandomState(0)
perm = rng.permutation(len(TS))
h1 = np.vstack([TS[i] for i in perm[:len(TS) // 2]])
h2 = np.vstack([TS[i] for i in perm[len(TS) // 2:]])
split_half = matched_r(run_ica(h1, DEFAULT_K, 0), run_ica(h2, DEFAULT_K, 0), DEFAULT_K)

# ---- component_maps.csv: the actual maps the verifier checks (K rows x 160 cols) ----
with open(OUT / "component_maps.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow([f"roi_{j}" for j in range(N_ROIS)])
    for m in comps:
        w.writerow([f"{v:.6f}" for v in m])

(OUT / "components.json").write_text(json.dumps({
    "atlas": "Dosenbach-160", "n_rois": N_ROIS, "n_subjects": len(TS),
    "method": "group FastICA of concatenated, per-subject z-scored resting-state ROI time series",
    "model_order_used": DEFAULT_K, "n_components": DEFAULT_K,
    "component_maps_shape": [DEFAULT_K, N_ROIS],
    "component_maps": [[float(v) for v in m] for m in comps],
    "components": descriptions,
    "run_to_run_reproducibility_by_model_order": {str(k): repro_by_order[k] for k in ORDERS},
    "reproducibility_across_seeds_at_default_order": seed_repro_default,
    "split_half_reproducibility_at_default_order": split_half,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset": "ABIDE (ABIDE_pcp, cpac, rois_dosenbach160), packaged control-subject bundle",
    "atlas": "Dosenbach-160", "n_subjects": len(TS), "n_rois": N_ROIS,
    "method": f"group FastICA at model order {DEFAULT_K} (reported decomposition); model order "
              f"swept over {ORDERS} with {N_RUNS} random seeds each, plus a split-half, to test "
              f"reproducibility (mean best-matched |r| between decompositions)",
}, indent=2))

sweep = ", ".join(f"{k} comp: r={repro_by_order[k]:.2f}" for k in ORDERS)
(OUT / "findings.md").write_text(f"""# RESTNETS-001 — resting-state networks from ICA (ABIDE, Dosenbach-160)

## ICA recovers components (reproduces the RSN decomposition)
Group FastICA of the concatenated, z-scored control-subject time series (n = {len(TS)} subjects)
at the default model order of {DEFAULT_K} components returns {DEFAULT_K} spatial maps
({DEFAULT_K} x {N_ROIS} loadings; see `component_maps.csv`) — the standard resting-state-network
picture (Beckmann 2005; Smith 2009). A naive analysis stops here and reports "we found {DEFAULT_K}
resting-state networks."

## But the components are not reproducible — model-order-dependent and run-unstable (un-cued)
The decomposition is governed by the arbitrary **model order** and the **random initialisation**.
Run-to-run reproducibility (mean best-matched |r| across {N_RUNS} FastICA seeds) **collapses as the
model order rises**: {sweep}. At the reported order of {DEFAULT_K} the components are only
{seed_repro_default:.2f} reproducible across seeds, and a **split-half** decomposition (independent
subject halves) matches only **{split_half:.2f}** — so the same data re-split gives a substantially
different set of maps. Different model orders give different numbers of components, and repeated runs
at the same order give different components.

## Conclusion
"We found {DEFAULT_K} resting-state networks" is an artifact of the **model-order choice** and the
**stochastic** decomposition, not a robust result — the components are barely reproducible across
random seeds (~{seed_repro_default:.2f} at order {DEFAULT_K}) and across independent split-halves
(~{split_half:.2f}), and reproducibility falls to ~{repro_by_order[40]:.2f} at 40 components.
Reporting a single ICA decomposition as *the* networks over-claims; component stability (e.g.
ICASSO — reproducibility across model order / random seeds / split-half) must be shown before the
components can be trusted.
""")
print(f"OK: n={len(TS)}; k={DEFAULT_K}; maps {DEFAULT_K}x{N_ROIS}; "
      f"run-to-run reproducibility {{{sweep}}}; seed@{DEFAULT_K}={seed_repro_default:.2f}; "
      f"split-half={split_half:.2f}")
