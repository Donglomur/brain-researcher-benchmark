"""Reference (oracle) for the top ASD-vs-control connectivity-difference task (ABIDE cc200).

Reproduces the case-control result — a set of edges differ between ASD and TD with a sizeable
effect size — then VOLUNTEERS the un-cued check the task never asks: are those SELECTED effect
sizes inflated by the selection itself (winner's curse)? They are. Selecting the top edges in a
DISCOVERY split and re-estimating their effect size on an INDEPENDENT validation split shows the
magnitudes shrink substantially — selecting the extreme edges capitalises on chance (regression
to the mean of selected extremes). The honest effect size is the held-out one.

Uses **Cohen's d** (a sample-size-independent effect size), not t (which grows with n), and
selects edges **only in the discovery split**. Reads the packaged connectome bundle (no network).

Validated numbers are written by this run and echoed to stdout (the receipt).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "cc200_connectomes.npz"
K = 100


def fail(reason):
    (OUT / "top_differences.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    d = np.load(DATA, allow_pickle=True)
    X, y = d["X"].astype(float), d["y"].astype(int)   # X: subjects x edges (Fisher-z), y: 1=ASD 2=TD
except Exception as e:
    fail(f"could not load packaged connectomes: {e}")
if X.shape[0] < 120:
    fail(f"only {X.shape[0]} subjects")


def cohens_d(M, grp):
    """per-edge Cohen's d, ASD(1) - TD(2), pooled SD."""
    a, c = M[grp == 1], M[grp == 2]
    na, nc = len(a), len(c)
    sp = np.sqrt(((na - 1) * a.var(0, ddof=1) + (nc - 1) * c.var(0, ddof=1)) / (na + nc - 2))
    return (a.mean(0) - c.mean(0)) / np.where(sp > 0, sp, np.nan)


# stratified discovery / validation split (50/50 within each group)
rng = np.random.RandomState(0)
disc = np.zeros(len(y), bool)
for g in (1, 2):
    gi = np.where(y == g)[0]
    disc[rng.permutation(gi)[:len(gi) // 2]] = True
val = ~disc

d_disc = cohens_d(X[disc], y[disc])
d_val = cohens_d(X[val], y[val])
# SELECT edges only in the discovery split, then read their held-out effect size
top = np.argsort(np.abs(np.nan_to_num(d_disc)))[::-1][:K]
disc_mean = float(np.nanmean(np.abs(d_disc[top])))
held_mean = float(np.nanmean(np.abs(d_val[top])))
shrink = float(1 - held_mean / disc_mean)
# do the selected magnitudes replicate? (nan-safe: drop edges with undefined d in either split)
ad, av = np.abs(d_disc[top]), np.abs(d_val[top])
mask = np.isfinite(ad) & np.isfinite(av)
repl = float(np.corrcoef(ad[mask], av[mask])[0, 1]) if mask.sum() > 2 else float("nan")

iu = np.triu_indices(200, 1)
top_conn = [{"pair": [int(iu[0][k]), int(iu[1][k])],
             "cohens_d_discovery": float(d_disc[k]), "cohens_d_held_out": float(d_val[k])}
            for k in top[:20]]

(OUT / "top_differences.json").write_text(json.dumps({
    "n_subjects": int(X.shape[0]), "n_discovery": int(disc.sum()), "n_validation": int(val.sum()),
    "n_selected": K, "atlas": "Craddock-200 (cc200)", "effect_size": "Cohen's d (ASD vs TD)",
    "top_connections": top_conn,
    "selected_effect_mean_abs_d_discovery": disc_mean,
    "selected_effect_mean_abs_d_held_out": held_mean,
    "held_out_shrinkage_frac": shrink,
    "discovery_vs_heldout_magnitude_corr": repl,
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_cc200), packaged bundle",
    "atlas": "Craddock-200", "n_subjects": int(X.shape[0]),
    "effect_size": "Cohen's d (pooled SD), ASD vs TD, per edge",
    "method": "select top-K edges by |d| in a discovery split; re-estimate |d| on an independent validation split",
}, indent=2))

(OUT / "findings.md").write_text(f"""# Top ASD-vs-control connectivity differences (ABIDE cc200)

## Edges do differ between groups (reproduces the case-control result)
Selecting the top {K} edges most different between ASD and TD (by |Cohen's d|) gives a sizeable
in-sample effect size — mean |d| = **{disc_mean:.2f}** in the discovery split. A naive analysis
stops here and reports these as the strongest autism connectivity differences.

## But the selected effect sizes are inflated by selection (winner's curse)
Re-estimating the *same* selected edges on an **independent validation split**, the mean effect
size falls to |d| = **{held_mean:.2f}** — a **{100*shrink:.0f}% shrinkage** (discovery-vs-held-out
magnitude correlation r = {repl:.2f}, so the selected magnitudes barely replicate). Selecting the
most extreme edges capitalises on chance (regression to the mean of selected extremes), so the
in-sample effect sizes **over-state** the true differences.

## Conclusion
There are ASD-vs-control connectivity differences, but the reported magnitudes of the *selected*
top edges are inflated by selection. The honest effect size is the **held-out** one
(|d| ≈ {held_mean:.2f}), not the in-sample value (|d| ≈ {disc_mean:.2f}); the top edges' effect
sizes must be quantified on independent data.
""")
print(f"OK: n={X.shape[0]}; selected top-{K} |d| discovery={disc_mean:.2f} held-out={held_mean:.2f} "
      f"shrinkage={100*shrink:.0f}% repl_r={repl:.2f}")
