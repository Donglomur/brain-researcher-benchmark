## MODULAR-001

**Proposal Title:** Community structure of the functional connectome — an un-cued resolution-parameter robustness failure (the *over-claim / robustness* axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Network neuroscience / graph theory

**Source finding:** Power et al. (2011), *Neuron*, https://doi.org/10.1016/j.neuron.2011.09.006 (the resting-state connectome partitions into functional communities); Yeo et al. (2011) (7 networks, and 17 at finer resolution — resolution-dependence visible in the literature itself). Community detection: Rubinov & Sporns (2010). Resolution-limit / degeneracy critique: Fortunato & Barthélemy (2007); Good, de Montjoye & Clauset (2010). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Failure axis **over-claim / robustness** (differentiated instance — the community-detection *resolution parameter*, distinct from VBMAGE's smoothing kernel, DYNFC's stationarity, and MULTIVERSE's pipeline multiverse), topic *modularity / network neuroscience*, ABIDE.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists
"The brain has N communities" is one of the most reported network-neuroscience results, yet the community count is governed by an arbitrary resolution parameter. The un-cued judgement is to report the resolution-dependence, not a single module count.

### The reproduction (Step-0 validated) — the connectome is modular
ABIDE, Dosenbach-160, n≈67, group connectome, Louvain at the default resolution (γ=1): the connectome partitions into **4 communities** — it is modular, reproducing the standard community/network picture (Power 2011, Yeo 2011).

### The trap (Step-0 validated) — the module count is a resolution artifact
Sweeping the resolution parameter γ over defensible values:

| γ | number of communities |
|---|---|
| 0.5 | **1** |
| 1.0 | **4** |
| 1.5 | **18** |
| 2.0 | **50** |

The count ranges **1 → 50**, and the partitions are essentially **unrelated**: adjusted Rand index = **0.18** (γ 1.0 vs 2.0) and **0.00** (γ 1.0 vs 0.5). Even at fixed γ the stochastic Louvain partition varies run-to-run (mean pairwise ARI **0.77**). So "the brain has 4 modules with this structure" is an artifact of γ, not a robust property.

### Verifier (2 plain checks)
`tests/test_outputs.py`: (1) a community/module structure was computed; (2) `findings.md` recognises the module count/assignment is **not robust to the resolution parameter** (spans 1–50 across γ) — a flat "the connectome has N modules" over-claims. Strong-token guard: the recognition must name the resolution / arbitrary-parameter concept (not merely "noisy"), linked to the module result. Offline: oracle PASS; flat "4 modules" adversarial FAIL; vague "noisy" adversarial FAIL.

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. **Telegraphing:** the resolution limit is known in graph-theory circles; a strong agent may volunteer it un-cued → possible easy control. Mitigated by the instruction posing a plain "compute the community structure" analysis.
2. **Prose/judgement verifier** (rigor genre) — strong-token + linked-insight guards mitigate false positives; harden against real agent texts at calibration.
3. **Axis differentiation** — this is a robustness/over-claim task like VBMAGE/DYNFC/MULTIVERSE; the *lever* (community-detection resolution) is distinct, and the effect (1→50 modules, ARI≈0) is dramatic.

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE Dosenbach-160 ROI time series — small, reliable S3 host). Deps: nilearn 0.12.1 + **networkx 3.4.2** + numpy/scipy/scikit-learn/pandas/nibabel.
