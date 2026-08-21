## T1WT2W-002

**Proposal Title:** T1w/T2w myelin-proxy mapping across a heterogeneous cohort — an execution-hard reconstruction task (convention removal + coupled-bias assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / myelin mapping

**Source paper:** Glasser & Van Essen 2011, *J. Neurosci.* (T1w/T2w myelin mapping, https://doi.org/10.1523/JNEUROSCI.2180-11.2011); Ganzetti et al. 2014, *Front. Hum. Neurosci.* (T1w/T2w intensity calibration / normalization). Dataset: a **synthetic** coregistered T1w+T2w cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the convention-invariant T1w/T2w myelin proxy, WM-referenced and, where determinable, affine-calibrated); the difficulty is *execution*. The agent derives the readouts **from scratch** (no reference tool is bundled), over a **heterogeneous cohort where subjects need different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence / convention removal** — the natural readout carries an arbitrary per-subject scanner-scale convention that must be removed. The two weighted images share the receive-coil field, which cancels in the ratio, leaving `raw_ratio = k · M_true · rho` with `k` an arbitrary per-subject constant (independent receive gains) and `rho` a residual multiplicative bias that does **not** cancel and must be divided out. Two convention-invariant readouts remove `k`: the WM-referenced ratio and the 2-landmark affine calibration — and the affine one is determinable **only** when both landmark ROIs are usable; a *minority* of subjects have an empty low-myelin landmark, where `myelin_cal` is not computable and must be **omitted** (like a water-reference-absent absolute concentration).
2. **Coupled-bias assembly** — the residual-bias division threads through **both** the output map and the region means (`R_corr = (T1w/T2w)/rho`; do **not** bias-correct the two images separately, since the shared receive field already cancels in the ratio). An error in the bias handling, the robust region mean, or the omit decision corrupts a different subset of the (subject × map) panels.
3. **Hidden robustness** — gross T2w drop-out voxels (susceptibility / edge / CSF partial-volume; corrected ratio ~100× physiological) sit **inside** the white-matter reference and the high-myelin landmark ROI, so a plain non-robust region mean is dragged upward and the *whole* normalization / calibration scale is wrong. They must be excluded before averaging even though the instruction never mentions them.
4. **Convention-invariant grading** — because `raw_ratio = k · M_true · rho` with `rho` provided, both readouts equal a fixed function of the true anatomy and the fixed targets, independent of `k`; two independent correct implementations compute them identically (proven below).

### Verifier

`tests/` recomputes every map from the bundled T1w/T2w images with a **held-out reference** pipeline (`t1t2_pipeline` + `t1t2_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel — 16 panels in all. A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (rtol 5%, atol 0.03 for both `myelin_norm` and `myelin_cal`); an unsupported map (`myelin_cal` where a landmark ROI is unusable) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** Convention-invariance is real: because `raw_ratio = k · M_true · rho` with `rho` provided, both readouts equal a fixed function of the true anatomy and the fixed targets, independent of `k` — a genuinely-correct independent implementation (different linear algebra, a different gross-outlier rule, an explicit 2-point affine solve; **no** import of the reference) reproduces every computable panel to well within tolerance (max median relative error ~1e-6). The plausible-but-wrong pipelines each fail only their own axis: **ignore the bias field** biases both maps only on the residual-bias subjects; a **plain non-robust region mean** biases both maps only on the drop-out subjects; **calibrate every subject** violates the omit rule only on the no-low-landmark subjects — and a naive pipeline combining the flaws fails a majority of panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **8/16 panels** — failed the hard axes: dividing out the residual multiplicative bias `rho` (rather than bias-correcting the images separately), robustly excluding the ~100× T2w drop-out voxels from the WM reference and the high-myelin landmark, and the `myelin_cal` omit rule when a landmark ROI is empty. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model computes a plausible normalized ratio but does not correctly remove the residual bias through both the map and the region means, discover-and-exclude the drop-out voxels contaminating the reference, or omit `myelin_cal` where a landmark is unusable. The passing panels show its core ratio/normalization is otherwise correct, so the 0.0 is earned on the genuine hard axes.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional, unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the ratio model but never enumerates the pitfalls (the residual-bias division, the drop-out contamination, the calibration omit rule) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
