## IVIM-002

**Proposal Title:** Intravoxel incoherent motion (IVIM) fitting of a heterogeneous diffusion cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / IVIM

**Source paper:** Le Bihan et al. 1988, *Radiology* (Separation of diffusion and perfusion in intravoxel incoherent motion MR imaging, https://doi.org/10.1148/radiology.168.2.3393671); Le Bihan et al. 1986, *Radiology* (MR imaging of intravoxel incoherent motions, https://doi.org/10.1148/radiology.161.2.3763909). Dataset: a **synthetic** IVIM diffusion cohort (8 subjects, differing b-value schemes), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth parameter maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the IVIM parameter maps `D`, `f`, `D*` where determinable); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the IVIM inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where the b-scheme decides which parameters are even determinable**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the subjects' b-value *schemes* decide which parameters are determinable, discoverable only from each sidecar's b-values (never labelled). Three tiers coexist: **FULL** exams (b=0 + low-b + high-b) support all of `D`, `f`, `D*`; **FD** exams (b=0 + high-b, no low-b) support `D` and `f` but **not** `D*` (a forced segmented `D*` step gives a spurious value, so it must be **omitted**); **MONO** exams (high-b only, no b=0) support only `D` (with no non-diffusion-weighted reference, `f` and `D*` are not separable and must be **omitted**). Emitting a map the scheme cannot support, or omitting one it can, is scored wrong — like a water-reference-absent absolute concentration.
2. **Coupled-physics assembly** — the physics chains together: the robust high-b mono-exponential slope (`D`), the b=0 extrapolated intercept it produces (which with the acquired `S(b=0)` gives `f = 1 − S_int/S(b=0)`), and the low-b perfusion residual (`D*`) are coupled, so an error in the `D` fit propagates into `f` and `D*`.
3. **Hidden robustness** — a *majority* of subjects (6 of 8) carry one or two grossly corrupted high-b diffusion volumes (a whole DWI frame scaled by a gross motion/dropout factor) that must be **rejected** before the high-b log-linear fit; a non-robust fit biases `D` and, through the extrapolated intercept, `f`. This is never announced.
4. **Convention-invariant grading** — `D` is the well-determined, method-invariant tissue diffusivity, and `f` is graded at a moderate band chosen so a genuinely different fitting paradigm (a full biexponential NLLS) still passes; two independent correct implementations agree — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled diffusion signals with a **held-out reference** pipeline (`ivim_pipeline` + `ivim_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map). Reward is binary (all 24 panels must pass). `D` is graded strictly (rtol 12%, atol 1.5e-4; PASS_FRAC 0.82); `f` at a moderate band (rtol 30%, atol 0.06; PASS_FRAC 0.80); the omit panels (`f` with no b=0; `D*` with no low-b) strictly (the submission must write no file); `D*` where determinable only loosely (present, positive, physically-plausible median) because it is intrinsically ill-conditioned.

**Grading-invariance proof (the key check).** Two genuinely-independent implementations — a different-code segmented fit **and** a full per-voxel biexponential NLLS — both reproduce every graded panel. The plausible-but-wrong pipelines each fail only their own axis: **compute f/D\* everywhere** or **mono-only everywhere** fails the omit panels; **skip the gross-volume rejection** biases `D`/`f` only on the corrupted subjects — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **11/24 panels**, failing the genuine hard axes — the b-scheme omit forks (`f` where there is no b=0, `D*` where there is no low-b) and the unannounced gross-volume rejection that biases `D`/`f` on the corrupted-volume majority. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one clean IVIM fit and applies it uniformly — it does not adapt the map set to each subject's b-scheme (over- or under-computing `f`/`D*`), nor discover-and-reject the unannounced corrupted high-b volumes. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (classify the b-scheme, adapt the map set, run a robust chained fit — with no bundled fitter), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the model but never enumerates the pitfalls (the omit forks, the corrupted volumes) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
