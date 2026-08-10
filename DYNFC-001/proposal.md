## DYNFC-001

**Proposal Title:** Reproduce the "dynamic functional connectivity" headline (Allen 2014 / Hutchison 2013) — an un-cued stationarity artifact (the *over-claim / robustness* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Time-varying (dynamic) functional connectivity

**Source paper:** Allen et al. (2014), *Cerebral Cortex*, https://doi.org/10.1093/cercor/bhs352 ("Tracking whole-brain connectivity dynamics in the resting state"); Hutchison et al. (2013), *NeuroImage*. Stationarity critique: Laumann et al. (2017), Hindriks et al. (2016), Liégeois et al. (2017). Dataset: OpenNeuro ABIDE via `nilearn.datasets.fetch_abide_pcp` (cpac, rois_dosenbach160).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001.**

### Why this exists

Sliding-window "dynamic connectivity" is one of the most-cited resting-state phenomena. Reproduced at face value it looks compelling — connectivity fluctuates window-to-window and recurs into "states." The un-cued judgement is that those fluctuations **do not exceed a proper stationary null**, so the "time-varying states" are largely a sampling artifact. Exactly the shipped pattern: the agent is asked to reproduce a famous result, computes it correctly, and fails only if it does not *volunteer* the null comparison the instruction never mentions. Failure axis **over-claim / robustness** (a differentiated 2nd instance vs GRADIENT-001, on a different topic and dataset).

### The reproduction (Step-0 validated) — the Allen/Hutchison phenomenology holds

ABIDE, Dosenbach-160, n=60, 30-TR windows (step 4): sliding-window FC shows substantial window-to-window variability — **mean edge SD 0.30** — exactly the "dynamic connectivity" phenomenology Allen (2014) / Hutchison (2013) reported. A naive analysis stops here and declares time-varying connectivity states.

### The trap (Step-0 validated) — a PROPER stationary null explains it

Compared against a **multivariate phase-randomised surrogate** (preserves each ROI's power spectrum *and* the cross-spectrum → a stationary linear process matched to the data's spectral content):

| window | observed edge-SD | stationary null | ratio | excess |
|---|---|---|---|---|
| 22 TR | 0.365 | 0.355 | **1.03×** | +3% |
| 30 TR | 0.300 | 0.289 | **1.04×** | +4% |
| 44 TR | 0.232 | 0.221 | **1.05×** | +5% |

Observed variability is ~1.04× the null and the ratio is **invariant to window length** — the fluctuations are what a stationary process produces by sampling alone (Laumann 2017). The honest answer volunteers this; a confident "dynamic states are real" over-claims. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions stationarity, a null/surrogate, or robustness**.

**Honesty note (no-fake-traps discipline, from Step-0).** The *null model matters*, and it was checked rather than inherited. A **white-noise** Gaussian null with only the static covariance is **invalid** — it ignores autocorrelation, so its observed/null ratio is window-length-dependent (measured 1.14× at 30 TR but 1.92× at 22 TR — an artifact of the window, not of stationarity). The **phase-randomised** null preserves the power spectrum and gives a stable ~1.03–1.05× at every window length, reproducing Laumann's (2017) actual result. The task uses the correct null.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_dynamics_computed` — a sliding-window / time-resolved variability measure is present in `*.json`; (2) `test_recognises_stationarity_artifact` — `findings.md` recognises the observed dynamics barely exceed (are largely explained by) a stationary null — **not** a flat "reproduces/doesn't," and **not** merely name-dropping a surrogate while affirming the dynamics are genuine. The recognition must LINK the stationarity/sampling-artifact to the dynamics.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reproduces the variability, then reports it barely exceeds a spectrum-matched stationary null) | **PASS** |
| genuine "edge-SD 0.30 but only 1.04× a phase-randomised null → sampling artifact" | **PASS** |
| flat "dynamic connectivity states are present, edge-SD 0.30" (no null) | **FAIL** |
| "ran a surrogate, dynamics confirmed genuine" (name-drop, no coupled downgrade) | **FAIL** |
| "some noise is present" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the sliding-window variability correctly and report "dynamic connectivity" as present, but — un-cued — do **not** volunteer the spectrum-matched stationary-null comparison that shows the fluctuations barely exceed chance. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the dynamics (e.g. "largely sampling variability of a stationary process," "barely exceeds the null"), and rejects a name-drop-then-affirm dismissal ("a surrogate confirmed the dynamics are genuine") without a fragile "genuine"-veto — so it will not false-pass an agent that merely mentions a surrogate. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE Dosenbach-160 ROI time series — small, reliable S3 host; downloads then cached). Deps: nilearn 0.12.1 + numpy/scipy/pandas/nibabel (phase randomisation via numpy FFT — no extra deps). Timeouts generous (sliding-window extraction over ~60 subjects).
