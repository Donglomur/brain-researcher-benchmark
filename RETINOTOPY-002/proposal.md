## RETINOTOPY-002

**Proposal Title:** Population receptive-field (pRF) mapping of a heterogeneous retinotopy cohort — an execution-hard reconstruction task (recipe divergence + coupled-model assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Visual neuroscience / retinotopic fMRI (pRF)

**Source paper:** Dumoulin & Wandell 2008, *NeuroImage* (population receptive-field estimates in human visual cortex, https://doi.org/10.1016/j.neuroimage.2007.09.034); Kay et al. 2013, *J. Neurophysiol.* (compressive spatial summation in human visual cortex). Dataset: a **synthetic** retinotopic-mapping fMRI cohort (moving-bar apertures + BOLD + per-subject HRF), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce per-voxel eccentricity, polar angle, and pRF size) and the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the pRF inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the forward model forks per subject, discoverable only from each sidecar: the visual-field pixel→degree scale, stimulated extent, number of bar-sweep directions, and TR all vary (a hard-coded stimulus geometry mis-locates the pRF); each subject supplies its **own** sampled HRF and a **majority are non-canonical** (convolving with a hard-coded canonical HRF biases the fit); and some subjects are **compressive** (`css_exponent` n<1 given in the sidecar), where a linear fit recovers a biased pRF *size* and the field's σ/√n "effective size" is the wrong quantity — the graded size is the **raw** Gaussian sd. A single fixed recipe cannot fit the cohort.
2. **Coupled-model assembly** — the pRF forward model is heavily coupled: a unit-height 2D-Gaussian's spatial overlap with the moving-bar aperture → an optional compressive nonlinearity (drive = overlap**n) → convolution with the subject's HRF → a per-voxel free gain and baseline. An error in any stage corrupts the least-squares fit for eccentricity, polar angle, and size.
3. **Hidden robustness** — a **majority of subjects** carry a few grossly motion-corrupted timepoints (large transients across all voxels) that are **unannounced** and must be detected and censored before fitting, or the variance-explained collapses and determinable voxels are wrongly omitted. Additionally, only a minority of voxels carry a reliable pRF, so a pipeline that fits every voxel reports spurious pRFs on noise and on voxels outside the stimulated field — all of which must be **omitted** by a variance-explained threshold (NaN), with polar angle further NaN within the foveal cutoff.
4. **Convention-invariant grading** — eccentricity (deg), polar angle (rad), and raw-σ pRF size (deg) are convention-invariant once the coordinate convention, HRF convention, and determinability rule are pinned in `protocol.json`; two independent correct implementations agree to a p90 voxel disagreement ≤ 0.012 deg / 0.004 rad (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled BOLD + apertures with a **held-out reference** pipeline (`prf_pipeline` + `prf_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise**, one parametrized test per (subject × map) panel — **24 panels** in all. The reference recompute gives a per-voxel R²; a voxel is graded **must-keep** when ref R² ≥ 0.42 (submission must report a finite value within a per-map tolerance: eccentricity rtol 0.08/atol 0.22 deg; prf_size rtol 0.12/atol 0.25 deg; polar_angle circular atol 0.15 rad), **must-omit** when ref R² ≤ 0.20 (submission must write NaN), and ungraded in between; a panel passes when ≥85% of its graded voxels satisfy their condition.

**Grading-invariance proof (the key check).** Two genuinely-independent correct implementations (different motion-spike censoring, grid, and optimiser; **no** import of the reference) reproduce every panel to a p90 voxel disagreement ≤ 0.012 deg / 0.004 rad — far inside tolerance. Wrong pipelines each fail only their axis: a **hard-coded canonical HRF** fails the non-canonical subjects; **no motion-spike censoring** fails all 5 motion-corrupted subjects; a **linear fit on the compressive subjects** (or reporting σ/√n) fails their size panels; **keeping every voxel** fails the omit rule everywhere; a **flipped coordinate convention** reflects polar angle. A naive uniform pipeline (canonical HRF, no censoring, linear everywhere, no omit) fails all 24 panels, so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **11/24 panels**. The 13 failing panels concentrate on the task's designed hard axes: the per-subject non-canonical HRF, the compressive-exponent / raw-σ size handling, the unannounced motion-spike censoring, and the variance-explained **omit** rule. A reproducible multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a clean pRF pipeline and applies it near-uniformly — it fits the standard linear/canonical-HRF subjects but does not thread each subject's own HRF, honour the compressive exponent and raw-σ size, discover-and-censor the unannounced motion spikes, or omit the low-variance voxels, so the 0.0 is earned on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get many coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the model conventions but never enumerates the pitfalls (the per-subject HRF, the compressive size, the motion spikes, the determinability omit) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted ground truth are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
