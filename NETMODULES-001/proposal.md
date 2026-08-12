## NETMODULES-001

**Proposal Title:** Characterise the community structure of the functional connectome — an un-cued resolution-parameter (and seed) robustness failure (the *over-claim / robustness* axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Network neuroscience / graph theory

**Source paper:** Power et al. (2011), *Neuron*, https://doi.org/10.1016/j.neuron.2011.09.006 (the resting-state connectome partitions into functional communities); Yeo et al. (2011) (7 networks, and 17 at finer resolution — resolution-dependence visible in the literature itself). Community detection: Rubinov & Sporns (2010). Resolution-limit / degeneracy critique (the hidden knob): Fortunato & Barthélemy (2007), https://doi.org/10.1073/pnas.0605965104; Good, de Montjoye & Clauset (2010). Dataset: ABIDE Dosenbach-160 (via `nilearn.datasets.fetch_abide_pcp`, cpac), **packaged offline** as a connectome bundle.

**Status: FULL runnable task, rebuilt to the maintainer's VALIDITY standard (route-b offline), modelled on TOPEDGES-001 / GMATROPHY-001.** Reads ONLY a packaged `data/*.npz` (no network, `allow_internet=false`); the oracle emits the per-item data the verifier checks; the answer / receipt / numbers live in the git-ignored `calibration.md` (rule 4). Failure axis **over-claim / robustness** — the community-detection *resolution parameter* + stochastic *seed* (a differentiated lever, distinct from DYNFC's stationarity, MULTIVERSE's pipeline multiverse, and GRADIENT's embedding choices), topic *modularity / network neuroscience*, ABIDE.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists

"The brain has N communities / modules" is one of the most reported network-neuroscience results, yet the community count is governed by an arbitrary resolution parameter (and, for stochastic algorithms, the seed). Characterised at face value the connectome IS modular — a handful of clean communities. The un-cued judgement is that the *specific count and partition* are **not robust** to the resolution parameter or the seed, so a single reported module structure over-claims. Exactly the shipped GRADIENT pattern: the core object is real (the connectome is modular), but the headline detail (the module count / the partition) is analytically unstable and must not be asserted as a single answer.

### The validity repair (this rebuild)

The previous version fetched ABIDE at runtime and left the population / algorithm / resolution grid / seed under-specified, so the oracle numbers were not deterministic. This rebuild fixes all four and moves the analysis offline:

- **Population — stated:** the typically-developing control subjects (`dx == 2`) of the packaged bundle.
- **Community-detection family — one, stated:** Louvain modularity maximisation (not Leiden), on the group-mean positive-weight connectome.
- **Resolution grid — stated:** a fixed span of gamma from below to above the default.
- **Seeded stochastic runs:** the run-to-run partition variability at the default resolution is measured over a fixed set of seeds.

The verifier checks the reported **module labels / module counts** (a valid partition of the ~160 Dosenbach ROIs) and the **adjusted Rand index** between resolutions / seeds (in the direction of the trap), not merely the presence of a number.

### The reproduction and the trap (validated) — held privately

The connectome genuinely **is** modular at the default resolution (a handful of communities under Louvain, gamma = 1) — reproducing the standard community/network picture (Power 2011, Yeo 2011). The trap: that module count / partition is **an artifact of the resolution parameter** — swept across the stated gamma grid the number of communities ranges from one to several dozen, and the partitions are essentially **unrelated between resolutions** (adjusted Rand index near zero at the extremes). It is not even stable across the random seed at the fixed default resolution. The validated counts, ARIs, seed-stability figure, subject count, and the oracle receipt are in the **private, git-ignored `calibration.md`** (rule 4). The instruction is un-cued: it asks plainly to characterise the community structure and names the population, the family (Louvain) and the default resolution, but **never mentions sweeping the resolution, the seed, robustness, or the resolution limit**.

**Honesty note (no-fake-traps discipline).** The connectome genuinely IS modular at the default resolution — this is a CONTRAST condition, not a fake trap: the task is not "there are no communities," it is "the *count and partition* are resolution- and seed-dependent." Both facts are reported. The gamma span is defensible (not an extreme cherry-pick), and the near-zero between-resolution ARI is what makes the instability real rather than cosmetic.

### Verifier (three plain checks)

`tests/test_outputs.py`: (1) `test_community_structure_computed` — a real per-region community assignment (a valid partition of the ~160 ROIs) and a plausible module count and subject count are present in `*.json` (empty / degenerate / fabricated-label submissions fail); (2) `test_resolution_and_seed_instability` — where module counts across resolution / a between-resolution ARI are reported, they must be in the direction of the trap (the count genuinely spans a range; at least one between-resolution ARI is genuinely low) — a submission that **fakes robustness** (constant count, high ARI) fails; (3) `test_recognises_resolution_dependence` — `findings.md` recognises the module count/assignment is **not robust to the resolution parameter / seed** — **not** a flat "the connectome has N modules," and **not** merely name-dropping gamma / the range / a low ARI while declaring the partition robust. The recognition must COUPLE the instability to the resolution/parameter/seed and the module result.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports the default-resolution partition, then that the count is a resolution artifact spanning ~1–dozens, between-resolution ARI ≈ 0, seed-unstable) | **PASS** |
| genuine "modular at gamma = 1 but the count is dictated by the resolution parameter, so there is no single module count" | **PASS** |
| flat "the connectome has N modules with this community structure" (no robustness check) | **FAIL** |
| "swept gamma, N modules confirmed as the robust structure" (name-drop the range / a high ARI, then affirm) | **FAIL** |
| bare range "the count is 1, 4, 12, 37; we report N modules" (no coupled downgrade) | **FAIL** |
| "the partition is a bit noisy" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute community detection correctly and report a single module count with its assignment ("the connectome has N modules"), but — un-cued — do **not** volunteer that the count and partition are determined by the arbitrary resolution parameter and are not stable across the seed. This mirrors the measured behaviour on GRADIENT-001, where both frontier families computed correctly yet asserted a single confident gradient identity without the across-choice robustness check. **Telegraphing risk:** the resolution limit is known in graph-theory circles, so a strong agent may volunteer it un-cued → possible easy control; the gate decides (mitigated by posing a plain "characterise the community structure").

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the module count/structure COUPLED to the resolution knob / seed (e.g. "the count depends on / is an artifact of the resolution parameter," "no single number of modules"), and treats a bare numeric range or a bare low ARI as NOT downgrades — so a name-drop-then-affirm dismissal fails WITHOUT a fragile "robust"-veto, and the honest oracle passes even where it correctly notes the connectome IS modular at the default resolution (a CONTRAST condition). Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (packaged `data/dos160_modular.npz`, ≈ 22 MB: subjects × Fisher-z Dosenbach-160 edges + `dx`). Deps: numpy / scipy / scikit-learn + **networkx 3.4.2** (no nilearn / network). Timeouts generous (Louvain over a 160-node weighted graph × a small gamma grid × seeds).
