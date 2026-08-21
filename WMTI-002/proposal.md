## WMTI-002

**Proposal Title:** White-matter-tract-integrity (WMTI) mapping of a heterogeneous diffusion-kurtosis cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure

**Source paper:** Fieremans, Jensen & Helpern 2011, *NeuroImage* (WMTI white-matter two-compartment model, https://doi.org/10.1016/j.neuroimage.2011.06.006); Jensen et al. 2005, *MRM* (diffusional kurtosis imaging). Dataset: a **synthetic** multi-shell diffusion-kurtosis cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the five WMTI parameter maps where the acquisition and model determine them); the difficulty is *execution*. The agent implements the DKI fit and the WMTI inversion **from scratch** (no fitter is bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with **hidden robustness** requirements, graded voxelwise against a **held-out reference**.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each subject's b-values. **Multi-shell** subjects (≥2 non-zero b-values) make the diffusion tensor `D` and the kurtosis tensor `W` both identifiable, so every WMTI map is computable; **single-shell** subjects (one non-zero b-value) leave the kurtosis tensor unidentifiable, so WMTI is undefined and every map must be **omitted** for that subject (like an absent contrast).
2. **Coupled-physics assembly** — the joint 22-parameter log-linear DKI fit, the diffusion-tensor eigen-decomposition, the axial and radial apparent kurtosis, and the branch-selected WMTI closed forms (AWF = Kmax/(Kmax+3); hindered/extra-axonal '+' branch, restricted/intra-axonal '−' branch) must **all** be assembled correctly; an error in any one compounds. Swapping the branch corrupts only Da / De_par / tortuosity while AWF and De_perp stay right.
3. **Hidden robustness** — two off-critical-path axes. The model is valid only in coherent, highly-anisotropic single-fibre white matter: a *majority* of every brain mask is low-anisotropy grey-matter / partial-volume tissue where the two-compartment model is **invalid** and the maps must be left non-finite (writing finite values there fails every multi-shell panel). And a *majority* of the multi-shell subjects carry one-to-three grossly **motion-corrupted volumes** that bias the log-linear tensor fit and must be detected and rejected before fitting. Neither is announced in `instruction.md`.
4. **Convention-invariant grading** — the graded WMTI parameters are uniquely determined by the pinned DKI model and branch convention (voxels where the model is invalid are non-finite in both reference and submission); two independent correct implementations compute them identically (proven below).

### Verifier

`tests/` recomputes every map from the bundled signals with a **held-out reference** pipeline (`wmti_pipeline` + `wmti_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel — 40 panels (8 subjects × {AWF, Da, De_par, De_perp, tortuosity}). A computable panel passes when ≥90% of brain voxels agree — a voxel agrees when it is non-finite in **both** maps (model invalid → undefined) or finite in both within a per-map tolerance (AWF rtol 8%/atol 0.02; Da rtol 8%/atol 0.06; De_par rtol 8%/atol 0.06; De_perp rtol 10%/atol 0.05; tortuosity rtol 12%/atol 0.25). A single-shell subject's panels pass only when the map is **omitted**.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (weighted vs ordinary least squares, sphere-maximum vs analytic radial kurtosis, batch vs one-at-a-time volume rejection; **no** import of the reference) reproduces every computable panel to well within tolerance (worst panel 97% agreement). The plausible-but-wrong pipelines each fail only their own axis: **no shell fork** fails the single-shell omit panels; **no validity mask** (finite values on the invalid low-anisotropy voxels) fails every multi-shell panel; **no outlier rejection** biases only the motion-corrupted subjects; **swapped branch** corrupts only Da / De_par / tortuosity — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **15/40 panels** — failed the hard axes: the multi-shell vs single-shell omit fork (all WMTI maps omitted for a single-shell subject), leaving the invalid low-anisotropy / partial-volume voxels non-finite, rejecting the motion-corrupted volumes before the log-linear DKI fit, and the correct branch selection ('+' / '−') in the WMTI closed forms. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one DKI+WMTI pipeline and applies it uniformly — it produces some correct panels but does not fork on shell count, restrict the maps to the valid single-fibre domain, discover-and-reject the corrupted volumes, or reliably select the WMTI branch. The passing panels show its DKI fit is otherwise correct, so the 0.0 is earned on the genuine hard axes.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional, unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the model conventions but never enumerates the pitfalls (the single-shell omit fork, the validity mask, the corrupted volumes, the branch selection) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
