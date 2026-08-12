## EFFCONN-001

**Proposal Title:** Reproduce Granger-causal directed connectivity (Roebroeck 2005) — an un-cued unreliability of fMRI causal direction (the *correlation→causation* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Effective / directed connectivity

**Source paper:** Roebroeck, Formisano & Goebel (2005), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2004.09.036 ("Mapping directed influence over the brain using Granger causality and fMRI") — the foundational directed-connectivity claim that lag-based Granger causality on fMRI maps directed influence between regions. Direction critique (the un-cued axis): Smith et al. (2011), https://doi.org/10.1016/j.neuroimage.2010.08.063 (fMRI recovers connection *presence* well but *direction* poorly); Ramsey et al. (2010). Dataset: OpenNeuro ABIDE via `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160), packaged offline.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001 / TOPEDGES-001 (route-b offline).** Failure axis **correlation→causation** (B·cause), on directed connectivity — a differentiated instance vs the robustness/over-claim tasks.

### Why this exists

Directed ("effective") connectivity is one of the most-cited things people *do* with resting fMRI: run a Granger-style estimator and report "region A drives region B." Reproduced at face value it looks compelling — a proper bivariate VAR(1) Granger test returns clean, group-consistent, highly-significant dominant directed influences. The un-cued judgement is that the inferred *direction* barely replicates within the same subject and is near chance, so a directed/causal claim is unwarranted (regional hemodynamic-lag differences confound lag-based causality; Smith 2011). Exactly the shipped pattern: the agent is asked to reproduce a famous result, computes it correctly, and fails only if it does not *volunteer* the reliability check the instruction never mentions.

### Repair applied (validity standard, maintainer #10)

The earlier draft computed a raw lag cross-product and labelled it "causal/Granger." This rebuild implements the **valid VAR/Granger** option: a real bivariate first-order **vector-autoregressive** model per region pair, with an **F-test on the lagged cross-term** (log-ratio of restricted vs full residual variance) giving the directed Granger influence in each direction; the net asymmetry is aggregated across subjects. The measure is genuinely Granger causality, not a mislabelled cross-product.

### The reproduction and the trap (validated) — held privately

The validated numbers (n, the within-subject split-half **direction** reliability vs chance, the **presence** reliability contrast, the group-level Granger significance, and the oracle receipt) are in the **private, git-ignored `calibration.md`** (rule 4: agents have internet-adjacent access and the repo is public). In brief: a proper VAR(1) Granger yields group-consistent, highly-significant dominant directed influences (the naive result), but the SAME inferred direction barely replicates across a within-subject split-half — essentially at chance — while connection *presence* replicates well. The instruction is un-cued (it names the reproduction and the Granger method in full, but **never mentions reliability, replication, a split-half, chance, or hemodynamic lag**).

**Honesty note (no-fake-traps discipline).** The direction reliability is *near* chance but a one-sample test detects a barely-significant sliver above it — there is a whisper of real directional signal, not pure noise. The honest conclusion is therefore "unreliable / near chance" (mirroring DYNFC's "largely, not entirely" nuance), which the oracle states as such, rather than "there is zero directional information." The reliability metric was measured, not assumed.

### Data (route-b offline)

Network-free packaged bundle `data/dos160_causal.npz` (built by `data/build_dos160_causal.py` from the git-ignored shared bundle): an object array of 250 per-subject Dosenbach-160 ROI **timeseries** (each T×160, float16) plus `dx`. The raw timeseries are shipped (not a precomputed connectome) because the reliability check needs to fit a VAR and split each subject's run. `allow_internet=false`; `compute.py` reads only the local npz.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_directed_connectivity_computed` — validates the actual DATA: a set of directed influences with real Dosenbach-160 ROI pairs (0..159, from≠to) and finite Granger scores, a sane subject count, the per-pair table, and — where a direction reliability is reported — that it is genuinely **near chance** (a claimed-reliable direction fails). Empty/fabricated fail. (2) `test_recognises_direction_unreliable` — `findings.md` recognises the inferred **direction is unreliable** (does not replicate / near chance / fMRI cannot recover direction / should be treated as undirected) — **not** a flat "region A drives region B", and **not** conceding "direction is near chance" then reporting A→B anyway. The recognition must LINK the unreliability to the direction/causal claim. Negation-aware, downgrade-driven helper (same family as GMATROPHY/TOPEDGES).

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (estimates VAR(1) Granger influences, then reports the direction barely replicates within-subject → unreliable) | **PASS** |
| correct-terse (direction ~chance, unreliable) | **PASS** |
| flat "region A drives region B" (real Granger numbers, no reliability) | **FAIL** (recognition) |
| "direction is at chance, but A drives B, reported with confidence" (concede-then-affirm) | **FAIL** (recognition) |
| fabricated (fake ROI pairs, or a claimed-reliable ~0.9 direction) | **FAIL** (data) |
| empty | **FAIL** (data) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (offline, in-container). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families fit the VAR(1) Granger correctly and report "region A drives region B" (group-consistent, significant) as the causal architecture, but — un-cued — do **not** volunteer the within-subject split-half reliability check that shows the inferred direction barely replicates. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR). **Telegraphing risk:** Smith 2011 is a landmark; a strong agent may already distrust fMRI directionality → possible easy control. The gate decides.

**Verifier-integrity note.** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the directional/causal claim (e.g. "direction does not replicate," "cannot establish which region drives which," "treat as undirected"), and rejects a concede-then-affirm dismissal ("direction is near chance, but A unmistakably drives B") without a fragile "genuine"-veto — the near-chance concession alone is deliberately NOT treated as a downgrade — while still letting the oracle pass when it notes connection *presence* is recovered well while *direction* is not. The data check independently rejects fabricated pairs and a claimed-reliable direction. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (packaged offline bundle). Deps: numpy + scipy (VAR/Granger via numpy `lstsq`, group stats via scipy — no extra deps). Oracle runs in ~6.5 s over 250 subjects; timeouts generous.
