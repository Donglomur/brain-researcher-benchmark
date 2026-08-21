## FMRIDENOISE-002

**Proposal Title:** Confound denoising of a heterogeneous resting-state fMRI cohort — cleaned residual + physiological-variance map — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** fMRI preprocessing / confound denoising

**Source paper:** Behzadi et al. 2007, *NeuroImage* (aCompCor, https://doi.org/10.1016/j.neuroimage.2007.04.042); Glover et al. 2000, *MRM* (RETROICOR, https://doi.org/10.1002/1522-2594(200007)44:1<162::AID-MRM23>3.0.CO;2-E); Friston et al. 1996, *MRM* (motion-parameter expansion, https://doi.org/10.1002/mrm.1910350312). Dataset: a **synthetic** resting-state fMRI confound cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (build each subject's nuisance design, regress it out, write the cleaned residual, and the physiological-variance map where determinable); the difficulty is *execution*, not an un-cued judgement. The agent assembles the confound pipeline **from scratch** (no denoiser bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different confound designs**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different confound designs*, discoverable only from each sidecar and the data: some subjects carry a simultaneous physiological phase recording, which adds a **RETROICOR** Fourier block *and* is the only subjects for which the physiological-variance map is defined (for the rest it is not computable and must be **omitted**, like an absent water-reference concentration); TR and run length vary, so the discrete-cosine high-pass set size `K = floor(2·n_vol·TR/128)` changes per subject (a pipeline that hard-codes the drift basis fits almost none).
2. **Coupled-physics assembly** — the Friston-24 motion expansion (with its backward derivative), the TR-dependent cosine high-pass, the top-5 anatomical-CompCor temporal-PC span, and the RETROICOR block must **all** be projected out *jointly*; the physiological-variance map is a nested variance decomposition (residual variance with vs without the RETROICOR block). An error in any one block compounds.
3. **Hidden robustness** — unannounced anywhere: a **majority** (6/8) of subjects carry a handful of grossly motion-corrupted single frames that, left in, **dominate the CompCor PCA** and bias the whole regression. They must be detected as gross outliers and excluded from **both** the component estimation and the fit (exactly like rejecting a corrupted echo before a relaxometry fit).
4. **Convention-invariant grading** — the cleaned residual is the projection onto the orthogonal complement of the confound column space (independent of the CompCor sign/rotation basis, the cosine normalisation, and the regression backend), and physio_var is a difference of projection variances; two independent correct implementations agree to ~1e-6 (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes both outputs from the bundled arrays with a **held-out reference** pipeline (`fd_pipeline` + `fd_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise**. There are **16 (subject × output) panels** (8 subjects × {clean, physio_var}), each its own parametrized test; the Harbor reward is binary (all panels must pass). The cleaned residual is graded over the retained frames and brain-mask voxels (≥90% of entries within rtol 0.02 / atol 0.5); physio_var is graded over the brain mask (≥90% of voxels within rtol 0.05 / atol 2.0) for physio subjects and must be **omitted** for the rest.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (Tukey-fence frame censoring instead of MAD, eigen-decomposition CompCor instead of SVD, QR-orthonormalised cosines, scipy lstsq, ddof=1 variance) reproduces every panel to well within tolerance (cleaned residual max abs diff ~1e-6); the corrupted frames are gross, isolated single-frame excursions any reasonable robust rule flags identically. The plausible-but-wrong pipelines (no frame censoring, no RETROICOR, fixed drift basis, no CompCor, physiological map for all) each fail only their own axis, and the naive uniform pipeline fails a majority (13/16) of panels — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | k=1 | 0.0 | Solved **7/16 panels**; the 9 it missed fall on the hard axes — the un-cued gross-motion single-frame censoring (dominating the CompCor PCA on the 6 motion subjects), the per-subject physiological (RETROICOR) fork and its physio_var omit rule, and the TR-dependent cosine high-pass. Reward 0 because every panel must pass. |
| **2nd frontier family (Claude/Gemini)** | pending | pending | to be run by the maintainer at gate calibration |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model builds a single clean confound pipeline and applies it uniformly — it does not discover-and-censor the unannounced gross-motion frames before the CompCor PCA, nor correctly fork the RETROICOR block and the physio_var omit. The specific failing set is characterised from the task's hard axes (per-panel identities were not logged for this k=1 run); the 9-panel miss is the count the gate recorded and lands on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (assemble a jointly-fit confound design with the right per-subject blocks and robustness, no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable but never enumerates the pitfalls (the gross-motion frames, the physio fork, the TR-dependent drift basis) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted arrays are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
