## QUASAR-002

**Proposal Title:** QUASAR multi-TI ASL model-free / model-based perfusion quantification — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Perfusion MRI / arterial spin labelling

**Source paper:** Petersen et al. 2006, *MRM*, "Model-free arterial spin labeling quantification approach for perfusion MRI" (QUASAR; https://doi.org/10.1002/mrm.20906). Dataset: a **synthetic** multi-TI pulsed-ASL cohort with paired flow-crushed/non-crushed acquisitions, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth CBF/ATT/aBV held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (estimate per-voxel CBF, ATT and, where determinable, aBV, and write them out); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the full QUASAR model-free and model-based quantification **from scratch** (no fitter bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *structurally different* analyses, discoverable only from each sidecar's acquisition field. Five subjects carry a **flow-crushed** acquisition paired with the non-crushed one: the intravascular arterial signal is directly measurable as `<noncrushed> − <crushed>`, so the **model-free** analysis applies — aBV and ATT are read off the T1-corrected arterial curve (a scaled area integral and its first moment), and CBF comes from regressing the crushed tissue curve onto the convolution of the **measured** local arterial input with the pinned single-compartment residue. The other three subjects have **only** the non-crushed acquisition: the arterial input can no longer be measured, so the analysis must **fall back** to a structurally different **model-based** kinetic fit (a transit-time search with a closed-form flow amplitude against the assumed dispersed-boxcar delivery) that yields CBF and ATT, while **aBV is not determinable and must be omitted**. A naive uniform pipeline fails a majority of the 24 panels either way.
2. **Coupled-physics assembly** — the crusher subtraction, the blood-T1 decay correction, the measured-AIF convolution, and the model-based delivery must **all** be assembled correctly, in the right units, with a per-voxel M0 calibration; an error in any one compounds.
3. **Hidden robustness** — two off-critical-path robustness requirements are **unannounced**: a **majority** of subjects carry one or two grossly motion-corrupted TI repetitions that must be rejected before the per-TI repetition average (a plain mean biases their curves), and voxels with ~0 equilibrium magnetization must be zeroed.
4. **Convention-invariant grading** — CBF (mL/100g/min), ATT (s) and aBV (dimensionless) are uniquely determined given the pinned signal model, crusher convention, constants, and M0 calibration, so two independent correct implementations compute them identically (proven below); a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled signals with a **held-out reference** pipeline (`quasar_pipeline` + `quasar_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the grey/white-matter mask, one parametrized test per (subject × map) panel. A computable map passes when ≥90% of mask voxels agree within a per-map tolerance (CBF rtol 10%/atol 3; ATT rtol 10%/atol 0.15; aBV rtol 12%/atol 0.002); an unsupported map (aBV for a non-crusher subject) passes only when the submission **omits** it. Reward is binary (all 24 panels pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (parametric arterial-boxcar fit + analytic tissue basis for the crusher branch, a scipy nonlinear (f,ATT) optimiser for the model-based branch, an independent robust average and M0 calibration — no import of the reference) reproduces every computable panel well within tolerance. The plausible-but-wrong pipelines each fail only their own axis: **model-based everywhere** omits all five crusher-pair aBV panels and biases their CBF/ATT (un-subtracted arterial signal contaminating the tissue curve); **model-free everywhere** cannot run where there is no crushed scan; **aBV emitted for all** fails the omit rule; **aBV without the T1-decay correction**, **tissue curve taken from the non-crushed instead of the crushed image**, and a **non-robust repetition mean** each fail only their own panels — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **15/24 panels**, failing the hard axes: the model-free (crusher-pair) vs model-based (non-crusher) fork, the measured-AIF convolution and T1-decay-corrected aBV, the unannounced motion-corrupted-repetition rejection on the majority of subjects, and/or the aBV omit rule on the non-crusher subjects. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one QUASAR recipe and applies it uniformly — it handles some panels but does not correctly thread the model-free/model-based structural fork, the measured-AIF convolution, nor discover-and-reject the unannounced corrupted repetitions. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the coupled physics, units, per-voxel M0 calibration, and per-subject adaptation right with no bundled quantifier), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the QUASAR conventions but never enumerates the pitfalls (the corrupted repetitions, the model-free/model-based fork, the aBV omit) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`; verified by grep). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
