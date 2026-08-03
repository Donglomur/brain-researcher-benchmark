## MULTIVERSE-001

**Proposal Title:** Age vs resting-state connectivity (ABIDE) — an un-cued specification-curve instability (the *point-estimate / no-multiverse* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Developmental / lifespan resting-state connectivity

**Source finding:** Di Martino et al. (2014), *Molecular Psychiatry* (ABIDE, wide age range). Multiverse / analytic-variability references: Steegen et al. (2016, multiverse analysis); Botvinik-Nezer et al. (2020, NARPS). Data: `nilearn.datasets.fetch_abide_pcp` (cpac).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Opens a **new failure axis** — **point-estimate / no-multiverse** (A·robustness) — on ABIDE.

**Axis honesty:** distinct from the shipped robustness tasks. GRADIENT (over-claim) asserts one *identity*; SOCIALBRAIN (confident-refutation) turns on one *GSR lever*. Here the honest behaviour is to report the **whole specification curve** — and the effect is flipped by **two** independent choices (atlas AND GSR), not one, so it is a genuine multiverse, not a single-lever story.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### The trap (Step-0 validated; `scratchpad/multiverse_step0.py`)
ABIDE cpac, n~200, age vs mean |connectivity|, across atlas × GSR × band-pass (8 pipelines):

| pipeline | r | p |
|---|---|---|
| cc200, no-GSR, no-BP | **+0.03** | 0.68 (null) |
| dosenbach160, no-GSR, no-BP | −0.35 | <0.001 (atlas alone flips it) |
| cc200, GSR, no-BP | −0.44 | <0.001 (GSR flips it) |
| dosenbach160, GSR, no-BP | **−0.53** | <0.001 |

The age–connectivity correlation ranges from **null to r=−0.53**, the sign flips, and only ~75% of specifications are significant. No single point estimate is defensible.

### Verifier (2 plain checks) + local calibration
`tests/test_outputs.py`: (1) an age–connectivity correlation was computed; (2) the submission either reports a **multiverse (≥4 specifications)** OR `findings.md` recognises the effect is **choice-dependent** (ranges/flips across atlas/GSR/pipeline) — a single point estimate with a flat yes/no fails. Linked-insight guard: variation words must tie to the *result*, not merely name pipeline components.

Local calibration (`scratchpad/validate_multiverse.py`):

| output | effect_computed | choice_dependence |
|---|---|---|
| **oracle** (8-spec curve) | PASS | PASS — reward 1.0 |
| prose recognises choice-dependence | PASS | PASS |
| structured multiverse (≥4 specs) | PASS | PASS |
| single flat "r=−0.44, decreases with age" | PASS | **FAIL** |
| single flat "r=0.03, no age effect" | PASS | **FAIL** |
| broken (no correlation) | **FAIL** | — |

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. Telegraphing: GRADIENT showed frontier agents do *not* volunteer robustness-across-choices un-cued → plausibly hard, but the gate decides.
2. **Prose/structured verifier** — the structured branch (≥4 specs) is clean; the prose branch grades an insight (linked-insight guard mitigates false positives).
3. Partly leans on GSR (SOCIALBRAIN's lever) — mitigated because the **atlas choice alone** also flips it (cc200 r≈0 vs dosenbach160 r=−0.35 with no GSR).

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 + dosenbach160 ROI time series — small, reliable S3 host; oracle runs 8 pipelines × 2 atlases, timeout 5400 s). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
