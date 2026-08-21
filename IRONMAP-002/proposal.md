## IRONMAP-002

**Proposal Title:** Regional brain-iron mapping from R2* and susceptibility — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / relaxometry

**Source paper:** Langkammer et al. 2010, *Radiology*, "Quantitative MR imaging of brain iron: a postmortem validation study" (https://doi.org/10.1148/radiol.10100495); Langkammer et al. 2012, *NeuroImage*, "Quantitative susceptibility mapping (QSM) as a means to measure brain iron? A post mortem validation study" (https://doi.org/10.1016/j.neuroimage.2012.05.049); Hallgren & Sourander 1958, *J. Neurochem.* (regional non-heme iron). Dataset: a **synthetic** multi-echo GRE + QSM iron-mapping cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth iron concentrations held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (estimate per-voxel non-heme iron concentration from R2* and susceptibility and write it out); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the R2* fit, susceptibility referencing and iron calibrations **from scratch** (no reconstruction library bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar/region map: some subjects are multi-echo (the mono-exponential OLS-on-log R2* fit applies and an R2*-based iron map is produced) while others are **single-echo** (R2* is not determinable and that map must be **omitted**, susceptibility only). The R2*→iron calibration slope and intercept scale with field strength (1.5/3/7 T) and differ between deep-gray nuclei and white matter, so the **right per-field, per-region calibration** must be selected per voxel; and the provided susceptibility map carries a per-subject reference offset that must be removed (subtract the reference-region mean) before its own per-region calibration.
2. **Coupled-physics assembly** — the log-linear R2* fit with robust echo rejection, the susceptibility referencing, and the two pinned linear calibrations with a physical validity window must **all** be assembled correctly; an error in any one corrupts a different subset of the (subject × map) panels.
3. **Hidden robustness** — a **majority** of the multi-echo subjects carry **one grossly motion-corrupted echo volume** that must be **rejected** before the R2* fit; this robustness requirement is **not announced** and must be discovered from the data, or R2* (hence the R2*-iron map) is biased.
4. **Convention-invariant grading** — R2*-iron and susceptibility-iron (mg/100g) are uniquely determined given the pinned fit, referencing convention, and calibrations (including the validity-window NaN pattern), so two independent correct implementations compute them identically (proven below); a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes both iron maps from the bundled magnitude + susceptibility with a **held-out reference** pipeline (`iron_pipeline` + `iron_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel. A computable map passes when ≥90% of brain voxels agree within tolerance (iron_r2s rtol 10%/atol 1.0 mg/100g; iron_chi rtol 8%/atol 0.8), where agreement **also** requires reproducing the reference's NaN pattern (the validity-window exclusions); an unsupported map (R2*-iron for a single-echo subject) passes only when the submission **omits** it. Reward is binary (all 16 panels pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (scipy `gelsd`, batch sigma-clip echo rejection, calibration read from `protocol.json` — no import of the reference) reproduces every computable panel to within 1.4e-6 mg/100g with zero NaN-pattern mismatch. The plausible-but-wrong pipelines each fail only their own axis: **ignore field** biases iron_r2s only on the non-3T subjects; **one-region calibration** biases white matter; **forget referencing** biases every iron_chi; a **non-robust R2* fit** is biased only on the motion-corrupted subjects; **no validity window** breaks the NaN pattern; **force R2* on single-echo** fails the omit rule — a naive uniform pipeline fails 15 of the 16 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **11/16 panels**, failing the hard axes: the per-field/per-region R2*→iron calibration selection, the susceptibility reference-offset removal and validity-window NaN pattern, the unannounced corrupted-echo rejection on the majority of multi-echo subjects, and/or the single-echo omit fork. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean iron pipeline and applies it uniformly — it handles the standard 3T panels but does not correctly thread the per-field/per-region calibration, the reference offset, nor discover-and-reject the unannounced corrupted echo. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the physics, units, referencing, and per-subject/per-region adaptation right with no bundled library), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the calibration conventions but never enumerates the pitfalls (the corrupted echo, the per-field/region forks, the single-echo omit) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`; verified by grep). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
