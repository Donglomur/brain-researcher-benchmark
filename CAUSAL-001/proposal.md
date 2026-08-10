## CAUSAL-001

**Proposal Title:** Reproduce Granger-causal directed connectivity (Roebroeck 2005) — an un-cued unreliability of fMRI causal direction (the *correlation→causation* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Effective / directed connectivity

**Source paper:** Roebroeck, Formisano & Goebel (2005), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2004.09.036 ("Mapping directed influence over the brain using Granger causality and fMRI") — the foundational directed-connectivity claim that lag-based Granger causality on fMRI maps directed influence between regions. Direction critique: Smith et al. (2011), https://doi.org/10.1016/j.neuroimage.2010.08.063 (fMRI recovers connection *presence* well but *direction* poorly); Ramsey et al. (2010). Dataset: OpenNeuro ABIDE via `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001 / DYNFC-001.** Failure axis **correlation→causation** (B·cause), on directed connectivity — a differentiated instance vs the robustness/over-claim tasks.

### Why this exists

Directed ("effective") connectivity is one of the most-cited things people *do* with resting fMRI: run a lag-based Granger-style estimator and report "region A drives region B." Reproduced at face value it looks compelling — the estimator returns clean, dominant directed influences. The un-cued judgement is that the inferred *direction* barely replicates within the same subject and is near chance, so a directed/causal claim is unwarranted (regional hemodynamic-lag differences confound lag-based causality; Smith 2011). Exactly the shipped pattern: the agent is asked to reproduce a famous result, computes it correctly, and fails only if it does not *volunteer* the reliability check the instruction never mentions.

### The reproduction (Step-0 validated) — directed influences ARE estimated

ABIDE, Dosenbach-160, n≈60, lag-based directed influence among the top-connected region pairs: the estimator yields **dominant directed influences** ("region A leads region B") — exactly what a Roebroeck-style directed-connectivity analysis reports, and what a naive analysis would present as the causal architecture of the resting network. A naive analysis stops here and reports which region drives which.

### The trap (Step-0 validated; `scratchpad/causal_step0.py`) — the directions are unreliable

ABIDE dosenbach160, n≈60, lag-based directed influence among the top-connected pairs:

| measure | value |
|---|---|
| within-subject split-half **direction** agreement | **~0.57–0.58** (chance 0.50) |

The inferred *direction* of influence barely replicates within the same subject — near chance, far below what is needed to assert directionality. fMRI recovers connection *presence* well but *direction* poorly, because inter-regional **hemodynamic-lag** differences confound lag-based causality (Smith 2011). The honest answer volunteers this; a confident "region A drives region B" over-claims causal direction from correlational fMRI. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions reliability, replication, a split-half, chance, or hemodynamic lag**.

**Honesty note (no-fake-traps discipline, from Step-0).** 0.58 is *near* chance but significantly above it (n≈60, SE≈0.025) — there is a *sliver* of real directional signal, not pure noise. The honest conclusion is therefore "unreliable / near chance," which the oracle states as such (mirroring DYNFC's "largely, not entirely" nuance), rather than "there is zero directional information." The reliability metric was measured, not assumed.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_directed_connectivity_computed` — a directed-influence result (a `from`→`to` / directional structure) is present in `*.json`; (2) `test_recognises_direction_unreliable` — `findings.md` recognises the inferred **direction is unreliable** (does not replicate / near chance / fMRI cannot recover direction / should be treated as undirected) — **not** a flat "region A drives region B", and **not** conceding "direction is near chance" and then reporting A→B anyway. The recognition must LINK the unreliability to the direction/causal claim.

**Discrimination (validated locally; `scratchpad/validate_causal.py`):**

| solution | verdict |
|---|---|
| reference (estimates directed influences, then reports the direction barely replicates within-subject → unreliable) | **PASS** |
| correct-terse (direction ~chance, unreliable) | **PASS** |
| flat "region A drives region B" (no reliability) | **FAIL** |
| "direction is at chance, but A drives B, reported with confidence" (concede-then-affirm) | **FAIL** |
| vague "the patterns are complex" (unlinked hedge) | **FAIL** |
| broken (no directed result) | **FAIL** (computed) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the lag-based directed influences correctly and report "region A drives region B" as the causal architecture, but — un-cued — do **not** volunteer the within-subject split-half reliability check that shows the inferred direction barely replicates. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check. **Telegraphing risk:** Smith 2011 is a landmark; a strong agent may already distrust fMRI directionality → possible easy control. The gate decides.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the directional/causal claim (e.g. "direction does not replicate," "cannot establish which region drives which," "treat as undirected"), and rejects a concede-then-affirm dismissal ("direction is near chance, but A unmistakably drives B") — the near-chance concession alone is deliberately NOT treated as a downgrade, so it will not false-pass an agent that merely mentions the statistic. It also lets the oracle pass when it notes connection *presence* is recovered well while *direction* is not. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE dosenbach160 ROI time series — small, reliable S3 host; downloads then cached). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel (lag-1 directionality via numpy — no extra deps). Timeouts generous (directed-influence estimation over ~60 subjects).
