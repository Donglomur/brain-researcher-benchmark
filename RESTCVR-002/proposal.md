## RESTCVR-002

**Proposal Title:** Resting-state cerebrovascular-reactivity (CVR) and hemodynamic-lag mapping — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Functional MRI / cerebrovascular reactivity

**Source paper:** Liu et al. 2017, *NeuroImage* (resting-state cerebrovascular-reactivity mapping without gas challenges, https://doi.org/10.1016/j.neuroimage.2016.11.054); Tong & Frederick 2014, *NeuroImage* (systemic low-frequency oscillations / hemodynamic lag). Dataset: a **synthetic** resting-state BOLD/PetCO2 cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth lag/rCVR/CVR maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce lag, rCVR, and where determinable CVR maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the resting-state CVR / hemodynamic-lag pipeline **from scratch** (no fitter bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. The vasoactive drive is the subject's natural end-tidal-CO2 fluctuation (resting state, no gas challenge), so the whole task turns on timing done right. Regressor fork: for some subjects an external PetCO2 trace was recorded (converted to mmHg — present in mmHg for some and kPa for others, ×7.5 apart — and resampled onto the BOLD frame grid honouring its own sampling and a possibly-negative start offset); for the rest **no trace exists**, so the regressor is built data-driven from the mask-mean BOLD and absolute CVR in %/mmHg is then **not determinable and must be omitted**.
2. **Coupled-physics assembly** — the motion-spike census, the percent-signal conversion, the detrending, the continuous (sub-frame) cross-correlation lag search, and the reactivity slope must **all** chain together; an error in any one compounds. The graded lag is the *continuous* cross-correlation-peak shift of either sign — a gas-challenge-style integer-frame (k·TR) search is too coarse and fails, because the resting delays are a fraction of a TR and TR varies per subject (1.0–2.0 s).
3. **Hidden robustness** — a majority of subjects carry a few grossly motion-corrupted frames that bias the lag heavily unless **censored** before the temporal mean; this is never announced in `instruction.md`.
4. **Convention-invariant grading** — lag (TR-relative tolerance), rCVR (GM-normalized), and CVR (%BOLD/mmHg) are uniquely determined given the pinned model, so two independent correct implementations compute them identically (proven below).

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled BOLD (+PetCO2) with a **held-out reference** pipeline (`restcvr_pipeline` + `restcvr_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the gradeable brain voxels (peak cross-correlation above an internal floor), one parametrized test per (subject × map) panel — 24 panels total. Reward is **fractional** (fraction of panels correct). A computable map passes when ≥90% of gradeable voxels agree within tolerance — lag atol = 0.35·TR (TR-relative, so sub-frame precision scales with the sampling interval; this uniformly defeats an un-refined integer-frame search while admitting any reasonable sub-frame refinement); rCVR rtol 10%/atol 0.06; CVR rtol 10%/atol 0.02. An unsupported map (absolute CVR for a data-driven subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (different motion census, and a fine-grid up-sampled-regressor lag search instead of the reference's parabolic peak refinement; **no** import of the reference) reproduces every computable panel to within tolerance (min 94.7% voxel agreement). The plausible-but-wrong pipelines each fail only their own axis: an **integer-frame lag** fails every lag panel; **no spike censoring** fails the spiked subjects; **no kPa→mmHg conversion** fails the kPa subjects' absolute-CVR panels; **absolute CVR for a data-driven subject** fails its must-omit panel. A single naive-uniform pipeline carrying all those choices fails 18 of the 24 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **15/24 panels**; the failures fall on the task's hard axes — the continuous sub-frame lag refinement (vs an integer-frame search), the unannounced motion-spike censoring, the kPa→mmHg conversion on the kPa subjects, and the data-driven-subject absolute-CVR omit rule. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model builds a CVR/lag pipeline but does not refine the lag to sub-frame precision, censor the unannounced motion spikes, or thread the per-subject unit conversion and omit fork, so the residual failures land on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get the timing, units, and per-subject forks right with no recipe). `instruction.md` names the deliverable and the conventions but never enumerates the pitfalls (the motion spikes, the sub-frame lag, the unit and omit forks) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
