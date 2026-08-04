## CAUSAL-001

**Proposal Title:** Reproduce Granger-causal directed connectivity (Roebroeck 2005) — un-cued unreliability of fMRI causal direction (the *correlation→causation* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Effective / directed connectivity

**Source finding:** Roebroeck, Formisano & Goebel (2005), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2004.09.036 — Granger causality applied to fMRI maps *directed influence* between regions (the foundational directed-connectivity claim). Critique: Smith et al. (2011), https://doi.org/10.1016/j.neuroimage.2010.08.063 (connection *presence* is recoverable from fMRI, *direction* is not); Ramsey et al. (2010). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Failure axis **correlation→causation** (B·cause), rigor genre (test the directed-influence claim, find its direction unreliable — GRADIENT-style), ABIDE.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### The reproduction (Step-0 validated) — directed influences ARE estimated
Anchored the shipped way. Lag-based Granger-style estimation runs on the top-connected ABIDE region pairs and yields **dominant directed influences** ("region A leads region B") — exactly what a Roebroeck-style directed-connectivity analysis reports, and what a naive analysis would present as the causal architecture.

### The trap (Step-0 validated; `scratchpad/causal_step0.py`) — the directions are unreliable
ABIDE dosenbach160, n~60, lag-based directed influence among the top-connected pairs:
ABIDE dosenbach160, n~60, lag-based directed influence among the top-connected pairs:

| measure | value |
|---|---|
| within-subject split-half **direction** agreement | **~0.57–0.58** (chance 0.50) |

The inferred *direction* of influence barely replicates within the same subject (near chance) — far below what is needed to assert directionality. fMRI recovers connection *presence* well but *direction* poorly (regional hemodynamic-lag differences confound lag-based causality).

### Verifier (2 plain checks) + local calibration
`tests/test_outputs.py`: (1) directed influences were computed; (2) `findings.md` recognises the inferred **direction is unreliable** (does not replicate / near chance / fMRI cannot recover direction) — a flat "region A drives region B" over-claims causal direction. Linked-insight + a `strong`-token guard (unreliable / replicate / chance / hemodynamic / cannot establish).

Local calibration (`scratchpad/validate_causal.py`):

| output | computed | recognises_unreliable |
|---|---|---|
| **oracle** | PASS | PASS — reward 1.0 |
| correct-terse (direction ~chance, unreliable) | PASS | PASS |
| flat "A drives B" | PASS | **FAIL** |
| vague "patterns are complex" | PASS | **FAIL** |
| broken (no directed result) | **FAIL** | — |

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. **Telegraphing:** Smith 2011 is a landmark; a strong agent may already distrust fMRI directionality → possible easy control. The gate decides.
2. **Prose/judgement verifier** (rigor genre) — linked-insight + strong-token guards mitigate false positives.
3. **Modest signal:** 0.58 is near chance but significantly above (n=60, SE≈0.025) — so there is a *sliver* of real directional signal; the honest conclusion is "unreliable / near chance," which the oracle states as such (mirrors DYNFC's "largely, not entirely" nuance).

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE dosenbach160 ROI time series — small, reliable S3 host). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
