## MSMTCSD-002

**Proposal Title:** Multi-shell multi-tissue spherical deconvolution of a heterogeneous dMRI cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure (multi-tissue spherical deconvolution)

**Source paper:** Jeurissen et al. 2014, *NeuroImage* (multi-tissue constrained spherical deconvolution for multi-shell dMRI, https://doi.org/10.1016/j.neuroimage.2014.07.061); Tournier et al. 2007, *NeuroImage* (constrained spherical deconvolution, https://doi.org/10.1016/j.neuroimage.2007.02.016). Dataset: a **synthetic** multi-shell multi-tissue dMRI cohort (8 subjects), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth FODs and fractions held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (per-voxel WM/GM/CSF tissue signal fractions + WM-FOD peaks from the pinned responses); the difficulty is *execution*, not an un-cued judgement. The agent implements MSMT-CSD **from scratch** (no `dwi2fod` / dipy bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** fractions and peak directions.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar: subjects with **three or more distinct b-values** (b0 + two/three DW shells) can separate three tissues (WM FOD + GM + CSF signal fractions), while subjects with **only two distinct b-values** (b0 + a single DW shell) cannot separate grey matter — the fit is 2-tissue (WM + CSF) and the GM fraction is **not computable** and must be **omitted**. The usable spherical-harmonic `lmax` adapts to each subject's outer-shell direction count. A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — a real orthonormal even-order SH basis, the per-shell zonal convolution of the FOD with the **pinned** WM response, the isotropic GM/CSF response columns, the Laplace–Beltrami-regularised deconvolution, the spherical-mean (powder) tissue unmixing, and non-negativity must **all** be assembled correctly; an error in any one compounds across the 40 (subject × panel) panels.
3. **Hidden robustness** — two off-critical-path requirements are un-announced: a **majority (5 of 8)** subjects carry one to three grossly motion-corrupted DW volumes that must be detected and rejected (gross MAD-outliers of the per-shell log-signal SH residual) before the spherical mean and the FOD are trustworthy; and the tissue amounts must be constrained **non-negative** (a plain least-squares unmixing goes negative in near-pure-CSF voxels). Neither is flagged in `instruction.md`.
4. **Convention-invariant grading** — the tissue fractions are the spherical-mean decomposition into the pinned responses (no SH normalisation, no reporting convention) and peak **directions** are invariant to the SH basis and FOD scale, so two independent correct implementations agree (proven below) — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every quantity from the bundled multi-shell signals with a **held-out reference** pipeline (`msmt_pipeline` + `msmt_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask. There are 40 parametrized (subject × panel) sub-tests — 8 subjects × {wm_frac, gm_frac, csf_frac, peaks, iso}; the binary Harbor reward (pytest rc) requires all to pass. A computable fraction passes at ≥90% agreement within (rtol 0.10, atol 0.03); gm_frac for a two-distinct-b subject passes only when **omitted**; the peaks panel passes when ≥90% of the reference's fibre voxels have the right WM-FOD peak count and directions within 15°; the iso panel passes when ≥90% of the reference's isotropic voxels are assigned **no** peak.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation — different SH assembly, an SH-l0 spherical mean, an analytic non-negative solve, and a different dense sphere and peak search — reproduces every panel to well within tolerance (fractions matched to 1e-4; peak directions to ~3°). The plausible-but-wrong pipelines each fail only their own axis: **always 3-tissue** violates the omit rule and biases WM/CSF on two-shell subjects; **no corrupted-volume rejection** biases only the corrupted subjects; **no non-negativity** biases only the pure-tissue voxels; a **wrong/estimated response** biases the fractions everywhere — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **17/40 panels** — a majority (23/40) failed. The model does not fully assemble the WM-FOD deconvolution/peak extraction, the un-announced corrupted-volume rejection, non-negativity, and the 2-vs-3-tissue GM-omit fork; the binary Harbor reward zeroes on any failed panel. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model gets a subset of the tissue-fraction panels but does not correctly build and deconvolve the FOD to recover peaks/iso, does not discover-and-reject the corrupted DW volumes, and does not thread the 2-vs-3-tissue omit fork — so it clears only 17/40. A clean, reproducible multi-axis execution failure on the genuine hard axes.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (assemble the SH deconvolution, robust volume rejection, non-negative unmixing, and omit forks with no bundled library), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the pinned responses/conventions but never flags the corrupted volumes or the non-negativity requirement — the agent must discover them.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted fields are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
