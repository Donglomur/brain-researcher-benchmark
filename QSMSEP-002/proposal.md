## QSMSEP-002

**Proposal Title:** Magnetic susceptibility source separation (chi-separation) of a heterogeneous cohort — paramagnetic (iron) and diamagnetic (myelin/Ca) maps from GRE+SE relaxometry — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / susceptibility source separation

**Source paper:** Shin et al. 2021, *NeuroImage* (χ-separation: magnetic susceptibility source separation toward iron and myelin mapping in the brain, https://doi.org/10.1016/j.neuroimage.2021.118371). Dataset: a **synthetic** chi-separation (GRE+SE) susceptibility cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (separate the given total susceptibility into paramagnetic and diamagnetic sources and write the per-voxel maps, plus R2*/R2 where determinable); the difficulty is *execution*, not an un-cued judgement. The agent implements the chi-separation relaxometry **from scratch** (no fitter bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** quantities. The dipole inversion (frequency → total susceptibility) is **excised** — the total susceptibility is given — so the graded quantity carries no QSM regularization/reference convention.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — discoverable only from each sidecar: most subjects carry a multi-echo spin-echo (SE) series so R2 — and hence `R2' = R2* − R2` and the full separation into paramagnetic (iron) and diamagnetic (myelin/Ca) sources — is determinable, but a minority have **no** SE series, where R2' cannot be formed and chi_para / |chi_dia| must be **omitted** (only R2* reported); one subject is **single-echo GRE**, where R2* itself is not determinable and is omitted (yet its SE series still yields R2). A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — R2* (GRE) and R2 (SE) combine into R2', which the given total susceptibility splits via the closed form `chi_para = 0.5·(R2'/D_r + chi_tot)`, `|chi_dia| = 0.5·(R2'/D_r − chi_tot)`; an error in the R2* fit shifts **both** sources together, a swapped sign shifts them oppositely, a missed R2 subtraction or a wrong D_r rescales both. The relaxometric constant is **field-dependent** (`D_r = 90·field_T/3`), so a fixed-D_r pipeline biases the separation on the 7T subjects.
3. **Hidden robustness** — a **majority** of subjects carry one grossly motion-corrupted echo volume (in the GRE or the SE train) that must be **rejected** before the mono-exponential fit, or R2*/R2 (and every quantity downstream) is biased on those subjects.
4. **Convention-invariant grading** — because the total susceptibility and D_r are pinned *inputs* and only physical relaxation rates are estimated, the graded quantity is convention-invariant: a from-scratch implementation (leave-one-out echo rejection, scipy normal-equation backend, explicit 2×2 separation solve) reproduces every computable panel at 100% voxel agreement (proven below), so a correct solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled signals + the given `chi_tot` with a **held-out reference** pipeline (`chisep_pipeline` + `chisep_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask. Each of the **32 (subject × map) panels** is its own parametrized test; the Harbor reward is 1 only when **all** pass (pytest rc). A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (R2star/R2 rtol 6%/atol 0.8; chi_para/chi_dia_abs rtol 10%/atol 0.006 ppm); an unsupported map (R2* for a single-echo GRE, R2 with no SE, the separation without R2') passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A from-scratch independent implementation reproduces every computable panel at 100% voxel agreement (max deviation chi ≤ 0.0008 ppm, R2 ≤ 0.34 1/s — far inside tolerance), and even a fully nonlinear magnitude-domain estimator passes all 32 panels. A naive uniform pipeline (no echo rejection, fixed D_r, no omit adaptation) fails 23 of 32 panels; each single-flaw pipeline fails only the panels on its own axis (**kept corrupted echo** → only the corrupted subjects; **forgotten R2 subtraction / swapped sign** → every separation panel; **fixed non-field D_r** → only the 7T separations; **forced separation with no SE / R2* on single echo** → the omit rule), so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | k=1 | 0.0 | Solved **18/32 panels**; the 14 it missed fall on the hard axes — the un-cued corrupted-echo rejection before the mono-exponential fit, the field-dependent `D_r = 90·field/3` on the 7T subjects, and the SE-present / single-echo omit forks for R2*/R2 and the separation. Reward 0 because every panel must pass. |
| **2nd frontier family (Claude/Gemini)** | pending | pending | to be run by the maintainer at gate calibration |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean chi-separation and applies it uniformly — it does not discover-and-reject the unannounced corrupted echo volumes, field-scale D_r, nor cleanly fork the omit set. The specific failing set is characterised from the task's hard axes (per-panel identities were not logged for this k=1 run); the 14-panel miss is the count the gate recorded and lands on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the per-subject train forks, the field-scaled constant, and the echo robustness right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable but never enumerates the pitfalls (the corrupted echoes, the field-dependent D_r, the omit forks) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
