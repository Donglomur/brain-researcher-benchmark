## BGSUPASL-002

**Proposal Title:** Background-suppressed pCASL cerebral blood flow of a heterogeneous cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Perfusion MRI / arterial spin labeling (ASL)

**Source paper:** Alsop et al. 2015, *Magn. Reson. Med.* (ASL consensus / white-paper single-compartment kinetic model, https://doi.org/10.1002/mrm.25197); Ye et al. 2000, *Magn. Reson. Med.* (background suppression / ASSIST static-signal attenuation). Dataset: a **synthetic** background-suppressed pCASL perfusion cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth CBF/rCBF and calibration parameters held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce CBF in mL/100g/min and rCBF maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the quantitative ASL inversion **from scratch** (no quantifier bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. Background suppression attenuates the perfusion difference by `eps**n_bgs` with `n_bgs` varying 0..6; this factor must be divided back out or CBF is biased 13-35% low on a majority of subjects. The equilibrium magnetization M0 is obtained by a per-subject-different path keyed by `m0_source`: a finite-TR proton-density scan needs a saturation-recovery correction `M0=<m0>/(1-exp(-m0_tr/T1t))` (matters only when TR is short); a `sat_recovery` series needs a per-voxel nonlinear fit of `S(TI)=M0*(1-exp(-TI/T1))`; and a `none` subject has no calibration, so absolute CBF is **not determinable and must be omitted** (only the M0-free relative map is produced).
2. **Coupled-physics assembly** — the fully-arrived white-paper kinetic term, the background-suppression correction, the M0 calibration, and the robust repetition average must **all** be assembled correctly; an error in any one compounds across the (subject × map) panels.
3. **Hidden robustness** — a majority of subjects carry one grossly motion-corrupted control/label repetition (and, for the proton-density-scan subjects, a corrupted M0 repetition) that must be **detected and rejected** before repetition-averaging; this is never announced in `instruction.md`.
4. **Convention-invariant grading** — CBF (mL/100g/min) and rCBF (dimensionless, GM-median-normalized) are uniquely determined given the pinned kinetic model, so two independent correct implementations compute them identically (proven below); a from-scratch solver passes while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled signals with a **held-out reference** pipeline (`asl_pipeline` + `asl_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the grey- and white-matter voxels, one parametrized test per (subject × map) panel — 16 panels total. Reward is **fractional** (fraction of panels correct). A computable map passes when ≥90% of GM/WM voxels agree within a per-map tolerance (CBF rtol 10%/atol 3.0; rCBF rtol 8%/atol 0.05); an unsupported map (CBF for a `none` subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (median-over-repetitions robustness instead of one-at-a-time MAD rejection; scipy Levenberg–Marquardt saturation-recovery fit instead of a grid+parabola search; **no** import of the reference) reproduces every computable panel to a median voxel disagreement ~2% — comfortably inside tolerance. The plausible-but-wrong pipelines each fail only their own axis: **ignore background suppression** biases only the `n_bgs≥2` panels; **skip the scan saturation-recovery** biases only the short-TR proton-density subjects; a **raw (unfitted) saturation-recovery M0** biases only the `sat_recovery` subjects; a **non-robust average** biases only the motion-corrupted subjects; **computing CBF where there is no M0** violates the omit rule. A naive uniform pipeline fails 15 of the 16 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=3** | **0.0 (all 3)** | Solved **4/16 panels**; the failures fall on the task's hard axes — the background-suppression correction (`n_bgs≥2` subjects), the per-subject M0 calibration fork (short-TR scan saturation-recovery and the per-voxel `sat_recovery` fit), the unannounced corrupted-repetition rejection, and the `none`-subject omit rule. A reproducible multi-axis execution failure (reward 0 confirmed across k=3). |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean pCASL pipeline and applies it near-uniformly — it handles a few standard panels but does not correctly thread the per-subject background-suppression factor and M0 calibration paths, nor discover-and-reject the unannounced corrupted repetitions, so the 0.0 is earned on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get many coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (per-subject M0, the corrupted repetitions, the omit fork) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
