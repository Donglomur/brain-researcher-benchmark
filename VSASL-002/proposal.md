## VSASL-002

**Proposal Title:** Velocity-selective ASL (VS-ASL) cerebral blood flow quantification — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Perfusion MRI / arterial spin labeling

**Source paper:** Wong et al. 2006, *MRM* (velocity-selective arterial spin labeling, https://doi.org/10.1002/mrm.20906); Guo et al. 2021, *MRM* (velocity-selective inversion ASL); Alsop et al. 2015, *MRM* (recommended implementation for ASL CBF quantification). Dataset: a **synthetic** velocity-selective ASL cohort (many label/control repetitions, per-subject labeling module and M0-calibration path), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the per-voxel CBF map in mL/100g/min) and the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the CBF quantification **from scratch** (no quantifier bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — two forks decided only from each sidecar. **Labeling module:** subjects labeled with a velocity-selective **saturation** module (VSS) vs a velocity-selective **inversion** module (VSI) invert the same single-compartment model with *different constants* — the effective-inversion factor κ (1 for saturation, 2 for inversion) and the labeling efficiency α (0.72 vs 0.90) — so applying one module's math to the other biases CBF by ~2×; the cohort is split ~half and half. **M0 calibration:** absolute CBF needs the equilibrium magnetization M0, obtained differently per subject — a fully-relaxed reference scan (`m0.npy`) for some, a saturation-recovery correction of the proton-density control (`M0 = <control>/(1−exp(−TR_ctrl/T1tissue))`) for others; using the raw control as M0 biases the scale ~20–30%. **Omit rule:** one subject ships neither an M0 scan nor a usable PD control, so absolute CBF is **not** determinable and the map must be **omitted** (like a water-reference-absent absolute concentration).
2. **Coupled-physics assembly** — the single-compartment inversion `f = dM·λ / (κ·α·M0·TI·exp(−TI/T1blood))` (reported as `CBF = f·6000`) must thread the module's κ and α, the calibrated M0, and the shared constants (λ=0.90, T1blood=1.65 s) correctly; an error in any factor compounds across the (subject × region) panels.
3. **Hidden robustness** — a **majority of subjects (5 of 8)** carry one or two grossly motion-corrupted label/control repetitions (a whole image scaled by a gross factor) that must be rejected by a robust average before the perfusion difference (and the control-derived M0) are trustworthy; a plain mean over all reps is biased. None of the artifacts are announced.
4. **Convention-invariant grading** — CBF (mL/100g/min) is uniquely determined once the module constants, calibration paths, and shared physical constants are pinned in `protocol.json`; two independent correct implementations compute it identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes CBF from the bundled label/control/M0 signals with a **held-out reference** pipeline (`vsasl_pipeline` + `vsasl_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the grey- and white-matter masks, one parametrized test per (subject × region) — **16 panels** in all (region ∈ {GM, WM}). A computable subject passes a region panel when ≥90% of that region's voxels agree with the reference within (rtol 0.10, atol 5 mL/100g/min); the undeterminable subject (`m0_source` = none) passes only when the submission **omits** CBF. Reward is binary (all panels must pass), while the CTRF per-panel breakdown is monotone in correctness.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (per-voxel median robust average, explicit closed-form M0 arithmetic, its own module/omit branching; **no** import of the reference) reproduces every computable panel to well within tolerance (max median voxel relative error across subjects well under the tolerance). Wrong pipelines each fail only their own axis: the **wrong module for all** fails the mismatched-module subjects; a **raw-control M0** fails the subjects needing a real calibration; a **non-robust average** fails only the motion-corrupted subjects; **computing the undeterminable subject** fails the omit panels — so a naive uniform pipeline fails a majority of the panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **6/16 panels**. The 10 failing panels concentrate on the task's designed hard axes: the VSS-vs-VSI labeling-module fork (κ, α), the M0-calibration fork (saturation-recovery vs raw control), the unannounced robust-average rejection on the 5 motion-corrupted subjects, and the no-calibration **omit** rule. A reproducible multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a clean single-compartment ASL pipeline and applies it near-uniformly — it quantifies the standard subjects but does not branch the module constants, apply the saturation-recovery M0 calibration, honour the no-calibration omit rule, or discover-and-reject the unannounced corrupted repetitions, so the 0.0 is earned on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get many coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the module and calibration forks, the corrupted repetitions, the omit rule) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted ground truth are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
