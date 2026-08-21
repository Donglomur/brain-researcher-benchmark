## SPINALQMRI-002

**Proposal Title:** Per-level quantitative MRI of a heterogeneous spinal-cord cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / relaxometry (spinal cord)

**Source paper:** Deoni et al. 2003, *MRM* (DESPOT1 variable-flip-angle R1 mapping, https://doi.org/10.1002/mrm.10407); De Leener et al. 2017, *NeuroImage* (Spinal Cord Toolbox / per-level cord qMRI, https://doi.org/10.1016/j.neuroimage.2016.10.009). Dataset: a **synthetic** cervical spinal-cord qMRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (produce per-voxel cord maps and per-level cord means); the difficulty is *execution*, not an un-cued judgement. The agent implements per-level spinal-cord qMRI **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded over the cord ROI against a **held-out reference** on **convention-invariant** quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar: some acquired an **MT pair** (MTR is computable, R1 is not and must be **omitted**); some a **two-flip variable-flip-angle pair** (R1 is computable, MTR is not and must be **omitted**); some **both**; and the subjects cover **different, contiguous cervical-level subsets**. A uniform recipe is wrong on most subjects.
2. **Coupled-physics assembly** — MTR = 100·(S_off−S_on)/S_off is a pinned ratio, but R1 is the two-flip **DESPOT1** solve (y=S/sin α, x=S/tan α, E1=slope, R1=−ln(E1)/TR) with the true per-voxel flip α = B1·radians(flip_deg), so **ignoring the per-voxel B1+ transmit map** (uniform on some subjects, ±25% inhomogeneous on others) biases R1. Errors compound across the (subject × map) panels.
3. **Hidden robustness** — the hard, un-cued part is **cord geometry**: the provided cord segmentation is an ROI, not a guarantee — on a majority of levels it **over-includes free-water / CSF partial-volume voxels** at the boundary (value collapses toward CSF), and a subset of levels additionally carry **gross cord-motion / CSF-pulsation voxels** (value thrown far off). A trustworthy per-voxel map and per-level mean require **detecting and excluding** these grossly contaminated cord-ROI voxels (finite value on valid voxels, NaN on excluded); a pipeline that trusts the whole cord mask biases every per-level mean. Never announced in `instruction.md`.
4. **Convention-invariant grading** — because the contamination is **gross** (a wide gap from clean cord), the valid set is method-agnostic and the pinned MTR ratio and B1-corrected DESPOT1 R1 are uniquely determined; two independent correct implementations reproduce every panel (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled per-level images with a **held-out reference** pipeline (`sc_pipeline` + `sc_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades over the cord ROI, one parametrized test per (subject × map) panel — **32 panels** in all. Reward is **fractional** (each panel its own test). A per-voxel panel passes when ≥90% of the reference's valid cord voxels agree within tolerance (MTR rtol 4%/atol 1.0 p.u.; R1 rtol 4%/atol 0.03) **and** ≥90% of the reference's grossly-contaminated cord voxels are omitted (NaN). A per-level panel passes when ≥90% of the levels' cord means agree (MTR atol 1.5 p.u.; R1 atol 0.04). An unsupported map (MTR with no MT pair, R1 with no VFA pair) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (a percentile/IQR outlier rule instead of MAD, its own DESPOT1 linear algebra) reproduces every panel. The plausible-but-wrong pipelines each fail only their own axis: **keeping all cord voxels** fails the per-voxel-omit and per-level-mean panels across the cohort; **ignoring B1** biases R1 only on the inhomogeneous subjects; **computing an unsupported map** fails the omit rule — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **12/32 panels**, failing the unannounced cord-ROI contamination detection/exclusion (CSF partial-volume + gross motion voxels), the B1-corrected DESPOT1 R1 solve on the inhomogeneous subjects, and the MTR/R1 acquisition-fork omit rule. |
| **2nd frontier family (Claude/Gemini)** | _pending_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model trusts the provided cord mask and applies one uniform recipe — it does not discover-and-exclude the grossly contaminated boundary/motion voxels (biasing every per-level mean), thread the per-voxel B1 correction, nor honour the MTR/R1 omit forks. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the coupled cord physics, contamination handling, and per-subject forks right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the conventions but never enumerates the pitfalls (the MT/VFA forks, the contaminated cord voxels, the B1 correction) — the agent must discover them.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
