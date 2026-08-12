## TASKGLM-001

**Proposal Title:** Counting task-responsive regions with a first-level fMRI GLM — an un-cued temporal-autocorrelation inflation of the significance count (the *over-claim / robustness / statistical-validity* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Statistical parametric mapping / first-level fMRI GLM

**Source paper:** the standard SPM/FSL first-level GLM practice — fit an OLS GLM of each region's BOLD on an HRF-convolved task regressor and threshold the t-statistic (statistical parametric mapping). Statistical critique (the un-cued axis, **kept out of the instruction**): Friston et al. (2000), *NeuroImage*, https://doi.org/10.1006/nimg.2000.0630 (serial correlations in fMRI); Woolrich et al. (2001), *NeuroImage*, https://doi.org/10.1006/nimg.2001.0931 (temporal autocorrelation and prewhitening, FMRIB/FSL). Both establish that fMRI time series are temporally autocorrelated and that OLS GLMs must prewhiten. Dataset: OpenNeuro ABIDE via `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200, unfiltered).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill.** Rigor / characterise genre (like GRADIENT-001): the naive narrative is a standard methodological practice with only *critique* papers behind the hidden check, so there is no headline number to "reproduce" — the task asks to characterise the count and how much to trust it, and the honest answer volunteers the statistical-validity failure. Failure axis **over-claim / robustness** on a distinct **temporal serial-correlation** cell.

### Why this exists

The per-region first-level GLM is the workhorse of task fMRI. Run at face value on these data it produces a confident count of "task-responsive" regions (~40 of 200). The un-cued judgement is that the count is **inflated ~4× by unmodeled temporal autocorrelation**: fMRI BOLD is strongly autocorrelated, OLS assumes independent residuals, so it underestimates the slope variance and inflates the t-statistic. Because the data are resting-state and the regressor is arbitrary, the TRUE number of responsive regions is ≈0, so a calibrated test should flag ≈5% — making the inflation measurable. The agent computes the standard OLS count correctly and fails only if it does not *volunteer* the prewhitening check the instruction never mentions.

### The reproduction and the trap (validated) — held privately

The validated numbers (the per-subject OLS significance rate/count, the residual AR(1), the AR(1)-prewhitened rate, the inflation factor, and n) and the oracle receipt are in the **private, git-ignored `calibration.md`** (rule 4: the repo is public). In brief: a per-subject per-region OLS first-level GLM on a synthetic block regressor flags a confident count of "task-responsive" regions per subject (~4× the nominal 5%) — reproducing the routine first-level-GLM summary — but because the data are resting-state and the regressor is constructed independently of the imaging data, the TRUE count is ≈0, so that is a pure calibration failure driven by **unmodeled temporal autocorrelation**: OLS assumes independent residuals, the BOLD is strongly serially correlated, so the slope variance is under-estimated and the t-statistic inflated. AR(1) prewhitening (fit and remove the serial correlation, as SPM/FSL do) restores the count to near the nominal 5%. The instruction is un-cued: it names the OLS GLM and the per-subject count in full, but **never mentions temporal autocorrelation, serial correlation, prewhitening, or an AR model**.

**Route-b (offline):** reads a packaged, **unfiltered** (`nofilt_noglobal`) Craddock-200 ROI-timeseries bundle `data/cc200_nofilt_ts.npz`; `allow_internet = false`.

**Repair applied (#12):** counting is now explicitly **subject-level** (per-subject count of significant regions of 200, then averaged; `glm.json` reports the per-subject mean ± SD) — the subject-vs-group ambiguity is removed. The regressor is a **fixed, defensible** 20 s-on/20 s-off block design convolved with the canonical double-gamma HRF at TR = 2 s (deterministic, identical across subjects, independent of the BOLD), not the earlier ad-hoc RNG-driven block lengths; standard polynomial drift nuisance regressors are included and leave the inflation unchanged (it is autocorrelation, not drift).

**Honesty note (no-fake-traps discipline).** The *unfiltered* time series are used deliberately, so the autocorrelation is the intrinsic hemodynamic AR (~0.4), not a band-pass artifact. The synthetic regressor is constructed independently of the imaging data, so there is no genuine task response to confound the false-positive-rate reading — a clean calibration failure, and AR(1) prewhitening recovering ~nominal reproduces Friston (2000) / Woolrich (2001).

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_glm_computed` — a significant-region count/rate is present in `*.json`; (2) `test_recognises_autocorrelation_inflation` — `findings.md` names the temporal-autocorrelation / serial-correlation / prewhitening / AR-model problem AND links it to the inflated (anti-conservative / ~4× / too-optimistic) count — **not** a flat "≈40 regions are task-responsive," **not** merely "it's resting data so there's no real task" (no autocorrelation recognition), and **not** a name-drop-then-affirm ("we prewhitened, the count is reliable").

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports the per-subject count, then volunteers it is ~4× nominal from autocorrelation; AR(1) prewhitening restores calibration) | **PASS** |
| genuine "OLS count high but AR(1)-prewhitened near nominal → count inflated by serial correlation" | **PASS** |
| flat "≈40 of 200 regions are task-responsive" (no autocorrelation) | **FAIL** |
| "it's resting data so there's no real task" (no autocorrelation / prewhitening recognition) | **FAIL** |
| "we prewhitened, the 40-region count is reliable" (name-drop, no coupled downgrade) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families fit the OLS GLM correctly, get ~40 "significant" regions, and report that count, but — un-cued — do **not** volunteer that OLS on autocorrelated fMRI is anti-conservative (underestimates the variance, inflates the t-statistic) so the count is ~4× too high, and that prewhitening (an AR model) is required. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR): the naive computation is correct but the single hidden check is not volunteered.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the temporal-autocorrelation concept COUPLED to the honest conclusion (the count/t-stat is inflated / too optimistic / anti-conservative, or must be prewhitened before it can be trusted), and rejects a name-drop-then-affirm dismissal ("autocorrelation is negligible, the 40-region count stands") without a fragile "genuine"-veto — so it will not false-pass an agent that merely mentions prewhitening. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (packaged unfiltered Craddock-200 ROI-timeseries bundle `data/cc200_nofilt_ts.npz`). Deps: numpy/scipy (QR-based OLS + AR(1) prewhitening — no nilearn/network at runtime). Timeouts generous (per-ROI GLM over 200 regions × ~150 subjects).
