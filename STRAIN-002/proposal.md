## STRAIN-002

**Proposal Title:** Cardiac-induced brain micro-displacement and strain from gated phase MRI — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / brain motion & strain

**Source paper:** Soellinger et al. 2009, *MRM*, "3D cine displacement-encoded MRI of pulsatile brain motion" (https://doi.org/10.1002/mrm.21802); Sloots et al. 2020, *NeuroImage*, "Cardiac and respiration-induced brain deformations in humans quantified with high-field MRI" (https://doi.org/10.1016/j.neuroimage.2019.116526); Aletras et al. 1999, *JMR* (DENSE displacement encoding). Dataset: a **synthetic** gated brain-motion cohort with DENSE and phase-contrast acquisitions, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth displacement/strain held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (estimate per-voxel displacement magnitude and, where determinable, principal strain, and write them out); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the displacement/strain estimators **from scratch** (no tool bundled), over a **heterogeneous 9-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *structurally different* computations, discoverable only from each sidecar. The acquisition **type** forks the recipe: **DENSE** subjects give displacement directly from the encoded phase (robustly average the repetitions, subtract the diastolic reference, divide by the per-direction encoding sensitivity `ke`), whereas **phase-contrast** subjects give only velocity and require **integrating** it over the cardiac cycle (cumulative trapezoid from the baseline frame, then the frame of maximum mean displacement) — a structurally different computation, so a DENSE recipe applied to a PC subject (reading one velocity frame as a displacement) is grossly wrong, and vice-versa. A second fork is the **omit rule**: subjects without a diastolic reference/baseline (`reference_phase = false`) cannot define the undeformed reference configuration, so the strain tensor is **not determinable** and `pstrain` must be **omitted**, while the displacement magnitude is still recoverable.
2. **Coupled-physics assembly** — a residual **planar background drift** contaminates the displacement of a **majority** of subjects and must be removed by a planar detrend over static tissue (for PC, per cardiac frame before the peak is chosen) or both the magnitude and the strain are biased over the whole brain; DENSE reference subjects additionally carry a **non-planar system phase** that only the reference subtraction removes. These couple with the displacement-gradient / eigenvalue strain computation.
3. **Hidden robustness** — a minority of DENSE subjects have a motion-wrecked repetition and a minority of PC subjects a motion-wrecked cardiac frame that must be rejected/repaired before the displacement is trustworthy; this is **not announced** in `instruction.md`.
4. **Convention-invariant grading** — `disp_um` (µm) and `pstrain` (dimensionless, the largest eigenvalue of the symmetric displacement-gradient tensor formed by `numpy.gradient` central differences) are uniquely determined given the pinned definitions and voxel spacing, so two independent correct implementations compute them identically (proven below); a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes both maps from the bundled phase data with a **held-out reference** pipeline (`strain_pipeline` + `strain_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise**, one parametrized test per (subject × map) panel — `disp_um` over the brain mask, `pstrain` over the interior brain core. A computable map passes when ≥90% of its graded voxels agree within a per-map tolerance (disp_um rtol 8%/atol 3 µm; pstrain rtol 15%/atol 1.5e-3); an unsupported map (`pstrain` where `reference_phase = false`) passes only when the submission **omits** it. Reward is binary (all 18 panels pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (complex-phasor reference subtraction, pairwise-agreement repetition rejection, median-|phase| frame detection, cumsum trapezoid integration, scipy least-squares detrend, and an explicit-slicing central-difference gradient — sharing no code with the reference) reproduces every panel to machine precision (displacement and strain median relative error ~2e-8). A **naive uniform** pipeline (one recipe for all, no robustness, no omit) scores only 2/18, and each plausible-but-wrong pipeline (wrong acquisition type, no detrend, no repetition/frame rejection, no omit, no reference subtraction) fails 3–8 panels on its own axis, so any single missing axis zeroes the binary reward.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **9/18 panels**, failing the hard axes: the DENSE (direct) vs phase-contrast (velocity-integration) acquisition fork, the planar-drift detrend and reference subtraction, the unannounced motion-wrecked repetition/frame rejection, and/or the `pstrain` omit rule where no diastolic reference exists. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one displacement recipe and applies it uniformly — it handles some panels but does not correctly thread the DENSE/PC structural fork, the background detrend, nor discover-and-reject the unannounced corrupted repetition/frame. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the physics, units, and per-subject adaptation right with no bundled tool), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the displacement/strain conventions but never enumerates the pitfalls (the corrupted repetition/frame, the acquisition-type fork, the strain omit) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`; verified by grep). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
