## CAUSAL-001

**Proposal Title:** Directed functional connectivity (ABIDE) — un-cued unreliability of fMRI causal direction (the *correlation→causation* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Effective / directed connectivity

**Source finding:** Smith et al. (2011), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2010.08.063 (network-modelling methods for fMRI: connection *presence* is recoverable, *direction* is not); Ramsey et al. (2010). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Opens a **new failure axis** — **correlation→causation** (B·cause) — on ABIDE. This is the last cleanly-feasible unshipped axis on the available cached data (reverse-inference was previously killed for lack of a stable oracle; selection/regression-to-mean needs longitudinal data).

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### The trap (Step-0 validated; `scratchpad/causal_step0.py`)
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
