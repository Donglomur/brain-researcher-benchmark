## FMRIGLM-002

**Proposal Title:** First-level fMRI GLM of a heterogeneous single-run cohort — an execution-hard reconstruction task (recipe divergence + coupled-inference assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Functional MRI analysis

**Source paper:** Friston et al. 1994, *Human Brain Mapping* (statistical parametric mapping / general linear model, https://doi.org/10.1002/hbm.460020402); Woolrich et al. 2001, *NeuroImage* (temporal-autocorrelation prewhitening for the fMRI GLM, https://doi.org/10.1006/nimg.2001.0931). Dataset: a **synthetic** first-level fMRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth betas/t-stats held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (produce per-voxel task and modulation betas and t-statistics); the difficulty is *execution*, not an un-cued judgement. The agent builds a first-level GLM **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need different designs**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** effect sizes and inference.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different designs*, discoverable only from each events table and motion trace: **half** the subjects' events tables carry a `modulation` column (a parametric-modulation regressor must be added and its contrast reported) and half do **not** (that contrast is undefined and must be **omitted**); the task regressor of a modulation subject is estimated in the *augmented* design, so dropping the modulation column also biases the task beta. TR, run length, and event timing differ per subject, so the regressors must be rebuilt per run.
2. **Coupled-inference assembly** — the fixed-micro-grid (0.1 s) HRF convolution and frame sampling, the mean-centred (not standardised, not orthogonalised) parametric-modulation column, the 6 motion + degree-2 drift nuisance basis, the gross-spike detection, the pooled AR(1) Prais-Winsten prewhitening, and the GLS contrast inference (β and t) must **all** be assembled correctly, and an error in any one compounds.
3. **Hidden robustness** — a majority of subjects (6 of 8) carry a few grossly motion-corrupted frames — a large framewise-displacement transient mirrored by a BOLD spike **not** captured by the 6 realignment parameters — that must be detected and modelled out (spike regression); never announced in `instruction.md`, and the betas and t-statistics are biased if they survive.
4. **Convention-invariant grading** — given the supplied HRF and the pinned design/prewhitening/inference conventions, β and t are uniquely determined; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every quantity from the bundled BOLD + events + motion with a **held-out reference** pipeline (`glm_pipeline` + `glm_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask. Reward is **binary**: pytest returns 0 only if **all 32** (subject × quantity) panels pass. A computable quantity passes when ≥90% of brain voxels agree within a per-quantity tolerance (beta rtol 4%/atol 0.4; tstat rtol 6%/atol 0.5); an unsupported quantity (the modulation contrast for a subject with no `modulation` column) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (FFT convolution, an explicit whitening matrix, scipy linear algebra, a different spike threshold) reproduces every computable panel to ~1e-6 (well within tolerance). The plausible-but-wrong pipelines each fail only their own axis: **no motion censoring** biases every quantity only on the corrupted subjects; an **omit-rule violation** (forcing or dropping the modulation contrast) fails those panels; **no prewhitening** biases the inference; a **re-normalised HRF** rescales every beta; **no drift** biases the fit. A naive uniform pipeline fails 20 of 32 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **14/32 panels**, failing the unannounced motion-spike censoring on the 6 corrupted subjects, the AR(1) Prais-Winsten prewhitening, and the parametric-modulation omit rule / augmented design. |
| **2nd frontier family (Claude/Gemini)** | _pending_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model builds one clean GLM and applies it uniformly — it does not discover-and-model the unannounced motion spikes, thread the pooled AR(1) prewhitening, nor honour the modulation omit rule (and the coupled task-beta bias it induces). The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get a hundred coupled design and inference decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the conventions but never enumerates the pitfalls (the modulation fork, the corrupted frames, the per-run design rebuild) — the agent must discover them.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted quantities are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
