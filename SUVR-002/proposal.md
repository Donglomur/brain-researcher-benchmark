## SUVR-002

**Proposal Title:** Regional SUVR of a heterogeneous static-PET cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** PET quantification

**Source paper:** Rousset, Ma & Evans 1998, *J. Nucl. Med.* (Correction for partial volume effects in PET: geometric transfer matrix / GTM); Baker et al. 2017, *Alzheimer's & Dementia: DADM* (reference-region SUVR harmonization, https://doi.org/10.1016/j.dadm.2016.11.002). Dataset: a **synthetic** static brain-PET cohort (8 subjects, differing reference regions, PSFs, and segmentation types), generated deterministically at `synth_build/generate_fixtures.py`; planted ground truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the per-region SUVR for each supported target region); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the SUVR quantification (including a from-scratch GTM/Rousset partial-volume correction) **from scratch** (no tool bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded per-region against a **held-out reference** on a **convention-invariant** quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — several structurally different computations are chosen per subject from the sidecar: a **PVC branch** — a *majority* (5/8) ship a full-volume parcellation and must be partial-volume-corrected with a from-scratch GTM/Rousset inversion (build the geometric-transfer matrix `G_ij = mean over region i of the Gaussian-PSF-blurred indicator of region j`, form regional means, solve `G t = m`), while the rest ship only sparse ROI labels and must get the **uncorrected** regional-mean ratio (a different value); and **reference divergence** — the SUVR denominator is the region *named per subject* (cerebellar grey, pons, or centrum-semiovale WM, split 3/3/2, a majority non-cerebellar), so a fixed reference biases every panel of the mismatched subjects.
2. **Coupled-physics assembly** — the PSF sigma must be converted from FWHM to voxels (`σ = FWHM/voxel_size/(2√(2ln2))`), the GTM built and solved, and the ratio formed; the global SUV scale (dose/weight/calibration) differs per subject but cancels in the ratio and must **not** be applied. An unconverted sigma, or GTM applied everywhere / nowhere, each breaks a different subset of panels — and via the GTM coupling a contaminated reference biases every corrected region.
3. **Hidden robustness** — unannounced: on a *majority* of subjects a compact cluster of reference-region voxels is grossly contaminated by spill-in (~8×), biasing the shared denominator, and on several subjects a cluster of a target region's voxels is dead (~0); both must be **detected and rejected** before the means are formed. Plus an **omit rule** — on two subjects a target region lies entirely outside the valid brain mask and its SUVR is undeterminable and must be omitted.
4. **Convention-invariant grading** — SUVR is a ratio (the global scale cancels), and the GTM solve is convention-invariant given the pinned PSF; a genuinely different implementation (FFT/zero-pad PSF, Moore-Penrose solve, a different robust window) reproduces every panel, so two independent correct implementations agree.

### Verifier

`tests/test_outputs.py` recomputes every SUVR from the bundled PET with a **held-out reference** pipeline (`suvr_pipeline` + `suvr_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades each (subject × target-region) panel as its own test (56 panels). Reward is binary (pytest rc → reward.txt via test.sh). A computable panel passes when the submitted SUVR agrees within rtol 0.04, atol 0.02; an unsupported panel (a target region with no valid in-mask voxels) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (FFT/zero-pad PSF, Moore-Penrose GTM solve, a different robust-mean window; **no** import of the reference) reproduces all 56 panels to within 0.6% (median 0.13%), and all scipy convolution boundary modes agree to within 0.32%, so the graded SUVR is convention-invariant. The plausible-but-wrong pipelines each fail only their own axis: **no PVC**, **fixed reference**, **no artifact rejection**, **unconverted sigma**, and **compute-omitted** each fail only the panels on their own axis; a naive uniform pipeline fails 49/56.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=3** | **0.0 (all 3)** | Solved only **14/56 panels**, failing on every genuine hard axis — the GTM/Rousset PVC branch vs uncorrected ROI ratio, the per-subject named reference region, the unannounced spill-in / dead-voxel rejection, and the undeterminable-region omit — a reproducible multi-axis execution failure confirmed across k=3 trials. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model computes plain regional-mean ratios against a single assumed reference — it does not build the from-scratch GTM/Rousset correction where a parcellation is shipped, does not thread the per-subject named reference, does not discover-and-reject the spill-in / dead-voxel clusters, and does not honour the omit rule. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (branch the PVC path, build and solve the GTM, thread the per-subject reference, reject artifact clusters, and omit undeterminable regions — with no bundled tool), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the physics but never enumerates the pitfalls (the artifact clusters, the reference divergence in full) — the agent must discover the robustness axis from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
