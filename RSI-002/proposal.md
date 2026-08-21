## RSI-002

**Proposal Title:** Restriction-spectrum imaging (RSI) of a heterogeneous multi-shell diffusion cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure

**Source paper:** White et al. 2013, *Human Brain Mapping* (Restriction Spectrum Imaging, https://doi.org/10.1002/hbm.22081); Kaden et al. 2016, *NeuroImage* (spherical-mean technique for multi-compartment microstructure). Dataset: a **synthetic** multi-shell diffusion cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the ADC and the three restriction-spectrum signal-fraction maps where determinable); the difficulty is *execution*. The agent implements the RSI reconstruction **from scratch** (no fitter is bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference**.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. Most subjects sample several distinct b>0 shells and support the three-scale (restricted / hindered / free) spectrum; some are **single-shell**, where the three scales are underdetermined and the fractions must be **omitted** (only the total ADC is determinable, like R2* omitted for a single-echo subject). The b-value *set itself* differs per subject, so the `exp(-b·D)` design must be **rebuilt for each one** from its own b-values.
2. **Coupled-physics assembly** — the per-shell robust spherical (powder) mean, the b0 normalization, the per-subject NNLS design over the pinned scale basis, the post-fit fraction normalization, and the through-origin ADC must **all** be assembled correctly; an error in any one compounds.
3. **Hidden robustness** — a *majority* of subjects carry one or two grossly corrupted diffusion volumes (motion dropout / spike) that must be detected and **rejected** before the spherical mean, the ADC, and the NNLS spectrum are trustworthy. This is never announced in `instruction.md`.
4. **Convention-invariant grading** — with the scale basis **pinned** and the acquisition sampling several well-separated shells, the NNLS design has full column rank, so the objective is strictly convex and the coefficient vector is unique; two independent correct implementations compute the fractions and ADC identically (proven below).

### Verifier

`tests/` recomputes every map from the bundled signals with a **held-out reference** pipeline (`rsi_pipeline` + `rsi_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel — 32 panels in all. A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (fractions atol 0.03; ADC rtol 6%/atol 1e-5); an unsupported map (the three fractions for a single-shell subject) passes only when the submission **omits** it. The Harbor reward is binary (all panels pass → 1).

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (a different NNLS solver via `scipy.optimize.lsq_linear` bvls, a different batch sigma-clip robust mean, and independent ADC code; **no** import of the reference) reproduces every computable panel to within ~3e-8 (fractions) / ~1e-10 (ADC), far inside tolerance. The plausible-but-wrong pipelines each fail only their own axis: **compute fractions for single-shell subjects** fails the omit rule; a **non-robust spherical mean** is biased only on the corrupted subjects; a **wrong scale basis** or **unnormalized fractions** biases every fraction panel — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **18/32 panels** — correct on the ADC and clean multi-shell subjects, but failed the hard axes: the single-shell omit fork (the three fractions omitted when only one b>0 shell is present), rebuilding the `exp(-b·D)` NNLS design per subject's own b-values, and robustly rejecting the grossly corrupted diffusion volumes before the spherical mean. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one NNLS spectrum pipeline and applies it uniformly — it handles the clean multi-shell subjects but does not discover-and-reject the unannounced corrupted volumes or omit the fractions for the single-shell subjects. The passing ADC/clean panels show its per-shell fit is otherwise correct, so the 0.0 is earned on the genuine hard axes.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional, unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the model conventions but never enumerates the pitfalls (the single-shell omit fork, the per-subject design, the corrupted volumes) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
