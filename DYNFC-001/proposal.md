## DYNFC-001

**Proposal Title:** Reproduce dynamic functional connectivity (Allen 2014 / Hutchison 2013) — an un-cued stationarity artifact (the *over-claim / robustness* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Time-varying (dynamic) functional connectivity

**Source finding:** Allen et al. (2014), *Cereb Cortex*, https://doi.org/10.1093/cercor/bhs352 ("Tracking whole-brain connectivity dynamics in the resting state"); Hutchison et al. (2013), *NeuroImage* — resting-state FC is not static: sliding-window FC fluctuates and recurs into "dynamic connectivity states." Stationarity critique: Laumann et al. (2017), Hindriks et al. (2016), Liégeois et al. (2017). Data: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Failure axis **over-claim / robustness** (differentiated 2nd instance vs GRADIENT), topic *dynamic FC*, ABIDE.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists
Anchored the shipped way — **reproduce the primary finding, then reveal its hidden trap.** Sliding-window "dynamic connectivity" is one of the most-cited resting-state phenomena; the un-cued judgement is that the fluctuations do not exceed a proper stationary null, so the "time-varying states" are largely a sampling artifact.

### The reproduction (Step-0 validated) — the Allen/Hutchison phenomenology holds
ABIDE, Dosenbach-160, n=60: sliding-window FC shows substantial window-to-window variability (mean edge SD **0.30** at 30-TR windows) — exactly the "dynamic connectivity" phenomenology Allen (2014) and Hutchison (2013) reported. A naive analysis stops here and declares time-varying connectivity states.

### The trap (Step-0 validated) — a PROPER stationary null explains it
Compared against a **multivariate phase-randomised surrogate** (preserves each ROI's power spectrum *and* the cross-spectrum → a stationary linear process matched to the data's spectral content):

| window | observed edge-SD | stationary null | ratio | excess |
|---|---|---|---|---|
| 22 TR | 0.365 | 0.355 | **1.03×** | +3% |
| 30 TR | 0.300 | 0.289 | **1.04×** | +4% |
| 44 TR | 0.232 | 0.221 | **1.05×** | +5% |

Observed variability is ~1.04× the null and the ratio is **invariant to window length** — the fluctuations are what a stationary process produces by sampling alone.

**Honesty note (no-fake-traps discipline, from Step-0).** The *null model matters*, and I checked it rather than inheriting the original. A **white-noise** Gaussian null with only the static covariance (the previous version of this oracle) is **invalid**: it ignores autocorrelation, so its observed/null ratio is window-length-dependent (I measured 1.14× at 30 TR but 1.92× at 22 TR — an artifact of the window choice, not of stationarity). The **phase-randomised** null preserves the power spectrum and gives a stable ~1.03–1.05× at every window length — reproducing Laumann's (2017) actual result. The task now uses the correct null; this is a genuine soundness fix over the trap-first draft.

### Verifier (2 plain checks)
`tests/test_outputs.py`: (1) a sliding-window / time-resolved variability measure is computed; (2) `findings.md` recognises the observed dynamics barely exceed (are largely explained by) a stationary null — a confident "dynamic states are real" over-claims. Linked-insight guard: the stationarity/surrogate insight must be tied to the dynamics, not a passing "noise" mention. Offline: oracle PASS; confident-states adversarial FAIL.

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. Telegraphing: the instruction mentions "recurring states" as an example (Allen's framing, not the trap) — un-cued about the null.
2. **Prose/judgement verifier** (rigor genre) — linked-insight guard mitigates false positives; harden against real agent texts at calibration.

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE Dosenbach-160 ROI time series — small, reliable S3 host). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel (phase randomisation via numpy FFT — no extra deps).
