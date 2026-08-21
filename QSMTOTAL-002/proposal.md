## QSMTOTAL-002

**Proposal Title:** Total quantitative susceptibility mapping (QSM) of a heterogeneous cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / susceptibility mapping

**Source paper:** Wang & Liu 2015, *MRM* (quantitative susceptibility mapping framework and dipole field model, https://doi.org/10.1002/mrm.25358); Bilgic et al. 2014, *MRM* (closed-form L2/Tikhonov-regularised dipole inversion, https://doi.org/10.1002/mrm.25029). Dataset: a **synthetic** QSM cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (produce per-voxel field and total-susceptibility maps); the difficulty is *execution*, not an un-cued judgement. The agent assembles a total-QSM reconstruction **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. **Field estimation** diverges: most subjects are **multi-echo**, where the local frequency is the free-intercept slope of the phase-vs-TE line (a spatially-varying receiver-phase offset makes a through-origin fit biased); two subjects are **single-echo**, where there is no intercept degree of freedom and the field is the direct phase/(2π·TE). The **referencing forks**: the inversion has a null DC term, so subjects **with a CSF reference ROI** report CSF-referenced absolute susceptibility (chi_abs) and must **omit** chi_rel, while subjects **without one** report whole-brain-referenced relative susceptibility (chi_rel) and must **omit** chi_abs.
2. **Coupled-physics assembly** — the Hz→ppm conversion uses the per-subject f0 (3T vs 7T; a fixed f0 biases the 7T subjects); the **dipole inversion** is a pinned closed-form Tikhonov k-space operator (fixed λ + Lorentz kernel, B0 the last axis) — unique only because it is pinned, and a naive thresholded k-space division streaks; the reference offset is the **median** over the reference region (vessels / calcification / choroid-plexus partial-volume contaminate a plain mean). Errors compound across panels.
3. **Hidden robustness** — a majority of the multi-echo subjects carry one grossly corrupted echo volume (spatially-varying motion/wrap error on an off-centre echo) that must be **rejected** before the field fit, or the field is biased; never announced in `instruction.md`.
4. **Convention-invariant grading** — the dipole operator, λ, and the median reference are pinned, so the graded susceptibility is uniquely determined; two independent correct implementations compute it identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled phase with a **held-out reference** pipeline (`qsm_pipeline` + `qsm_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask eroded by one voxel, one parametrized test per (subject × map) panel — **24 panels** in all; the **binary** reward is 1 only when all pass. A computable map (field for every subject; chi_abs for CSF-referenced subjects; chi_rel for whole-brain-referenced subjects) passes when ≥90% of brain voxels agree within (rtol 8%, atol 0.008 ppm); an unsupported map (chi_rel for a CSF subject, chi_abs for a whole-brain subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (scipy vs numpy FFT, batch sigma-clip vs one-at-a-time echo rejection, sigma-clip-median vs plain-median reference) reproduces every panel to a worst-case 0.0017 ppm (well within tolerance). The plausible-but-wrong pipelines each fail only their own axis: **no echo rejection**, a **through-origin fit**, a **fixed f0**, a **whole-brain reference for all**, a **plain-mean offset**, or a **thresholded k-space division** each corrupt only the panels on their own axis — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **15/24 panels**, failing the free-intercept multi-echo field fit with unannounced corrupted-echo rejection, the pinned Tikhonov dipole inversion, and the CSF-vs-whole-brain referencing fork (median offset, chi_abs/chi_rel omit). |
| **2nd frontier family (Claude/Gemini)** | _pending_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model assembles one clean QSM pipeline and applies it uniformly — it does not discover-and-reject the unannounced corrupted echoes, thread the per-subject field/f0/inversion conventions, nor honour the CSF-vs-whole-brain referencing fork with its median offset. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the coupled field-mapping, dipole inversion, and referencing right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the conventions but never enumerates the pitfalls (the multi/single-echo fork, the corrupted echo, the referencing fork) — the agent must discover them.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
