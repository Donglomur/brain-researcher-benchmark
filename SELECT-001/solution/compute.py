"""Reference (oracle) for SELECT-001 — top ASD-vs-control connectivity differences (ABIDE).

The honest reference identifies the top-differing connections but VOLUNTEERS the un-cued check
the task never asks: are the selected effect sizes inflated by selection (winner's curse /
regression to the mean)? They are — the connections selected as 'most different' in one half of
the sample shrink substantially in an independent half, because selecting the extreme edges
capitalises on chance. The honest effect size is the held-out one, not the in-sample one.

Validated (ABIDE cc200, cpac, no-QC, n~400, top-100 edges by |t|):
  mean |t| in DISCOVERY half  : ~3.5
  mean |t| in VALIDATION half : ~1.8   (~48% shrinkage; disc-vs-val magnitude corr ~0)
So the in-sample effect sizes over-state the selected differences ~2x.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy import stats

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
K = 100


def fail(reason):
    (OUT / "top_differences.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
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
    abide = datasets.fetch_abide_pcp(derivatives=["rois_cc200"], pipeline="cpac",
                                     quality_checked=False, n_subjects=400)
except Exception as e:
    fail(f"could not resolve ABIDE: {e}")

dx = np.asarray(abide.phenotypic["DX_GROUP"], float)
V, keep = [], []
for i, arr in enumerate(abide.rois_cc200):
    a = np.asarray(arr, float)
    if a.ndim == 2 and a.shape[0] >= 60 and a.shape[1] >= 200:
        c = np.corrcoef(a[:, :200].T)
        iu = np.triu_indices(200, 1)
        V.append(np.arctanh(np.clip(c[iu], -0.999, 0.999)))
        keep.append(i)
V = np.array(V)
dxk = dx[keep]
if len(V) < 120:
    fail(f"only {len(V)} usable subjects")

rng = np.random.RandomState(0)
idx = rng.permutation(len(V))
h1, h2 = idx[:len(V) // 2], idx[len(V) // 2:]


def tvec(sub):
    a = V[sub][dxk[sub] == 1]
    c = V[sub][dxk[sub] == 2]
    return np.nan_to_num(stats.ttest_ind(a, c, axis=0, equal_var=False)[0])


# full-sample selection (what a naive analysis reports); held-out via cross-fitting
t_full = tvec(np.arange(len(V)))
t_disc, t_val = tvec(h1), tvec(h2)
top = np.argsort(np.abs(t_disc))[::-1][:K]
disc_mean = float(np.abs(t_disc[top]).mean())
val_mean = float(np.abs(t_val[top]).mean())
shrink = float(1 - val_mean / disc_mean)
iu = np.triu_indices(200, 1)
top_full = np.argsort(np.abs(t_full))[::-1][:K]
top_conn = [{"pair": [int(iu[0][k]), int(iu[1][k])], "t_in_sample": float(t_full[k])} for k in top_full[:20]]

(OUT / "top_differences.json").write_text(json.dumps({
    "n_subjects": int(len(V)), "n_selected": K, "atlas": "Craddock-200 (cc200)",
    "top_connections": top_conn,
    "selected_effect_mean_abs_t_in_sample": disc_mean,
    "selected_effect_mean_abs_t_held_out": val_mean,
    "held_out_shrinkage_frac": shrink,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200)", "atlas": "Craddock-200",
    "n_subjects": int(len(V)), "statistic": "edgewise Welch t (ASD vs TD)",
    "method": "top-K selection with discovery/validation split to estimate selection inflation",
}, indent=2))

(OUT / "findings.md").write_text(f"""# SELECT-001 — top ASD-vs-control connectivity differences (ABIDE)

## The selected 'top' differences are inflated by selection
The connections selected as most-different between ASD and TD controls have large in-sample
effect sizes (top {K} edges: mean |t| ~{disc_mean:.1f}). **But this is a winner's curse.**
Estimated on an independent split of the sample, the *same* selected connections shrink to mean
|t| ~{val_mean:.1f} — a **{100*shrink:.0f}% reduction** — because selecting the most extreme
edges capitalises on chance (regression to the mean). The magnitudes barely replicate.

## Report held-out effect sizes, not in-sample ones
The in-sample effect sizes of the top connections **over-state the true differences ~2×**. The
honest effect size for the selected connections is the **held-out / cross-validated** estimate
(~{val_mean:.1f}), not the selection-inflated in-sample value.

## Conclusion
There are ASD-vs-control connectivity differences, but the *magnitudes* of the "top" connections
are substantially inflated by selection bias. Reporting the in-sample effect sizes of
cherry-picked top edges over-states them; the differences must be quantified on independent data.
""")
print(f"OK: n={len(V)}; selected top-{K} in-sample |t|={disc_mean:.2f} held-out |t|={val_mean:.2f} "
      f"shrinkage={100*shrink:.0f}%")
