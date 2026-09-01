## CSDFOD-002

**Proposal Title:** Fibre orientation distributions for a heterogeneous diffusion-MRI cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + declared robustness with hidden realization)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / tractography

**Source paper:** Tournier et al. 2004, *NeuroImage* (spherical deconvolution of the fibre-orientation density, https://doi.org/10.1016/j.neuroimage.2004.07.037); Tournier et al. 2007, *NeuroImage* (non-negativity-constrained super-resolved CSD, https://doi.org/10.1016/j.neuroimage.2007.02.016). Dataset: a **paper-parameterized** diffusion-MRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; the true fibre geometry is held out for grading under `tests/planted_truth.npz` (the reference run on the noise-free signal, built by `synth_build/build_truth.py`).

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (produce per-voxel FOD peaks, amplitudes, and the single-fibre response); the difficulty is *execution*, not an un-cued judgement. The agent implements a full constrained-spherical-deconvolution pipeline **from scratch** (no reconstruction library bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **publicly-declared robustness** requirement (the corrupted-volume realization hidden), graded voxelwise against the **planted physiology** on **convention-invariant** peak directions and response profiles.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar: the b-value / shell layout differs (b 1000–3000; several subjects are **multi-shell** with a large low-b inner shell, so the FOD must be estimated on the **outermost shell only** — a first-/all-shell pipeline merges the crossings), the gradient scheme differs (20–90 directions → usable even SH order lmax is 4, 6 or 8; a fixed lmax under-fits sparse subjects or merges rich subjects' crossings), and — the biggest lever — the single-fibre **response function is not provided** and must be estimated **per subject** from that subject's own high-FA voxels (a canonical kernel has the wrong anisotropy at every other b-value).
2. **Coupled-physics assembly** — a real orthonormal even-order SH basis, a per-voxel diffusion-tensor fit for the response voxels, the exact spherical-convolution factor, a Laplace-Beltrami-regularised deconvolution, an AFD normalisation, and a peak extractor must **all** be assembled correctly, and errors compound. The 2-fibre crossings sit at the per-subject angular-resolution edge: the correct outermost-shell / per-subject-lmax / per-subject-response pipeline resolves them; a wrong choice merges them.
3. **Declared robustness, hidden realization** — a majority of subjects carry a **cluster of grossly corrupted diffusion volumes** (motion spikes / dropouts) that bias the FOD unless detected and rejected; `instruction.md` now declares this and only *which* subjects/volumes remains hidden. Off the critical path, near-isotropic **grey-matter / CSF voxels must be given no peak** (spurious peaks there fail).
4. **Convention-invariant grading** — peak directions and the normalised response profile R(θ)/R(90°) are basis-invariant (SH-basis conventions cancel); two independent correct implementations reproduce them, so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### What changed in this revision (addressing the review of the hidden-reference grading)

1. **Robustness contract made public.** `instruction.md` now states, under *Robustness / data-quality contract*, that a majority of subjects carry grossly corrupted DW volumes that must be detected and rejected robustly — only the *realization* (which subjects/volumes) is hidden. A correct fit of the stated model is no longer penalized for failing to guess an undeclared step.
2. **Graded against the true physiology, not one fitter.** The verifier no longer recomputes with a private pipeline on the real data and demands agreement. It compares each submitted FOD, voxelwise, to the **held-out planted target** = the CSD/FOD reference run on the **noise-free, corruption-free** signal (`tests/planted_truth.npz`, built by `synth_build/build_truth.py`) — the physical peak directions, per-voxel counts, and single-fibre response the acquisition supports. The graded voxel populations are defined by that planted result (fibre vs isotropic), exactly as before but frozen. **Any valid estimator** applied to the real data recovers it within tolerance. The hidden reference modules (`csd_pipeline.py`, `csd_ref.py`) were removed from `tests/` (the oracle's copies under `solution/` remain).

### Verifier

`tests/test_outputs.py` grades against `tests/planted_truth.npz` over the brain mask across **36 parametrized panels** (9 subjects × {wm_nfib, wm_dirs, iso, resp}); the pytest run returns 0 (reward 1) only if **every** panel passes at ≥90%. wm_nfib = fraction of fibre voxels whose reported fibre count matches the planted count; wm_dirs = fraction fully correct (count + every planted peak matched within 15°, antipodally); iso = fraction of isotropic voxels correctly given no peak; resp = the reported response profile matches within 0.08.

**Validity / discrimination evidence (recomputed for this revision).** The oracle recovers the planted target on **all 36 panels** — wm_nfib/wm_dirs/iso at **100 %** of the graded voxels for all nine subjects, and the response profile to within a max-abs-diff of **0.049** (< 0.08). A **naive fit that skips the gross-volume rejection fails 17 panels** (wm_nfib/wm_dirs and some resp on the corrupted subjects; the clean subjects still pass). So a from-scratch correct solver passes and the no-rejection shortcut fails, on an axis the instruction *declares*.

### Difficulty — frontier gate

Oracle **reward 1.0**, in-container (deterministic).

On the *previous* (hidden-contract) version, **gpt-5.6-sol (codex, xhigh) scored 0.0**, solving 25/36 panels — failing the per-subject single-fibre response estimation, the per-subject lmax / outermost-shell selection on the multi-shell subjects, and the corrupted-volume rejection.

**Frontier re-gate on this revised (public-contract) version: PENDING.** Because the revision *discloses* the corrupted-volume robustness requirement, the old gate number does not transfer and must be re-measured — not overclaimed here. The expectation is that the multi-axis assembly remains hard (per-subject response/lmax/outermost-shell, the SH algebra + deconvolution + peak extraction, the isotropic no-peak rule, and discover-and-reject the hidden corrupted volumes); the local discrimination above shows the no-rejection shortcut still fails. A 2nd frontier family (Claude/Gemini) gate is likewise pending at maintainer calibration.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the SH algebra, per-subject response, deconvolution, and peak extraction right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the conventions but never enumerates the pitfalls (per-subject response/lmax/shell, the corrupted volumes, the isotropic no-peak rule) — the agent must discover them.
- **Data.** Paper-parameterized, small, deterministic, and **leakage-clean** (the planted truth lives only in `tests/planted_truth.npz`, never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py` + `synth_build/build_truth.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
