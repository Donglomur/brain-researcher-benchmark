## SODIUM-002

**Proposal Title:** Absolute tissue-sodium-concentration (TSC) mapping of a heterogeneous 23Na cohort — B1+/T1-corrected, phantom-calibrated mmol/L — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative sodium (23Na) MRI

**Source paper:** Ouwerkerk et al. 2003, *Radiology* (tissue sodium concentration in human brain tumors by 23Na MRI, https://doi.org/10.1148/radiol.2272020483); Madelin & Regatte 2013, *JMRI* (biomedical applications of sodium MRI in vivo, https://doi.org/10.1002/jmri.24168). Dataset: a **synthetic** ultra-high-field 23Na sodium-MRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (estimate the per-voxel absolute TSC in mmol/L, and the effective T2* map where determinable); the difficulty is *execution*, not an un-cued judgement. The agent implements the TSC quantification **from scratch** (no solver bundled), over a **heterogeneous 7-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the single largest divergence: a **multi-echo** acquisition recovers the relaxation-corrected TE=0 signal from a per-voxel log-linear echo fit (and produces the effective T2* map), whereas a **single-echo** acquisition cannot fit anything and must instead correct with the per-**region** T2* **constants** in the sidecar — a *different* constant for the tumour lesion (short T2*), for healthy tissue, and for each reference gel — and must **omit** the T2* map. One fixed relaxation recipe is wrong for half the cohort, and one global relaxation constant biases the lesion and the calibration on the single-echo sessions.
2. **Coupled-physics assembly** — every constant must be exactly right: the SPGR B1+/T1 saturation factor `sin(a)(1−E1)/(1−cos(a)E1)` with `a = B1·nominal`, the per-voxel receive-sensitivity division, the per-region relaxation correction, and the per-**session** external-reference-phantom calibration (a least-squares slope through the origin of corrected phantom signal vs known [Na]) that anchors the absolute mmol/L scale — an error in any one compounds.
3. **Hidden robustness** — discovered from the data: a minority of sessions carry **one grossly mis-calibrated reference tube** that must be rejected before the calibration (else the whole TSC scale is biased ~15%), and a minority carry a compact cluster of **low-SNR signal-void voxels** inside the parenchyma that must be masked out, not reported as a spurious concentration.
4. **Convention-invariant grading** — a genuinely-correct independent implementation (weighted vs unweighted log-linear fit, median-ratio vs through-origin calibration, a different SNR threshold and an independent noise estimate) reproduces every computable panel to within ~1.3% (TSC) / ~1.7% (T2*) of the reference — well inside tolerance (proven below), so the graded quantity carries no method/convention spread.

### Verifier

`tests/test_outputs.py` recomputes TSC (and T2*) from the bundled signal with a **held-out reference** pipeline (`sodium_pipeline` + `sodium_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over label-defined masks. Each (subject × panel) is its own parametrized test (**28 panels** = 7 subjects × {TSC_tissue, TSC_tumour, TSC_excl, T2star}); the panel vector is a fine diagnostic gradient while the Harbor reward (`test.sh`) is binary on the whole suite. A computable panel passes when ≥90% of its voxels agree within tolerance (TSC rtol 5%/atol 1.5 mmol/L; T2* rtol 12%/atol 1.5 ms); the void-exclusion panel passes when ≥90% of the signal-void voxels are excluded; the T2* panel of a single-echo subject passes only when the map is **omitted**.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation reproduces every computable panel to within ~1.3% (TSC) / ~1.7% (T2*) of the reference — well inside tolerance. The plausible-but-wrong pipelines each fail only their own axis: **ignore B1+/receive** → only the inhomogeneous sessions; **one global relaxation constant** → only the single-echo (and lesion) panels; **keep the mis-calibrated tube** → only the mis-calibrated sessions; **no void mask** → only the void sessions; **force T2* on a single echo** → the omit rule. Partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | k=1 | 0.0 | Solved **20/28 panels**; the 8 it missed fall on the hard axes — the multi-echo vs single-echo relaxation fork (per-region T2* constants and the T2* omit), the mis-calibrated-tube rejection before the phantom calibration, and the low-SNR signal-void masking. Reward 0 because every panel must pass. |
| **2nd frontier family (Claude/Gemini)** | pending | pending | to be run by the maintainer at gate calibration |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean TSC pipeline and applies it uniformly — it does not fork the single-echo per-region relaxation constants, discover-and-reject the mis-calibrated tube, nor mask the void voxels. The specific failing set is characterised from the task's hard axes (per-panel identities were not logged for this k=1 run); the 8-panel miss is the count the gate recorded and lands on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the per-subject relaxation fork, the coupled saturation/receive/calibration chain, and the tube/void robustness right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable but never enumerates the pitfalls (the single-echo relaxation fork, the bad tube, the void voxels) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
