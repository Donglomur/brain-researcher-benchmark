## CBFCVRJOINT-002

**Proposal Title:** Joint CBF + cerebrovascular-reactivity mapping from a dynamic ASL / CO2 challenge — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Perfusion MRI / arterial spin labeling (ASL)

**Source paper:** Alsop et al. 2015, *MRM* (ASL white paper / recommended implementation, https://doi.org/10.1002/mrm.25197); Buxton et al. 1998, *MRM* (general kinetic model for quantitative ASL); Bright & Murphy 2013, *NeuroImage* (CVR mapping with hypercapnia); Moia et al. 2020, *NeuroImage* (hemodynamic-lag correction of the CVR response). Dataset: a **synthetic** dynamic pCASL / CO2-challenge cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce baseline CBF, hemodynamic lag, rCVR, and aCVR maps); the difficulty is *execution*, not an un-cued judgement. The agent implements the coupled joint-CBF+CVR pipeline **from scratch** (no quantifier is bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with **hidden robustness** requirements, graded voxelwise against a **held-out reference** on **convention-invariant** physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. The M0 reference forks two ways: a dedicated background-suppressed M0 scan on some subjects, versus a saturation-recovery inversion of the baseline control image (using `tr_ctrl` and `T1_tissue`) on others — the wrong path biases white-paper CBF (and hence aCVR) by a large factor. The CO2 regressor forks two ways: an external PetCO2 trace (in mmHg, or in kPa needing a 7.5× conversion) resampled onto the pair-time grid, versus a data-driven gray-matter-mean CBF signal when no trace exists. A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the single-compartment kinetic inversion, the per-voxel M0 calibration, the per-pair CBF time series, the two-sided integer-frame lag search, and the GM-normalized reactivity slope must **all** be assembled correctly; an error in any one compounds across the (subject × map) panels.
3. **Hidden robustness** — a *majority* of subjects carry grossly motion-corrupted control/label pairs that must be **censored** before the baseline average and the lag/CVR fits, and a spatial cluster of vasculopathic voxels whose true hemodynamic lag is strongly delayed or **negative** (leading) — a fixed-lag or positive-only-window search mis-reads their reactivity. Neither is announced in `instruction.md`.
4. **Convention-invariant grading** — absolute reactivity aCVR (mL/100g/min per mmHg) is determinable **only** for the external-PetCO2 subjects and must be **omitted** for the data-driven ones (like a water-reference-absent absolute concentration); rCVR is always GM-normalized and dimensionless. The graded quantities are uniquely determined by the pinned model, so two independent correct implementations compute them identically (proven below) — no reporting-convention ambiguity.

### Verifier

`tests/` recomputes every map from the bundled signals with a **held-out reference** pipeline (`cbfcvr_pipeline` + `cbfcvr_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise**, one parametrized test per (subject × map) panel — 32 panels in all. CBF is graded over brain (GM+WM) voxels; lag/rCVR/aCVR over the well-determined voxels (reference optimal-lag correlation > 0.5). A computable map passes when ≥90% of graded voxels agree within a per-map tolerance (CBF rtol 10%/atol 2.5; rCVR rtol 12%/atol 0.06; aCVR rtol 12%/atol 0.15; lag within half a pair-TR); an unsupported map (aCVR for a data-driven subject) passes only when the submission **omits** it. The gate delivers a binary reward (all panels pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (different spike census, scipy resampling, an explicit per-voxel lag loop, algebraic CBF inversion; **no** import of the reference) reproduces every computable panel to ~1e-8 (floating-point roundoff). The plausible-but-wrong pipelines each fail only their own axis: **ignore the M0 fork** biases CBF/aCVR on the M0-scan subjects; **no frame census** biases baseline CBF and motion-subject reactivity; a **fixed / positive-only lag window** fails lag+rCVR on the anomalous-lag subjects; **aCVR for data-driven subjects** fails the omit rule; **no kPa conversion** fails aCVR on the kPa subject — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **13/32 panels** — correct on the standard subjects/maps, but failed the hard axes: the M0-calibration fork (dedicated M0 scan vs saturation-recovery of the control), the two-sided integer-frame hemodynamic-lag search on the delayed/negative-lag vasculopathic voxels, censoring the motion-corrupted pairs, the aCVR omit rule on the data-driven subjects, and the kPa→mmHg PetCO2 conversion. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean CBF/CVR pipeline and applies it uniformly — it handles the standard subjects but does not thread the per-subject M0 fork, discover-and-censor the unannounced corrupted pairs, or search both-signed lags. The passing panels show its underlying kinetic inversion is otherwise correct, so the 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get a hundred coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the M0 fork, the corrupted pairs, the both-signed lag, the omit forks) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
