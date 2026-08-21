## FMRILAG-002

**Proposal Title:** Hemodynamic-lag mapping of a resting-state BOLD cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Functional MRI / hemodynamics

**Source paper:** Tong & Frederick 2010, *NeuroImage* (global low-frequency oscillation lag, https://doi.org/10.1016/j.neuroimage.2010.06.049); Tong et al. 2019, *Front. Neurosci.* (systemic low-frequency hemodynamic "noise" in resting-state BOLD, https://doi.org/10.3389/fnins.2019.00787). Dataset: a **synthetic** resting-state BOLD cohort (8 subjects, one run each, differing TR), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth lag fields held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the per-voxel hemodynamic lag map, in seconds, NaN where not significant); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the lag estimator **from scratch** (no pipeline bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the *reference signal* forks, and the fork is **not labelled**: on the clean subjects the whole-brain global mean faithfully tracks the shared low-frequency hemodynamic fluctuation and is the reference, but on the artifact subjects a high-amplitude non-neural fluctuation contaminates a band of non-gray-matter voxels and hijacks the global mean, so the reference must be restricted to gray matter. Neither uniform choice works — the global reference is wrong on the artifact subjects, and a gray-matter reference is systematically offset (deep white-matter / CSF arrive later) on the clean subjects — so the fork must be inferred by comparing the two candidate references.
2. **Coupled-physics assembly** — the reference must be built, the integer-frame lagged Pearson cross-correlation formed over the retained frames, its peak located, and that peak refined to sub-TR precision by **parabolic interpolation**, with the correct sign convention (positive where the voxel follows the reference); an error in any stage biases the map. Integer-only lag (no parabolic refinement) fails the tolerance.
3. **Hidden robustness** — gross motion-spike frames (present on a *majority* of subjects, unannounced) must be **censored** before building the reference *and* before the per-voxel cross-correlation, else the spikes — shared across the brain at zero relative lag — pull every voxel's lag toward zero; and voxels whose peak correlation is at the noise floor (non-vascular / low-SNR) carry no significant lag and must be **omitted** (NaN) rather than read as lag.
4. **Convention-invariant grading** — the graded quantity (a lag in seconds, and an omit partition) is fixed by the pinned model; an ungraded band between the significance and noise cuts makes the exact threshold non-load-bearing, so two independent correct implementations agree — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes the lag map from the bundled BOLD with a **held-out reference** pipeline (`fmrilag_pipeline` + `fmrilag_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise**. Reward is fractional over 16 (subject × check) panels: a **lag** panel requires the submitted lag to be finite and agree within 0.40 s with the reference over the significantly-lagged voxels (reference correlation ≥ 0.55); an **omit** panel requires the noise-floor voxels (reference correlation ≤ 0.30) to be omitted (NaN). The ungraded band between the two cuts makes the exact significance threshold non-load-bearing.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (DVARS-style spike detector, FFT-based normalized cross-correlation, its own per-voxel peak search and reference-agreement threshold; **no** import of the reference) reproduces every panel to well within tolerance. The plausible-but-wrong pipelines each fail only their own axis: **always the global reference** fails the artifact subjects; **always the gray-matter reference** fails the clean subjects; **no spike census** biases every voxel toward zero lag; **no significance omit** fails the omit panels; **integer-only lag** fails the sub-TR tolerance — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=3** | **0.0 (all 3)** | Solved **5/16 panels**, failing the genuine hard axes — the un-labelled global-vs-gray-matter reference fork, the unannounced motion-spike censoring, the significance omit, and the sub-TR parabolic refinement — a reproducible multi-axis execution failure confirmed across k=3 trials. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one clean lag pipeline (a fixed reference, integer or lightly-refined lag, no spike census, no significance omit) and applies it uniformly — it never infers the per-subject reference fork nor discovers the unannounced motion spikes and noise-floor voxels. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (infer the reference fork, censor spikes, build the cross-correlation and refine its peak, and omit the insignificant voxels — with no bundled pipeline), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and conventions but never enumerates the pitfalls (the reference fork, the spike census, the significance omit) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
