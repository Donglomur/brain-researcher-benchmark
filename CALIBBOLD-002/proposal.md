## CALIBBOLD-002

**Proposal Title:** Calibrated-BOLD CMRO2 estimation across a heterogeneous gas-challenge cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Calibrated fMRI / CMRO2 quantification

**Source paper:** Davis et al. 1998, *PNAS* (calibrated functional MRI / the Davis model, https://doi.org/10.1073/pnas.95.4.1834); Hoge et al. 1999, *MRM* (deoxyhaemoglobin-dilution model); Chiarelli et al. 2007, *NeuroImage* (hyperoxia calibration of BOLD). Dataset: a **synthetic** calibrated-BOLD gas-challenge cohort (simultaneous BOLD + ASL during task, plus a hypercapnia or hyperoxia calibration run), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth parameters held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the Davis calibration constant M and the relative-CMRO2 map) and the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the quantitative inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the calibration constant M is estimated by a *structurally different* method per subject, discoverable only from each sidecar: a **hypercapnia** subject uses the isometabolic CO2 power law `M = dBOLD/(1 − rCBF^(α−β))`; a **hyperoxia** subject cannot use that at all and must instead derive M from the arterial blood-gas panel (baseline venous saturation from OEF, the arterial O2-content change from the Hüfner constant and dissolved-O2 solubility, the resulting relative venous deoxy-haemoglobin change fed into `M = dBOLD/(1 − rCBF^(α−β)·r_dHb^β)`); and a subject with **no gas run** has no identifiable M, so absolute CMRO2 is not computable and both M and rCMRO2 must be **omitted** (like a water-reference-absent absolute concentration). A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the per-run percent change, the field-dependent β, the two M estimators with their many blood-oxygen constants, and the Davis rCMRO2 inversion `rCMRO2 = (1 − dBOLD/M)^(1/β)·rCBF^((β−α)/β)` must **all** be assembled correctly; an error in any one compounds across the (subject × map) panels.
3. **Hidden robustness** — two requirements the instruction never mentions and the agent must discover from the data: a **majority of subjects (5 of 8)** carry two grossly motion-corrupted whole-volume frames per run that bias every percent change (and thus M and CMRO2) unless censored; and every subject has grey-matter voxels with near-zero baseline perfusion (ASL drop-out) whose naive CBF ratio is division-by-noise and turns CMRO2 non-finite unless handled.
4. **Convention-invariant grading** — rBOLD, rCBF (%), M (%), and rCMRO2 (%) are uniquely determined once α/β and the blood-oxygen constants are pinned in `protocol.json`; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled timeseries with a **held-out reference** pipeline (`calib_pipeline` + `calib_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the grey-matter mask, one parametrized test per (subject × map) panel — **32 panels** in all. A computable map passes when the submission is finite and ≥90% of grey-matter voxels agree within a per-map tolerance (rBOLD rtol 10%/atol 0.15; rCBF rtol 10%/atol 3; M rtol 12%/atol 1; rCMRO2 rtol 12%/atol 3, all in percent units); an unsupported map (M or rCMRO2 for a subject with no gas run) passes only when the submission **omits** it. Reward is binary (all panels pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (different motion detector, GLM percent-change, different drop-out handling, its own hyperoxia blood-oxygen algebra; **no** import of the reference) reproduces every computable panel to ~1e-7 on the well-perfused voxels and passes all 32. Wrong pipelines each fail only their own axis: **skip motion censoring** biases only the motion subjects; **hyperoxia-as-hypercapnia** fails only the hyperoxia subjects; **fabricate M with no calibration** violates the omit rule; a **sign-flipped Davis exponent** fails only rCMRO2; **unhandled drop-out voxels** make CMRO2 non-finite. A naive uniform pipeline fails 26 of 32 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=3** | **0.0 (all 3)** | Solved **10/32 panels** (reward 0.0 confirmed across 3 trials). The 22 failing panels concentrate on the task's designed hard axes: the per-subject M-estimator fork (the hyperoxia blood-gas M and its dependent rCMRO2), the no-gas-run **omit** rule, the unannounced motion-frame censoring on the 5 corrupted subjects, and the ASL drop-out handling. A reproducible multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean calibrated-BOLD pipeline and applies it near-uniformly — it handles the standard hypercapnia/task computation but does not correctly thread the hyperoxia blood-gas M, honour the no-calibration omit rule, or discover-and-reject the unannounced corrupted frames, so the 0.0 is earned on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get a hundred coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the per-subject M fork, the corrupted frames, the drop-out voxels, the omit forks) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
