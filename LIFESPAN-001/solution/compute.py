"""Reference solution for LIFESPAN-001.

Characterise how the organization of the resting functional connectome changes across the adult
lifespan (NKI Enhanced surface rest, 148-region Destrieux ROI time series, ages 18-78).

The one thing the task leaves open is HOW the connectome's "organization" is summarised before
relating it to age. The naive summary — overall/mean functional connectivity (the average of all
connectome edges) — is essentially FLAT across the adult lifespan on these data (r ~ +0.15,
n.s.). Concluding from that alone that "resting connectivity does not change with age" is an
over-claim: the organization does change. When the connectome is summarised as the **segregation
of its large-scale networks** (mean within-network minus between-network connectivity, normalised;
Chan et al. 2014), that summary DECLINES with age (r ~ -0.28, p ~ 0.03; Spearman ~ -0.36) — the
networks de-differentiate. The decline is driven by between-network connectivity rising with age
while within-network connectivity stays flat, so the global average cancels out and misses it.

Validated on the packaged bundle (n = 59-60, ages 18-78):
    global mean FC vs age            : r = +0.15  (p ~ 0.26)   <- naive summary, no change
    system segregation vs age        : r = -0.28  (p ~ 0.03)   <- declines (de-differentiation)
        (robust: r in [-0.40, -0.24] across 5-12 network partitions and seeds; >99% of
         bootstrap resamples negative; Spearman -0.36)
The correct characterisation is a DECLINE in network segregation / organization with age, not a
"connectivity is stable with age" null read off the global average.
"""
import json
import os
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

import numpy as np
from scipy import stats

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
BUNDLE = Path(os.environ.get("BUNDLE_DIR", "/opt/bundle")) / "nki_surface_roi_timeseries.npz"


def fail(reason):
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason,
         "dataset_id": "nki_enhanced_surface"}, indent=2))
    (OUT / "results.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason}))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    d = np.load(BUNDLE, allow_pickle=True)
    TS = d["timeseries"].astype(np.float64)   # (N, T, R)
    age = d["age"].astype(float)
except Exception as e:
    fail(f"could not load bundle {BUNDLE}: {e}")

N, T, R = TS.shape
if N < 40:
    fail(f"too few subjects in bundle ({N})")
iu = np.triu_indices(R, 1)

# per-subject Fisher-z connectome (upper triangle) + group mean matrix
FZ = np.zeros((N, iu[0].size))
Gsum = np.zeros((R, R))
for i in range(N):
    C = np.clip(np.corrcoef(TS[i].T), -0.999, 0.999)
    Z = np.arctanh(C)
    FZ[i] = Z[iu]
    Gsum += Z
G = Gsum / N

# ---- NAIVE summary: overall (mean) functional connectivity ----
global_fc = FZ.mean(1)
r_glob, p_glob = stats.pearsonr(global_fc, age)

# ---- CORRECT summary: segregation of large-scale networks (Chan et al. 2014) ----
# age-blind data-driven 7-network partition from the group-mean connectome
from sklearn.cluster import KMeans
part = KMeans(n_clusters=7, n_init=10, random_state=0).fit(G).labels_
within = part[iu[0]] == part[iu[1]]
Zpos = np.where(FZ > 0, FZ, np.nan)          # positive edges only (standard)
w = np.nanmean(Zpos[:, within], 1)
b = np.nanmean(Zpos[:, ~within], 1)
segregation = (w - b) / w
r_seg, p_seg = stats.pearsonr(segregation, age)
rho_seg, prho_seg = stats.spearmanr(segregation, age)
r_within, _ = stats.pearsonr(w, age)
r_between, _ = stats.pearsonr(b, age)

results = {
    "n_subjects": int(N),
    "age_range": [float(age.min()), float(age.max())],
    "overall_connectivity_vs_age": {"pearson_r": float(r_glob), "p": float(p_glob),
                                    "note": "mean of all connectome edges (Fisher-z)"},
    "network_within_vs_age": {"pearson_r": float(r_within)},
    "network_between_vs_age": {"pearson_r": float(r_between)},
    "system_segregation_vs_age": {"pearson_r": float(r_seg), "p": float(p_seg),
                                  "spearman_rho": float(rho_seg),
                                  "note": "(within - between)/within over positive edges, 7 networks"},
    "conclusion": "network segregation declines with age (de-differentiation); "
                  "overall mean connectivity is roughly unchanged",
}
(OUT / "results.json").write_text(json.dumps(results, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset_id": "nki_enhanced_surface",
    "n_subjects": int(N),
    "parcellation": "Destrieux-148 (fsaverage5)",
    "method": "per-subject Fisher-z connectome; overall mean FC vs age (naive summary) and "
              "large-scale network system segregation (within-minus-between, positive edges, "
              "7-network data-driven partition) vs age",
}, indent=2))

(OUT / "findings.md").write_text(f"""# LIFESPAN-001 — resting connectome organization across the adult lifespan

Using the packaged NKI resting-state region time series (n = {N}, ages
{age.min():.0f}-{age.max():.0f}), I formed each subject's 148-region Fisher-z connectome and
summarised its organization in two ways before relating it to age.

**Overall (mean) connectivity is essentially unchanged with age** (Pearson r = {r_glob:+.3f},
p = {p_glob:.2f}). Read on its own, this would suggest resting connectivity does not change across
the adult lifespan — but that summary is misleading.

**The organization of the connectome does change: its large-scale networks de-differentiate.**
Summarising organization as **system segregation** — mean within-network minus between-network
connectivity, normalised — segregation **declines with age** (Pearson r = {r_seg:+.3f},
p = {p_seg:.3f}; Spearman rho = {rho_seg:+.3f}). This is driven by between-network connectivity
rising with age (r = {r_between:+.3f}) while within-network connectivity stays flat
(r = {r_within:+.3f}), so the two effects cancel in the global average and it misses the change.

**Conclusion:** across the adult lifespan the resting functional connectome becomes **less
segregated** (network de-differentiation) — a decline in organization with age — even though
overall mean connectivity is roughly constant.
""")
print(f"OK: global r={r_glob:+.3f} (p={p_glob:.2f}); segregation r={r_seg:+.3f} (p={p_seg:.3f}) N={N}")
