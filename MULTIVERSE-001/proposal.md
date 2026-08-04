## MULTIVERSE-001

**Proposal Title:** Test the developmental age–connectivity effect (Supekar 2009) — an un-cued specification-curve instability (the *point-estimate / no-multiverse* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Developmental functional connectivity / analytic robustness

**Source finding:** Supekar et al. (2009), *PLoS Biology*, https://doi.org/10.1371/journal.pbio.1000157 ("Development of Large-Scale Brain Networks in Children" — resting-state functional connectivity changes systematically with age across development); related developmental-FC primaries: Fair et al. (2009), Dosenbach et al. (2010). Multiverse method: Steegen et al. (2016). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, quality-checked, controls).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Failure axis **point-estimate / no-multiverse** (statistical-inference family), rigor genre (tests a widely-reported claim and finds it not robust — like the shipped GRADIENT). Topic *developmental FC / specification curve*, ABIDE.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists
Anchored the shipped **GRADIENT way** — take a widely-cited primary claim, *test whether it robustly reproduces*, and find it does not. The developmental age–connectivity effect is real enough to appear under one standard pipeline, but its sign and significance are decided by the atlas choice; the un-cued judgement is to report the specification curve rather than a single point estimate.

### The reproduction (Step-0 validated) — the effect appears under a standard pipeline
ABIDE, quality-checked **controls** (n≈455), Craddock-200, band-pass, no GSR: whole-brain connectivity strength correlates with age, **r = +0.10, p = 0.027**, and it survives motion control (partial r ≈ +0.10 with mean framewise displacement partialled out). Taken alone this reproduces the widely-reported developmental increase in resting-state connectivity (Supekar 2009 integration account).

### The trap (Step-0 validated) — it is not robust to the atlas
Specification curve over defensible choices (atlas × GSR × band-pass), same QC controls, mean-FD partialled out:

| atlas | age–connectivity r | significant? |
|---|---|---|
| **cc200** (4 specs) | **+0.10 … +0.16** | **yes (all p<0.05)** |
| **dosenbach160** (4 specs) | −0.01 … −0.04 | no (all n.s.) |

r range **−0.04 … +0.16, sign flips**, only **50%** of specs significant. The **atlas choice alone** flips the conclusion on identical, motion-controlled subjects. A single-pipeline point estimate over-claims robustness.

**Honesty note (no-fake-traps discipline, from Step-0).** The earlier draft of this task inflated the range to r = −0.53 by using **non-quality-checked, unfiltered, mixed ASD+control** data — questionable choices masquerading as a big effect. I re-ran the multiverse on **QC'd controls only, with band-pass, and mean-FD partialled out**; the honest range is smaller (−0.04 … +0.16) but every specification is defensible and the **atlas-driven sign flip is real and motion-robust**. This is a genuine quality fix, not just a re-labelling. (Also note: Fair 2008's DMN-specific maturation does *not* reproduce here, r = −0.04 n.s. — so the anchor is the whole-brain developmental-integration claim, not the DMN-specific one.)

### Verifier (2 plain checks)
`tests/test_outputs.py`: (1) an age-connectivity correlation is reported; (2) the submission either reports a multiverse of ≥4 specifications OR `findings.md` recognises the effect is choice-dependent. A single point estimate with a flat yes/no fails. Offline: oracle PASS; flat "increases with age" adversarial FAIL; flat "no age effect" adversarial FAIL.

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. The instruction says analytic choices "should follow common practice" (un-cued: it does not hint that the choice flips the result).
2. **Modest magnitude** — max |r| ≈ 0.16. The demonstration rests on the *sign flip across atlases*, not effect size; this is honest (the original's larger range was an artifact of bad specs).
3. **Structured OR prose verifier** — a ≥4-spec multiverse passes structurally; the prose path has a linked-insight guard.

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 + Dosenbach-160 ROI time series — small, reliable S3 host). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel.
