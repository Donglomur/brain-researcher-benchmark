## BGSUPASL-002

**Proposal Title:** Background-suppressed pCASL cerebral blood flow of a heterogeneous cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Perfusion MRI / arterial spin labeling (ASL)

**Source paper:** Alsop et al. 2015, *Magn. Reson. Med.* (ASL consensus / white-paper single-compartment kinetic model, https://doi.org/10.1002/mrm.25197); Ye et al. 2000, *Magn. Reson. Med.* (background suppression / ASSIST static-signal attenuation). Dataset: a **paper-parameterized** background-suppressed pCASL perfusion cohort, generated deterministically at `synth_build/generate_fixtures.py`; the true physiology is held out for grading under `tests/planted_truth.npz` (the reference run on the noise-free, corruption-free signals, built by `synth_build/build_truth.py`).

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce CBF in mL/100g/min and rCBF maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the quantitative ASL inversion **from scratch** (no quantifier bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **publicly-declared robustness** requirement (the corrupted-repetition realization hidden), graded voxelwise against the **planted physiology** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. Background suppression attenuates the perfusion difference by `eps**n_bgs` with `n_bgs` varying 0..6; this factor must be divided back out or CBF is biased 13-35% low on a majority of subjects. The equilibrium magnetization M0 is obtained by a per-subject-different path keyed by `m0_source`: a finite-TR proton-density scan needs a saturation-recovery correction `M0=<m0>/(1-exp(-m0_tr/T1t))` (matters only when TR is short); a `sat_recovery` series needs a per-voxel nonlinear fit of `S(TI)=M0*(1-exp(-TI/T1))`; and a `none` subject has no calibration, so absolute CBF is **not determinable and must be omitted** (only the M0-free relative map is produced).
2. **Coupled-physics assembly** — the fully-arrived white-paper kinetic term, the background-suppression correction, the M0 calibration, and the robust repetition average must **all** be assembled correctly; an error in any one compounds across the (subject × map) panels.
3. **Declared robustness, hidden realization** — a majority of subjects carry one grossly motion-corrupted control/label repetition (and, for the proton-density-scan subjects, a corrupted M0 repetition) that must be **detected and rejected** before repetition-averaging. `instruction.md` now *declares* this requirement; only the *realization* (which subjects/repetitions are corrupted) is hidden.
4. **Convention-invariant grading** — CBF (mL/100g/min) and rCBF (dimensionless, GM-median-normalized) are uniquely determined given the pinned kinetic model, so two independent correct implementations compute them identically; a from-scratch solver passes while wrong pipelines fail — no reporting-convention ambiguity.

### What changed in this revision (addressing the review of #59/#61)

1. **Robustness contract made public.** `instruction.md` now states, under *Robustness / data-quality contract*, that a majority of subjects carry a grossly corrupted repetition that must be detected and rejected robustly (and restates the background-suppression correction). A correct implementation of the stated quantification is no longer penalized for failing to guess an undeclared step.
2. **Graded against the true physiology, not one fitter.** The verifier no longer recomputes with a private pipeline on the real data and demands agreement. It compares each submitted map, voxelwise over the GM/WM mask, to the **held-out planted target** = the reference run on the **noise-free, corruption-free** signals (`tests/planted_truth.npz`, built by `synth_build/build_truth.py`); any valid estimator applied to the real data recovers it within tolerance. The GM/WM grade mask (from the stored tissue + brain mask) travels in the npz. The hidden reference modules were removed from `tests/` (the oracle's copies remain under `solution/`).

### Verifier

`tests/test_outputs.py` grades **voxelwise** over the grey- and white-matter voxels against `tests/planted_truth.npz`, one parametrized test per (subject × map) panel — 16 panels total. A computable map passes when ≥90% of GM/WM voxels match the planted value within a per-map tolerance (CBF rtol 10%/atol 3.0; rCBF rtol 8%/atol 0.05); an unsupported map (CBF for a `none` subject) passes only when the submission **omits** it. Reward is binary (all panels pass → 1).

**Validity / discrimination evidence (recomputed for this revision).** The oracle recovers the planted target on **all 16 panels (14 computable at 0.94–1.00 voxel agreement, 2 correctly omitted)** — the lowest panels are the 7 T / high-`n_bgs` subject at the perfusion-noise floor, comfortably above the 0.90 gate. The plausible-but-wrong pipelines each fail on their declared axis: a **non-robust average** (no corrupted-repetition rejection) fails **12 panels** (the corrupted subjects' CBF collapse to 0.00 and rCBF to 0.77–0.88); **ignoring the background-suppression correction** fails the **5** `n_bgs≥2` CBF panels (rCBF is a ratio and cancels it, as expected). So a from-scratch correct solver passes and single-axis shortcuts fail, on axes the instruction declares (the corrupted repetitions and the BGS/M0 conventions).

### Difficulty — frontier gate

Oracle **reward 1.0** verified in-container. On the *previous* (hidden-contract) version, **gpt-5.6-sol (codex, xhigh) scored 0.0 across k=3**, solving 4/16 panels — failing the background-suppression correction, the per-subject M0 calibration fork, the corrupted-repetition rejection, and the `none`-subject omit rule.

**Frontier re-gate on this revised (public-contract) version: PENDING.** Because the revision *discloses* the robustness requirement, the old gate number does not transfer and must be re-measured — not overclaimed here. The expectation is that the coupled multi-axis assembly remains hard (per-subject BGS factor, the M0 calibration fork including the per-voxel `sat_recovery` fit, discover-and-reject the corrupted repetitions, the omit fork); the local discrimination above shows the single-axis shortcuts still fail. A 2nd frontier family (Claude/Gemini) gate is likewise pending at maintainer calibration.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get many coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions and now declares the robustness axis, but never enumerates the *realization* (per-subject M0 fork, which repetitions are corrupted) — the agent must discover those from the data.
- **Data.** Paper-parameterized, small, deterministic, and **leakage-clean** (the planted truth lives only under `tests/`, never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py` + `synth_build/build_truth.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
