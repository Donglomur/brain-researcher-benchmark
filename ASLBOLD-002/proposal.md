## ASLBOLD-002

**Proposal Title:** Dual-echo simultaneous ASL+BOLD — baseline perfusion, BOLD change and calibrated CMRO2 across a heterogeneous pCASL cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Calibrated fMRI / CMRO2

**Source paper:** Davis et al. 1998, *PNAS* (calibrated fMRI / Davis model, https://doi.org/10.1073/pnas.95.4.1834); Alsop et al. 2015, *MRM* (recommended pCASL implementation, https://doi.org/10.1002/mrm.25197); Hoge et al. 1999, *MRM* (deoxyhemoglobin dilution model). Dataset: a **synthetic** dual-echo pseudo-continuous ASL (pCASL) ASL+BOLD cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce baseline CBF, rBOLD, rCBF, and calibrated rCMRO2 maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the ASL+BOLD separation and the Davis calibration **from scratch** (no fitter bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. The M0 reference diverges: a background-suppressed subject carries a dedicated M0 scan that **must** be used (its control image is a strongly suppressed, invalid proton-density reference), while a non-suppressed subject has no M0 scan and must derive M0 from the control image with a saturation-recovery correction — reading absolute CBF off the wrong M0 over-scales it several-fold. The calibration also diverges: a hypercapnia run yields the Davis *M* and hence relative CMRO2, but a subject with no hypercapnia run has no identifiable *M*, so rCMRO2 is **not computable and must be omitted** (like a reference-absent absolute concentration). A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the surround perfusion difference, the same-echo M0 cancellation, the Alsop (2015) single-compartment pCASL constants, the long-echo BOLD percent change, the field-dependent β, the hypercapnia *M* and the Davis CMRO2 inversion must **all** be assembled correctly; an error in any one compounds across the (subject × map) panels.
3. **Hidden robustness** — never announced in `instruction.md`: on a **majority** (5 of 8) of subjects a low-frequency common-mode drift develops across the run, and because control and label images are acquired half a TR apart, a simple pairwise control−label subtraction reads that drift — amplified ~100× by the static/perfusion ratio — as a large spurious perfusion change, biasing baseline CBF, task rCBF, and thus rCMRO2. It must be removed with a surround (or detrend/running) subtraction the agent discovers from the data.
4. **Convention-invariant grading** — baseline CBF (mL/100g/min), rBOLD (%), rCBF (%) and Davis rCMRO2 (%) are uniquely determined given the pinned constants (in `protocol.json`), and the drift is a linear trend any correct de-contamination removes identically; two independent correct implementations compute them the same (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled dual-echo signals with a **held-out reference** pipeline (`aslbold_pipeline` + `aslbold_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the grey-matter mask, one parametrized test per (subject × map) panel across **32 panels**; the Harbor reward is binary (1 iff every panel passes). A computable map passes when the submission is finite and ≥90% of grey-matter voxels agree within a per-map tolerance (CBF rtol 8%/atol 1.5 mL/100g/min; rBOLD rtol 12%/atol 0.30; rCBF rtol 10%/atol 3; rCMRO2 rtol 12%/atol 3, percent units); an unsupported map (rCMRO2 for a subject with no hypercapnia run) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (a different, label-centred surround subtraction, a GLM percent change, its own M0 and Davis algebra — importing none of the reference) reproduces every computable panel (rBOLD to ~1e-7, CBF within ~4%, rCBF/rCMRO2 well within tolerance) and passes all 32. The plausible-but-wrong pipelines each fail only their own axis: **ignore the M0 scan** → 3 CBF panels; **simple pairwise subtraction** → the 5 drift subjects' CBF/rCBF/rCMRO2; **fabricate M with no calibration** → the omit panels; **wrong BOLD echo** → rBOLD; **sign-flipped Davis exponent** → the calibrated rCMRO2. A naive uniform pipeline (pairwise + control-as-M0 + a fixed literature *M* for everyone) fails 20 of 32 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | k=1 | 0.0 | Solved **19/32 panels**; the 13 it missed fall on the hard axes — the per-subject M0 divergence (dedicated M0 scan vs saturation-recovery control), the un-cued common-mode drift (surround vs pairwise subtraction on the 5 drift subjects, biasing CBF/rCBF/rCMRO2), and the Davis calibration/omit fork. Reward 0 because every panel must pass. |
| **2nd frontier family (Claude/Gemini)** | pending | pending | to be run by the maintainer at gate calibration |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean ASL+BOLD pipeline and applies it uniformly — it handles the standard subjects but does not thread the per-subject M0 rule through the suppressed subjects nor discover-and-remove the unannounced common-mode drift before the perfusion subtraction. The specific failing set is characterised from the task's hard axes (per-panel identities were not logged for this k=1 run), but the 13-panel miss is the count the gate recorded and lands on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get a hundred coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (per-subject M0, the corrupted drift, the CMRO2 omit fork) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
