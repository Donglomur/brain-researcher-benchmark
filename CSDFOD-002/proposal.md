## CSDFOD-002

**Proposal Title:** Fibre orientation distributions for a heterogeneous diffusion-MRI cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / tractography

**Source paper:** Tournier et al. 2004, *NeuroImage* (spherical deconvolution of the fibre-orientation density, https://doi.org/10.1016/j.neuroimage.2004.07.037); Tournier et al. 2007, *NeuroImage* (non-negativity-constrained super-resolved CSD, https://doi.org/10.1016/j.neuroimage.2007.02.016). Dataset: a **synthetic** diffusion-MRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth FODs held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (produce per-voxel FOD peaks, amplitudes, and the single-fibre response); the difficulty is *execution*, not an un-cued judgement. The agent implements a full constrained-spherical-deconvolution pipeline **from scratch** (no reconstruction library bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with **hidden robustness** requirements, graded voxelwise against a **held-out reference** on **convention-invariant** peak directions and response profiles.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar: the b-value / shell layout differs (b 1000–3000; several subjects are **multi-shell** with a large low-b inner shell, so the FOD must be estimated on the **outermost shell only** — a first-/all-shell pipeline merges the crossings), the gradient scheme differs (20–90 directions → usable even SH order lmax is 4, 6 or 8; a fixed lmax under-fits sparse subjects or merges rich subjects' crossings), and — the biggest lever — the single-fibre **response function is not provided** and must be estimated **per subject** from that subject's own high-FA voxels (a canonical kernel has the wrong anisotropy at every other b-value).
2. **Coupled-physics assembly** — a real orthonormal even-order SH basis, a per-voxel diffusion-tensor fit for the response voxels, the exact spherical-convolution factor, a Laplace-Beltrami-regularised deconvolution, an AFD normalisation, and a peak extractor must **all** be assembled correctly, and errors compound. The 2-fibre crossings sit at the per-subject angular-resolution edge: the correct outermost-shell / per-subject-lmax / per-subject-response pipeline resolves them; a wrong choice merges them.
3. **Hidden robustness** — two failure modes are un-cued and off the stated critical path: a majority of subjects carry a **cluster of grossly corrupted diffusion volumes** (motion spikes / dropouts) that bias the FOD unless detected and rejected, and near-isotropic **grey-matter / CSF voxels must be given no peak** (spurious peaks there fail).
4. **Convention-invariant grading** — peak directions and the normalised response profile R(θ)/R(90°) are basis-invariant (SH-basis conventions cancel); two independent correct implementations reproduce them (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every subject's FOD from the bundled signals with a **held-out reference** pipeline (`csd_pipeline` + `csd_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades over the brain mask across **36 parametrized panels** (9 subjects × {wm_nfib, wm_dirs, iso, resp}); the pytest run returns 0 (reward 1) only if **every** panel passes at ≥90%. wm_nfib = fraction of WM voxels whose reported fibre count matches; wm_dirs = fraction fully correct (count + every reference peak matched within 15°, antipodally); iso = fraction of GM/CSF voxels correctly given no peak; resp = the reported response profile matches within 0.08.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (scipy `sph_harm` real basis, a Legendre-route response, a subdivided-icosahedron peak search, and a 3×-different regularisation weight) reproduces every panel to well within tolerance (per-panel ≥95% of voxels agree; peak-direction median ~2.7°; response max-abs-diff ≤0.012), stable across regenerated noise realizations. The plausible-but-wrong pipelines each fail only their own axis: a **fixed/canonical response** fails resp on 8 of 9 but not the peaks; a **fixed low lmax** merges the tighter crossings; a **first-/all-shell** pipeline wrecks the multi-shell subjects; **ignoring the corrupted volumes** biases the six motion-spiked subjects; **assigning peaks in isotropic voxels** fails iso. The combined naive uniform pipeline fails 20 of 36 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **25/36 panels**, failing the per-subject single-fibre response estimation, the per-subject lmax / outermost-shell selection on the multi-shell subjects, and the unannounced corrupted-volume rejection. |
| **2nd frontier family (Claude/Gemini)** | _pending_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model builds one clean CSD pipeline with a fixed response/lmax/shell and applies it uniformly — it resolves the easy crossings but does not estimate a per-subject response, adapt lmax and the outermost-shell choice, nor discover-and-reject the unannounced corrupted volumes. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the SH algebra, per-subject response, deconvolution, and peak extraction right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the conventions but never enumerates the pitfalls (per-subject response/lmax/shell, the corrupted volumes, the isotropic no-peak rule) — the agent must discover them.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted FODs are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
