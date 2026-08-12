## DYNCONN-001

**Proposal Title:** Reproduce the "dynamic functional connectivity" headline (Allen 2014 / Hutchison 2013) — an un-cued stationarity artifact (the *over-claim / robustness* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Time-varying (dynamic) functional connectivity

**Source paper:** Allen et al. (2014), *Cerebral Cortex*, https://doi.org/10.1093/cercor/bhs352 ("Tracking whole-brain connectivity dynamics in the resting state"); Hutchison et al. (2013), *NeuroImage*. Stationarity critique (the un-cued axis): Laumann et al. (2017), Hindriks et al. (2016), Liégeois et al. (2017). Dataset: ABIDE Dosenbach-160 ROI time series (originally `nilearn.datasets.fetch_abide_pcp`, cpac, rois_dosenbach160), packaged offline.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001 / TOPEDGES-001. Route-b offline (reads a packaged `data/*.npz`; no network).**

### Why this exists

Sliding-window "dynamic connectivity" is one of the most-cited resting-state phenomena. Reproduced at face value it looks compelling — connectivity fluctuates window-to-window and recurs into "states." The un-cued judgement is that those fluctuations **do not meaningfully exceed a proper stationary null**, so the "time-varying states" are largely a sampling artifact. Exactly the shipped pattern: the agent is asked to reproduce a famous result, computes it correctly, and fails only if it does not *volunteer* the stationary-null comparison the instruction never mentions. Failure axis **over-claim / robustness** (a differentiated instance vs GRADIENT-001 / TOPEDGES-001, on a different topic).

### The reproduction and the trap (validated) — held privately

The validated numbers (observed edge-SD, the stationary-null ratio across window lengths, the paired-test p-value, n) and the oracle receipt are in the **private, git-ignored `calibration.md`** (rule 4). In brief: sliding-window FC does fluctuate substantially on these data (reproducing Allen 2014 / Hutchison 2013), but against **repeated** multivariate phase-randomised surrogates (100/subject) with **paired** inference across subjects the observed variability barely exceeds the null (a few % excess), and this ratio is invariant to window length — so the apparent "dynamics" are overwhelmingly sampling variability of a stationary process. The instruction is un-cued (it names the reproduction and the sliding-window method in full, but never mentions stationarity, a null/surrogate, or robustness).

**Honesty note (no-fake-traps discipline).** The *null model matters*, and it was checked rather than inherited. A **white-noise** Gaussian null with only the static covariance is **invalid** — it ignores autocorrelation, so its observed/null ratio is window-length-dependent. The **multivariate phase-randomised** null preserves the power spectrum *and* cross-spectrum and gives a stable ratio at every window length, reproducing the Laumann (2017) result. The task uses the correct null. Note also the honest subtlety the repeated-surrogate + paired design surfaces: the small excess *is* statistically detectable across subjects, yet negligible in magnitude — the honest conclusion turns on effect size, not on a bare significance call.

### Data (offline, route-b)

Packaged bundle `data/dos160_dynfc.npz` (`numpy.load(..., allow_pickle=True)`): `ts` = an object array of ~60 subjects' Dosenbach-160 ROI time series (each `T × 160`, `float16`), plus `atlas` / `preprocessing` provenance strings. The time series are ABIDE `cpac` `filt_noglobal` (band-pass filtered, no GSR), stated explicitly in the instruction so the agent's pipeline matches. No network; `allow_internet = false`.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_dynamics_computed` — a real sliding-window edge-variability magnitude and sane subject count are present in `*.json`, and (where a stationary-null / ratio is reported) it sits near 1 (the true "barely exceeds" direction); a fabricated output that inflates the dynamics far past the null fails. (2) `test_recognises_stationarity_artifact` — `findings.md` recognises the observed dynamics barely exceed (are largely explained by) a stationary null — **not** a flat "reproduces/doesn't," and **not** merely name-dropping a surrogate while affirming the dynamics are genuine. The recognition must LINK the stationarity/sampling-artifact to the dynamics.

**Discrimination (validated locally, offline):**

| solution | verdict |
|---|---|
| reference (reproduces the variability, then reports it barely exceeds a spectrum-matched stationary null under repeated-surrogate paired inference) | **PASS** |
| genuine "edge-SD ~0.26 but only ~1.04x a phase-randomised null → sampling artifact" | **PASS** |
| flat "dynamic connectivity states are present, edge-SD ~0.26" (no null) | **FAIL** (recognition) |
| "ran a surrogate, dynamics confirmed genuine" (name-drop, no coupled downgrade) | **FAIL** (recognition) |
| fabricated "observed 3x the stationary null, +201% excess" | **FAIL** (data check) |
| empty submission | **FAIL** (data check) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (offline, in-container). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families compute the sliding-window variability correctly and report "dynamic connectivity" as present, but — un-cued — do **not** volunteer the spectrum-matched stationary-null comparison that shows the fluctuations barely exceed chance. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note.** The recognition check is negation-aware and downgrade-driven: it requires the honest CONCLUSION coupled to the dynamics (e.g. "largely sampling variability of a stationary process," "barely exceeds the null," "~96% reproduced by the surrogate"), and rejects a name-drop-then-affirm dismissal ("a surrogate confirmed the dynamics are genuine") without a fragile "genuine"-veto — so it will not false-pass an agent that merely mentions a surrogate, and it still lets the honest oracle pass even though the oracle correctly notes the small excess is statistically detectable. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (packaged Dosenbach-160 timeseries bundle). Deps: numpy/scipy (phase randomisation via numpy FFT, paired test via scipy — no nilearn/network at runtime). Timeouts generous (sliding-window extraction + 100 surrogates over 60 subjects; ~80 s locally).
