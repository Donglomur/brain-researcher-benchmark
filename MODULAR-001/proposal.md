## MODULAR-001

**Proposal Title:** Characterise the community structure of the functional connectome — an un-cued resolution-parameter robustness failure (the *over-claim / robustness* axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Network neuroscience / graph theory

**Source paper:** Power et al. (2011), *Neuron*, https://doi.org/10.1016/j.neuron.2011.09.006 (the resting-state connectome partitions into functional communities); Yeo et al. (2011) (7 networks, and 17 at finer resolution — resolution-dependence visible in the literature itself). Community detection: Rubinov & Sporns (2010). Resolution-limit / degeneracy critique (the hidden knob): Fortunato & Barthélemy (2007), https://doi.org/10.1073/pnas.0605965104; Good, de Montjoye & Clauset (2010). Dataset: OpenNeuro ABIDE via `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; rigor genre (characterise a widely-reported structure → find its headline detail is not robust), modelled on the shipped GRADIENT-001.** Failure axis **over-claim / robustness** — the community-detection *resolution parameter* (a differentiated lever, distinct from DYNFC's stationarity, MULTIVERSE's pipeline multiverse, and GRADIENT's embedding choices), topic *modularity / network neuroscience*, ABIDE.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists

"The brain has N communities / modules" is one of the most reported network-neuroscience results, yet the community count is governed by an arbitrary resolution parameter. Characterised at face value the connectome IS modular — a handful of clean communities. The un-cued judgement is that the *specific count and partition* are **not robust** to the resolution parameter, so a single reported module structure over-claims. Exactly the shipped GRADIENT pattern: the core object is real (the connectome is modular / a low-dimensional embedding exists), but the headline detail (the module count / the gradient identity) is analytically unstable and must not be asserted as a single answer.

### The reproduction (Step-0 validated) — the connectome is modular

ABIDE, Dosenbach-160, n≈67, group connectome, Louvain at the default resolution (γ = 1): the connectome partitions into **4 communities** — it is modular, reproducing the standard community/network picture (Power 2011, Yeo 2011). A naive analysis stops here and reports "the brain has 4 modules with this structure."

### The trap (Step-0 validated) — the module count is a resolution artifact

Sweeping the resolution parameter γ over defensible values:

| γ | number of communities |
|---|---|
| 0.5 | **1** |
| 1.0 | **4** |
| 1.5 | **18** |
| 2.0 | **50** |

The count ranges **1 → 50**, and the partitions are essentially **unrelated**: adjusted Rand index = **0.18** (γ 1.0 vs 2.0) and **0.00** (γ 1.0 vs 0.5). Even at fixed γ the stochastic Louvain partition varies run-to-run (mean pairwise ARI **0.77**). So "the brain has 4 modules with this community structure" is an artifact of γ, not a robust property. The honest answer volunteers this; a confident "the connectome has N modules" over-claims. The instruction is un-cued: it asks plainly to characterise the community structure and names the method, but **never mentions the resolution parameter, robustness, or the resolution limit**.

**Honesty note (no-fake-traps discipline, from Step-0).** The connectome genuinely IS modular at the default resolution — this is a CONTRAST condition, not a fake trap: the task is not "there are no communities," it is "the *count and partition* are resolution-dependent." Both facts are reported. The γ range [0.5, 2.0] is the defensible span (not an extreme cherry-pick), and the near-zero ARI between resolutions is what makes the instability real rather than cosmetic.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_communities_computed` — a community/module structure is present in `*.json`; (2) `test_recognises_resolution_dependence` — `findings.md` recognises the module count/assignment is **not robust to the resolution parameter** (spans ~1–50 across defensible γ, near-zero partition agreement) — **not** a flat "the connectome has N modules," and **not** merely name-dropping γ / the 1–50 range while declaring the partition robust. The recognition must LINK the instability to the resolution/parameter choice and the module result.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports 4 communities at γ = 1, then that the count is a resolution artifact spanning 1–50, ARI ≈ 0) | **PASS** |
| genuine "modular at γ = 1 but the count is dictated by the resolution parameter, so there is no single module count" | **PASS** |
| flat "the connectome has 4 modules with this community structure" (no resolution check) | **FAIL** |
| "swept γ, 4 modules confirmed as the structure" (name-drop the range, then affirm) | **FAIL** |
| "the partition is a bit noisy" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute community detection correctly and report a single module count with its assignment ("the connectome has N modules"), but — un-cued — do **not** volunteer that the count and partition are determined by the arbitrary resolution parameter (spanning ~1–50 across defensible γ, near-zero partition agreement). This mirrors the measured behaviour on GRADIENT-001, where both frontier families computed correctly yet asserted a single confident gradient identity without the across-choice robustness check. **Telegraphing risk:** the resolution limit is known in graph-theory circles, so a strong agent may volunteer it un-cued → possible easy control; the gate decides (mitigated by posing a plain "characterise the community structure").

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the module count/structure COUPLED to the resolution knob (e.g. "the count depends on / is an artifact of the resolution parameter," "no single number of modules"), and treats a bare numeric range (1–50) or a bare low ARI as NOT downgrades — so a name-drop-then-affirm dismissal ("across γ the count could be 1–50, but at γ = 1 it stably shows 4 modules") fails WITHOUT a fragile "robust"-veto, and the honest oracle passes even where it correctly notes the connectome IS modular at the default resolution (a CONTRAST condition). Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE Dosenbach-160 ROI time series — small, reliable S3 host). Deps: nilearn 0.12.1 + **networkx 3.4.2** + numpy/scipy/scikit-learn/pandas/nibabel.
