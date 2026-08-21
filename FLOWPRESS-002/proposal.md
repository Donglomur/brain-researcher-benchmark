## FLOWPRESS-002

**Proposal Title:** Relative pressure mapping from a heterogeneous 4D-flow / phase-contrast cohort by pressure-Poisson integration — an execution-hard reconstruction task (acquisition recipe divergence + coupled Navier-Stokes assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / hemodynamics

**Source paper:** Ebbers & Farnebäck 2009, *J. Magn. Reson. Imaging* (pressure-Poisson relative pressure from velocity MRI, https://doi.org/10.1002/jmri.21641); Krittian et al. 2012, *Med. Image Anal.* (direct relative-cardiovascular-pressure computation). Dataset: a **synthetic** segmented-vessel velocity-field cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth fields held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the relative-pressure field and the peak systolic drop); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's reconstruction tasks (e.g. `pcasl-cbf-quantifier`): the agent implements the pressure reconstruction **from scratch** (no solver bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded against a **held-out reference** on a **gauge-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. Six subjects are 3-directional 4D-flow (n_comp=3, three cardiac frames) where the full 3D pressure-Poisson field **is** solvable; two are 2D through-plane phase-contrast (a single stored velocity component on one plane) where no spatial field can be reconstructed — the pressure map must be **omitted** and only the simplified unsteady-Bernoulli peak drop reported (a structurally different computation, like a missing water-reference forcing an omit).
2. **Coupled-physics assembly** — the momentum source b = −ρ(∂v/∂t + (v·∇)v) + µ∇²v sums a temporal (unsteady) acceleration finite-differenced across frames, a convective acceleration requiring the full velocity-gradient tensor contracted with the velocity, and a viscous term; an error in any one corrupts the whole global Poisson solve (dropping the temporal term biases the field; dropping the convective term collapses the stenotic drop **and** the field).
3. **Hidden robustness** — spanning a **majority** of the cohort and unannounced: the provided ROI is a loose bounding region including low-magnitude background-phase and partial-volume voxels carrying grossly wrong velocity, and in **five of the six** 4D-flow subjects a couple of dozen interior voxels at the graded (middle) cardiac frame are gross aliasing/noise spikes. All must be excluded (segment the true lumen from the magnitude, reject the velocity outliers) **before** differentiating, because the derivatives amplify them and the Poisson solve propagates any leaked garbage across the entire field. Nothing in the instruction or protocol mentions the spikes; only one 4D-flow subject is clean, so correct physics without robustness earns just it plus the two through-plane drops.
4. **Convention-invariant grading** — relative pressure is defined only up to an additive gauge constant, so both fields are de-meaned before comparison; two independent correct implementations agree to a worst-case per-voxel max under 0.06 mmHg (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reference-node/gauge ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every quantity from the bundled velocity field with a **held-out reference** pipeline (`flowpress_pipeline` + `flowpress_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades over 16 (subject × quantity) panels, each its own test. The relative-pressure **field** is graded **voxelwise** over the reference's interior-lumen voxels after de-meaning both fields; a panel passes when ≥90% of voxels agree within (rtol 0.06, atol 0.15 mmHg). The peak drop is graded within (rtol 0.12, atol 0.30 mmHg). A field is **omitted** for a 2D exam and the submission must omit it too. Reward is binary (all panels pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent implementation (finite-volume direct solve vs least-squares edge integration, a different lumen-segmentation threshold, a different spike-rejection rule, a different derivative stencil; **no** import of the reference) rejects the same gross outliers and reproduces every field to a worst-case per-voxel max under 0.06 mmHg and every drop to under 0.01 mmHg — far inside tolerance. The plausible-but-wrong pipelines each fail only their own axis (ignore-temporal biases the fields; ignore-convective collapses the stenotic drops+fields; skip-the-outlier-rejection fails all five spiked subjects on **both** quantities; skip-the-lumen-segmentation additionally fails the clean subject; solve-a-field-for-a-2D-exam violates the omit rule); a naive non-robust uniform pipeline fails all 16 — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **6/16 panels**, failing the 2D-vs-3D omit fork, the coupled Navier-Stokes momentum-source / Poisson-solve assembly, and the unannounced lumen-segmentation + velocity-outlier-rejection axes the task is built around. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean pressure-Poisson pipeline and applies it uniformly — solving the clean/through-plane panels but missing the per-subject 2D omit fork, the exact coupled momentum-source assembly, and the discover-and-reject of the unannounced interior velocity spikes on the five contaminated 4D-flow subjects. The ten failed panels are the ones gated on those hard axes; the k=1 gate reports the count (6/16), and a per-panel itemization will come from the maintainer's calibration run.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (assemble coupled hemodynamic physics and get the per-subject decisions right with no solver), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the 2D omit fork, the loose ROI, the interior spikes) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted fields are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
