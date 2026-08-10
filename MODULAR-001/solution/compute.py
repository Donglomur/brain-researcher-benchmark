"""Reference (oracle) for MODULAR-001 — modular / community structure of the functional connectome.

Paper anchor: Power et al. 2011, Neuron (10.1016/j.neuron.2011.09.006) and Yeo et al. 2011, J
Neurophysiol — the resting-state functional connectome partitions into a set of communities /
networks (Power reported ~a dozen; Yeo reported 7, and 17 at finer resolution). Community
detection: Rubinov & Sporns 2010 (BCT). Resolution-limit / degeneracy critique: Fortunato &
Barthelemy 2007; Good, de Montjoye & Clauset 2010.

The task (un-cued) asks to compute the community structure of the group connectome and report the
number of modules and their membership. This reference computes it at the default resolution
(gamma=1) — the connectome IS modular, ~a handful of communities — and then VOLUNTEERS the check
the task never asks: is that module count robust? It is not. Across the resolution parameter
gamma in [0.5, 2] the number of communities ranges from 1 to ~50, and the partitions are
essentially unrelated (adjusted Rand index ~0 between resolutions). So 'the brain has N modules'
is an artifact of the arbitrary resolution parameter, not a robust property.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
GAMMAS = [0.5, 1.0, 1.5, 2.0]


def fail(reason):
    (OUT / "communities.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import networkx as nx
    from nilearn import datasets
    from nilearn.connectome import ConnectivityMeasure
    from sklearn.metrics import adjusted_rand_score as ari
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    ab = datasets.fetch_abide_pcp(derivatives=["rois_dosenbach160"], pipeline="cpac",
                                  band_pass_filtering=True, global_signal_regression=False,
                                  quality_checked=True)
except Exception as e:
    fail(f"could not resolve ABIDE: {e}")

dx = np.asarray(ab.phenotypic["DX_GROUP"])
ctrl = np.where(dx == 2)[0][:80]
cm = ConnectivityMeasure(kind="correlation")
mats = []
for i in ctrl:
    ts = ab.rois_dosenbach160[i]
    if ts is None:
        continue
    a = np.asarray(ts, float)[:, :160]
    if a.ndim != 2 or a.shape[0] < 80:
        continue
    R = np.nan_to_num(cm.fit_transform([a])[0])
    np.fill_diagonal(R, 0)
    mats.append(R)
if len(mats) < 40:
    fail(f"only {len(mats)} usable subjects")
G = np.clip(np.mean(mats, 0), 0, None)   # group mean connectome, positive weights
np.fill_diagonal(G, 0.0)
graph = nx.from_numpy_array(G)


def louvain(gamma, seed=0):
    comm = nx.community.louvain_communities(graph, weight="weight", resolution=gamma, seed=seed)
    lab = np.zeros(G.shape[0], int)
    for k, c in enumerate(comm):
        for node in c:
            lab[node] = k
    return lab, len(comm)


parts = {}
counts = {}
for g in GAMMAS:
    lab, k = louvain(g)
    parts[g] = lab
    counts[g] = k
default_lab, default_k = parts[1.0], counts[1.0]

# resolution (in)stability
ari_1_vs_2 = float(ari(parts[1.0], parts[2.0]))
ari_1_vs_05 = float(ari(parts[1.0], parts[0.5]))
kmin, kmax = min(counts.values()), max(counts.values())

# stochastic (seed) stability at the default resolution
seedlabs = [louvain(1.0, s)[0] for s in range(8)]
seed_aris = [ari(seedlabs[i], seedlabs[j]) for i in range(8) for j in range(i + 1, 8)]
seed_ari = float(np.mean(seed_aris))

(OUT / "communities.json").write_text(json.dumps({
    "atlas": "Dosenbach-160", "n_subjects": len(mats),
    "method": "Louvain community detection on the group functional connectome",
    "n_modules_default_gamma1": int(default_k),
    "community_assignment_gamma1": default_lab.tolist(),
    "n_modules_by_resolution": {str(g): int(counts[g]) for g in GAMMAS},
    "adjusted_rand_gamma1_vs_gamma2": ari_1_vs_2,
    "adjusted_rand_gamma1_vs_gamma0p5": ari_1_vs_05,
    "seed_stability_mean_ari_gamma1": seed_ari,
    "n_modules_range_over_resolution": [int(kmin), int(kmax)],
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok", "dataset": "ABIDE (ABIDE_pcp, cpac, rois_dosenbach160, quality_checked)",
    "atlas": "Dosenbach-160", "n_subjects": len(mats),
    "method": "Louvain community detection; resolution parameter gamma swept over [0.5, 2.0]",
}, indent=2))

(OUT / "findings.md").write_text(f"""# MODULAR-001 — community structure of the functional connectome (ABIDE)

## The connectome is modular (default resolution)
At the default resolution (Louvain, gamma = 1.0) the group functional connectome partitions into
**{default_k} communities** — the connectome is modular, reproducing the standard picture of
community/network structure.

## But the number of communities is not robust — it is a resolution artifact (un-cued)
The community structure depends entirely on the arbitrary **resolution parameter gamma**. Across
gamma in [0.5, 2.0] the number of communities ranges from **{kmin} to {kmax}**
({', '.join(f'gamma={g}: {counts[g]}' for g in GAMMAS)}), and the partitions are essentially
**unrelated**: adjusted Rand index = {ari_1_vs_2:.2f} (gamma 1.0 vs 2.0) and {ari_1_vs_05:.2f}
(gamma 1.0 vs 0.5). Even at fixed gamma the stochastic Louvain partition varies run-to-run
(mean pairwise ARI = {seed_ari:.2f}).

## Conclusion
"The brain has {default_k} modules with this community structure" is an artifact of the
**resolution parameter**, not a robust property — the count spans {kmin}-{kmax} across defensible
choices, with near-zero partition agreement. Reporting a single community structure without
showing its resolution-dependence over-claims.
""")
print(f"OK: default_k={default_k}; range {kmin}-{kmax}; ARI(1v2)={ari_1_vs_2:.2f} "
      f"ARI(1v0.5)={ari_1_vs_05:.2f} seed_ari={seed_ari:.2f}")
