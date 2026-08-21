## GLUCOCEST-002

**Proposal Title:** Dynamic glucose-enhanced (DGE) CEST quantification of a heterogeneous cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Molecular MRI / chemical-exchange saturation transfer (CEST)

**Source paper:** Walker-Samuel et al. 2013, *Nature Medicine* (glucoCEST, https://doi.org/10.1038/nm.3252); Xu et al. 2015, *Tomography* (dynamic glucose-enhanced / DGE MRI); Kim et al. 2009, *MRM* (WASSR B0 correction of CEST Z-spectra, https://doi.org/10.1002/mrm.21873). Dataset: a **synthetic** dynamic Z-spectrum time-series cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the dynamic glucoCEST AUC and initial uptake rate maps); the difficulty is *execution*. The agent implements the DGE-CEST quantification **from scratch** (no reconstruction library is bundled), over a **heterogeneous cohort of Z-spectrum time series where subjects need fundamentally different handling**, with **hidden robustness** requirements, graded voxelwise against a **held-out reference** on **convention-invariant** (temporal-difference) quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different handling*, discoverable only from the data: the scanner centre frequency **drifts** over the dynamic series on a *majority* of subjects, so the whole Z-spectrum slides along the offset axis with time and must be re-referenced to the water resonance **per timepoint** (a single static B0 correction reads the drift as spurious glucose uptake); some subjects have a **drifting pre-infusion baseline** whose trend must be removed (a constant-mean baseline leaves the drift as false enhancement); a couple of subjects have too few post-infusion dynamics for the initial uptake rate to be determinable, so the rate map must be **omitted** (like a water-reference-absent absolute concentration).
2. **Coupled-physics assembly** — the per-timepoint water referencing, the glucose-band CEST integral on the corrected axis, the gross-frame rejection, the baseline detrend, and the AUC / OLS-slope must **all** be assembled correctly; an error in any one compounds.
3. **Hidden robustness** — a minority of subjects carry one or two grossly **motion-corrupted** post-infusion dynamic frames whose glucose-band signal is a gross temporal outlier that must be rejected and repaired (temporal interpolation) *before* the AUC and rate, not integrated. This is never announced in `instruction.md`.
4. **Convention-invariant grading** — the graded quantities are **dynamic** (a temporal difference of the glucose-band integral), so the per-voxel static water-dip / interpolation bias cancels and the AUC / rate are convention-invariant; two independent correct implementations compute them identically (proven below).

### Verifier

`tests/` recomputes both maps from the bundled Z-spectra with a **held-out reference** pipeline (`glucocest_pipeline` + `glucocest_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel — 16 panels in all. A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (auc rtol 12%/atol 0.010 ppm·min; rate rtol 15%/atol 0.0010 ppm/min); an unsupported map (rate for a short post-infusion series) passes only when the submission **omits** it. The gate delivers a binary reward (all panels pass → 1.0).

**Grading-invariance proof (the key check).** Because the graded quantities are temporal differences, a genuinely-correct independent implementation (parabola vs dense-spline water referencing, per-voxel vs global drift correction, cubic vs pchip/linear interpolation, one-at-a-time vs batch frame rejection, linear vs quadratic baseline detrend; **no** import of the reference) reproduces every computable panel to well within tolerance. The plausible-but-wrong pipelines each fail only their own axis: **single static B0 / no drift tracking** biases only the drift subjects; a **constant-mean baseline** biases only the drift-baseline subjects; **no motion-frame rejection** biases only the motion subjects; **rate computed everywhere** fails only the omit panels — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=3** | **0.0 (all 3)** | Solved **5/16 panels** — failed the hard axes on every run: the per-timepoint B0-drift re-referencing (a majority of subjects), the drifting pre-infusion baseline detrend, rejection + temporal repair of the grossly motion-corrupted frames, and the rate omit rule for the short post-infusion series. A reproducible multi-axis execution failure (confirmed reward 0 across k=3). |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol across k=3; hypothesis for the 2nd family):** the model applies a single static B0 correction and a constant baseline uniformly — it handles the drift-free, motion-clean subjects but reads the per-timepoint frequency drift and the baseline trend as spurious glucose enhancement and does not discover-and-repair the corrupted frames. The passing panels show its band integral is otherwise correct, so the 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional, unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the per-timepoint drift, the baseline trend, the corrupted frames, the rate omit rule) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
