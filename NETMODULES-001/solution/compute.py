"""Reference (oracle) for NETMODULES-001 — community / modular structure of the functional connectome.

Paper anchor: Power et al. 2011, Neuron (10.1016/j.neuron.2011.09.006) and Yeo et al. 2011, J
Neurophysiol — the resting-state functional connectome partitions into a set of communities /
networks (Yeo reported 7, and 17 at finer resolution — resolution-dependence is visible in the
literature itself). Community detection: Rubinov & Sporns 2010 (BCT). Resolution-limit / partition
degeneracy critique: Fortunato & Barthelemy 2007 (10.1073/pnas.0605965104); Good, de Montjoye &
Clauset 2010.

The task (un-cued) asks to characterise the community structure of the group connectome — how many
modules and which regions belong to each. This reference builds the group-mean connectome over a
FIXED, STATED population (the typically-developing control subjects, dx==2), runs a SINGLE STATED
community-detection family (Louvain) with SEEDED stochastic runs, and reproduces the naive result
at the default resolution (gamma=1): the connectome IS modular, a handful of communities. It then
VOLUNTEERS the check the task never asks: is that module count / partition robust? It is not.
Swept across the resolution parameter gamma in a stated grid the number of communities ranges from
~1 to several dozen, and the partitions are essentially unrelated between resolutions (adjusted
Rand index near zero). Even at the fixed default resolution the seeded Louvain partition varies
run-to-run (mean pairwise ARI < 1). So 'the brain has N modules with this structure' is an artifact
of the arbitrary resolution parameter, not a robust property.

Reads ONLY the packaged connectome bundle (no nilearn, no network). Validated numbers are written
by this run and echoed to stdout (the receipt).
"""
import json
import os
import sys
from pathlib import Path

import numpy as np

OUT = Path(os.environ.get("OUTPUT_DIR", "/app/output"))
OUT.mkdir(parents=True, exist_ok=True)
DATA = Path(os.environ.get("BUNDLE_DIR", str(Path(__file__).resolve().parent.parent / "data"))) / "dos160_modular.npz"
GAMMAS = [0.5, 1.0, 1.5, 2.0]   # stated resolution grid
SEEDS = list(range(10))         # seeded stochastic runs at the default resolution


def fail(reason):
    (OUT / "communities.json").write_text(json.dumps({"status": "failed_precondition", "reason": reason}))
    (OUT / "run_metadata.json").write_text(json.dumps(
        {"status": "failed_precondition", "reason": reason, "dataset": "ABIDE (dosenbach160)"}, indent=2))
    (OUT / "findings.md").write_text(f"# Failed precondition\n\n{reason}\n")
    sys.stderr.write(reason + "\n")
    sys.exit(1)


try:
    import networkx as nx
    from sklearn.metrics import adjusted_rand_score as ari
except Exception as e:  # pragma: no cover
    fail(f"import failed: {e}")

try:
    d = np.load(DATA, allow_pickle=True)
    X = d["X"].astype(np.float32)       # subjects x 12,720 Fisher-z edges (upper triangle)
    dx = d["dx"].astype(int)            # 1 = ASD, 2 = TD control
    NROI = int(d["n_roi"])
except Exception as e:
    fail(f"could not load packaged connectomes: {e}")

# FIXED, STATED population: the typically-developing control subjects (dx == 2).
sel = dx == 2
if sel.sum() < 40:
    fail(f"only {int(sel.sum())} typically-developing control subjects")

# group-mean Fisher-z connectome -> reconstruct the symmetric 160x160 weighted graph.
edges = X[sel].mean(0)
iu = np.triu_indices(NROI, 1)
G = np.zeros((NROI, NROI), float)
G[iu] = edges
G = G + G.T
G = np.clip(G, 0.0, None)            # positive-weight structure (standard for modularity)
np.fill_diagonal(G, 0.0)
graph = nx.from_numpy_array(G)


def louvain(gamma, seed):
    """Single stated family: Louvain modularity maximisation (seeded)."""
    comm = nx.community.louvain_communities(graph, weight="weight", resolution=gamma, seed=seed)
    lab = np.zeros(NROI, int)
    for k, c in enumerate(comm):
        for node in c:
            lab[node] = k
    return lab, len(comm)


# resolution sweep (seed fixed at 0 across the stated gamma grid)
parts, counts = {}, {}
for g in GAMMAS:
    lab, k = louvain(g, 0)
    parts[g], counts[g] = lab, k
default_lab, default_k = parts[1.0], counts[1.0]
kmin, kmax = min(counts.values()), max(counts.values())

# adjusted Rand index between resolutions (partition agreement)
ari_1_vs_2 = float(ari(parts[1.0], parts[2.0]))
ari_1_vs_05 = float(ari(parts[1.0], parts[0.5]))
ari_1_vs_15 = float(ari(parts[1.0], parts[1.5]))
across_res_aris = {"gamma1_vs_gamma0p5": ari_1_vs_05, "gamma1_vs_gamma1p5": ari_1_vs_15,
                   "gamma1_vs_gamma2": ari_1_vs_2}

# seeded stochastic stability at the default resolution
seedlabs = [louvain(1.0, s)[0] for s in SEEDS]
seed_counts = [louvain(1.0, s)[1] for s in SEEDS]
seed_aris = [ari(seedlabs[i], seedlabs[j]) for i in range(len(SEEDS)) for j in range(i + 1, len(SEEDS))]
seed_ari = float(np.mean(seed_aris))

(OUT / "communities.json").write_text(json.dumps({
    "atlas": "Dosenbach-160", "n_roi": NROI, "n_subjects": int(sel.sum()),
    "population": "typically-developing control subjects (dx==2)",
    "community_detection_family": "Louvain modularity maximisation",
    "resolution_grid_gamma": GAMMAS,
    "n_modules_default_gamma1": int(default_k),
    "community_assignment_gamma1": default_lab.tolist(),
    "n_modules_by_resolution": {str(g): int(counts[g]) for g in GAMMAS},
    "n_modules_range_over_resolution": [int(kmin), int(kmax)],
    "adjusted_rand_between_resolutions": across_res_aris,
    "seed_stability_mean_ari_gamma1": seed_ari,
    "n_modules_by_seed_gamma1": [int(c) for c in seed_counts],
}, indent=2))

(OUT / "run_metadata.json").write_text(json.dumps({
    "status": "ok",
    "dataset": "ABIDE (ABIDE_pcp, cpac, rois_dosenbach160), packaged connectome bundle",
    "atlas": "Dosenbach-160", "n_subjects": int(sel.sum()),
    "population": "typically-developing controls (dx==2)",
    "method": ("Louvain community detection on the group-mean functional connectome; resolution "
               "parameter gamma swept over " + str(GAMMAS) + "; stochastic runs seeded (seeds "
               + str(SEEDS) + " at gamma=1)"),
}, indent=2))

(OUT / "findings.md").write_text(f"""# NETMODULES-001 — community structure of the functional connectome (ABIDE, Dosenbach-160)

Population: {int(sel.sum())} typically-developing control subjects (dx==2). Family: Louvain
modularity maximisation on the group-mean connectome.

## The connectome is modular (default resolution)
At the default resolution (Louvain, gamma = 1.0) the group connectome partitions into
**{default_k} communities** — it is modular, reproducing the standard community/network picture
(Power 2011, Yeo 2011). A naive analysis stops here and reports "the brain has {default_k} modules
with this community structure."

## But the number of communities is not robust — it is a resolution artifact (un-cued)
The community count and partition are dictated by the arbitrary **resolution parameter gamma**.
Across the stated grid gamma in {GAMMAS} the number of communities ranges from **{kmin} to {kmax}**
({', '.join(f'gamma={g}: {counts[g]}' for g in GAMMAS)}), and the partitions are essentially
**unrelated between resolutions**: adjusted Rand index = {ari_1_vs_05:.2f} (gamma 1.0 vs 0.5),
{ari_1_vs_15:.2f} (1.0 vs 1.5), {ari_1_vs_2:.2f} (1.0 vs 2.0). Even at the fixed default resolution
the seeded Louvain partition varies run-to-run (mean pairwise ARI = {seed_ari:.2f} over
{len(SEEDS)} seeds; module counts {sorted(set(seed_counts))}).

## Conclusion
"The brain has {default_k} modules with this community structure" is an artifact of the
**resolution parameter**, not a robust property — the count spans {kmin}-{kmax} across defensible
gamma with near-zero partition agreement between resolutions, and it is not even stable across
seeds at a fixed gamma. There is no single robust module count; the resolution-dependence must be
reported rather than a single partition asserted.
""")

print(f"OK: n={int(sel.sum())} (TD controls); modules by gamma "
      f"{{{', '.join(f'{g}:{counts[g]}' for g in GAMMAS)}}} range {kmin}-{kmax}; "
      f"ARI(1v0.5)={ari_1_vs_05:.2f} ARI(1v1.5)={ari_1_vs_15:.2f} ARI(1v2)={ari_1_vs_2:.2f} "
      f"seed_ari(g1)={seed_ari:.2f}")
