## CVRLAG-002

**Proposal Title:** Lag-optimized cerebrovascular-reactivity (CVR) mapping of a heterogeneous BOLD-CO2 cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Functional MRI / cerebrovascular reactivity

**Source paper:** Moia et al. 2021, *NeuroImage*, "Voxelwise optimization of hemodynamic lags to improve regional CVR estimates in breath-hold fMRI" (https://doi.org/10.1016/j.neuroimage.2020.117579); Bright & Murphy 2013, *NeuroImage* (reliable CVR quantification from PetCO2 regression). Dataset: a **synthetic** BOLD-fMRI CO2-reactivity cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth lag/CVR held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (estimate per-voxel hemodynamic lag and, where determinable, CVR amplitude, and write them out); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the lag-optimized CVR estimators **from scratch** (no pipeline bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. The core divergence is the per-voxel **hemodynamic lag**: the CO2 regressor must be shifted per voxel over a lag search of **either sign** and the best-fitting shift picked, because a steno-occlusive-like cluster in several subjects has genuinely **negative** lag — a single fixed-lag GLM, or a positive-only search, is wrong exactly there. The regressor **source** also forks three ways: most subjects carry a calibrated PetCO2 trace (`petco2_units == mmHg`) that must be resampled onto the BOLD frame grid honouring a per-subject sampling interval **and** a negative start offset (CVR in %/mmHg determinable); a couple have **no** external trace, where the regressor is built data-driven from the mask-mean BOLD; and one carries an **uncalibrated** external trace (`petco2_units != mmHg`) — still resampled to recover the lag, but CVR is **not** determinable and must be **omitted**. A uniform "a PetCO2 file exists, therefore compute CVR" rule is wrong.
2. **Coupled-physics assembly** — the percent-signal conversion, the offset-honouring linear resample, the both-signs per-voxel lag search, the constant+linear detrend, and the slope-at-optimal-lag must **all** be right; an error in any one compounds across the (subject × map) panels.
3. **Hidden robustness** — a minority of frames are grossly motion-corrupted (signal spikes) and must be censored before the fit, and a spatial low-SNR cluster must not be read as spurious reactivity; **neither is announced** in `instruction.md`.
4. **Convention-invariant grading** — lag (s) and CVR (%/mmHg) are uniquely determined given the pinned percent-signal model, resample convention, and lag definition, so two independent correct implementations compute them identically (proven below); a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes both maps from the bundled BOLD + PetCO2 with a **held-out reference** pipeline (`cvr_pipeline` + `cvr_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the gradeable voxels (brain mask AND reference optimal-lag correlation ≥ 0.5; low-SNR voxels not graded), one parametrized test per (subject × map) panel. A computable lag panel passes when ≥90% of gradeable voxels agree within half a TR (the integer-frame optimum; a correct sub-TR refinement of an on-grid lag still agrees); a computable CVR panel passes when ≥90% agree within rtol 8% + atol 0.02 %/mmHg; an unsupported CVR panel (data-driven or uncalibrated-external — three of the eight subjects) passes only when the submission **omits** it. Reward is fractional across the 16 panels.

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (fixed-fractional spike census instead of a MAD z-score, a per-voxel `polyfit` lag loop instead of the vectorised `lstsq`/`einsum`, an explicit Pearson formula — no import of the reference) reproduces every computable panel to ~2e-8, so the graded quantity is convention-invariant. The plausible-but-wrong pipelines each fail only their own axis: a **fixed-lag GLM** or **positive-only search** fails the lag (and, on external subjects, CVR) panels wherever the true lag is nonzero or negative; **skipping the percent conversion** puts CVR on the wrong scale; **ignoring the PetCO2 start offset** shifts every lag on the offset subjects; **not resampling** mis-times the regressor where dt ≠ TR; **computing CVR for a data-driven subject** violates the omit rule; **leaving the motion spikes in** biases both maps — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **7/16 panels**, failing the hard axes: the both-signs per-voxel lag search (the negative-lag steno-occlusive cluster), the offset-honouring PetCO2 resample, the frame-spike censoring, and the omit fork for the data-driven / uncalibrated-external CVR panels. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean CVR pipeline and applies it uniformly — it handles the standard positive-lag calibrated subjects but does not correctly thread the both-signs lag search, the per-subject regressor-source fork, and the unannounced spike censoring. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the timing, units, and per-subject adaptation right with no bundled pipeline), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the negative-lag cluster, the corrupted frames, the CVR omit forks) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`; verified by grep). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
