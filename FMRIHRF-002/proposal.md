## FMRIHRF-002

**Proposal Title:** Voxelwise HRF estimation from a heterogeneous event-related fMRI cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Functional MRI analysis

**Source paper:** Glover 1999, *NeuroImage*, "Deconvolution of impulse response in event-related BOLD fMRI" (https://doi.org/10.1006/nimg.1998.0419); Dale 1999, *Human Brain Mapping*, "Optimal experimental design for event-related fMRI." Dataset: a **synthetic** single-run event-related fMRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth response curves held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (estimate the per-voxel evoked haemodynamic response and write out its shape summaries); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the FIR deconvolution and curve summaries **from scratch** (no fitter bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each design: some subjects are well-spaced jittered event-related runs whose voxelwise FIR haemodynamic response is identifiable (report amplitude + time-to-peak + FWHM read from the estimated response curve), and others are rapid, near-collinear fixed-interval runs where the FIR columns are nearly linearly dependent (condition number in the tens) so the **shape is not identifiable** and must be **omitted** — only the canonical-GLM response amplitude is reportable there (like MTsat where there is no MT contrast). TR differs per subject (0.8–1.5 s), so the FIR grid and the onset-to-frame mapping change subject to subject; a pipeline that hardcodes one TR misplaces every onset on the off-TR subjects.
2. **Coupled-physics assembly** — the percent-BOLD conversion, the low-frequency drift model, the FIR deconvolution, the identifiability decision, and the convention-invariant curve summaries (peak / time-to-peak / FWHM) must **all** be assembled correctly; an error in any one compounds into every shape map.
3. **Hidden robustness** — a **majority** of subjects carry a few grossly motion-spiked frames that must be detected and censored (or modelled) before the fit, or the low-amplitude voxels are fit to spurious responses; this robustness is **not announced** in `instruction.md`.
4. **Convention-invariant grading** — amplitude, time-to-peak and FWHM are read from the estimated response *curve* and are uniquely determined given the pinned FIR recipe and canonical HRF, so two independent correct implementations compute them identically (proven below); a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled run with a **held-out reference** pipeline (`hrf_pipeline` + `hrf_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the mask, one parametrized test per (subject × map) panel. A computable map passes when ≥90% of mask voxels agree within a per-map tolerance (amplitude rtol 10% / atol 0.15 percent-BOLD; ttp atol 1.25 s; fwhm atol 1.5 s); an unsupported map (ttp / fwhm where the rapid design does not identify the shape) passes only when the submission **omits** it. Reward is fractional across the 24 (subject × map) panels.

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (Toeplitz FIR construction, scipy `gelsd` solve, polynomial drift, global-signal spike detection, parabolic-interpolated peak summaries, a different condition-number threshold — no import of the reference) reproduces every computable panel to well within tolerance (median time-to-peak agreement ~0.1 s). The plausible-but-wrong pipelines each fail only their own axis: **report shape everywhere** or **canonical amplitude everywhere** fails the omit rule; **no spike censoring** biases only the spiked subjects' low-amplitude voxels; **no drift** and **fixed TR** each fail only their own panels; a naive uniform FIR-everywhere-no-censoring pipeline fails a majority (18 of 24) of the panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **15/24 panels**, failing the hard axes: the identifiability decision (omitting ttp/fwhm on the rapid near-collinear designs vs reporting them where the shape is estimable), the unannounced motion-spike censoring on the majority of subjects, and/or the per-subject TR handling on the off-TR runs. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean FIR pipeline and applies it uniformly — it handles the amplitude panels but does not correctly thread the per-design identifiability fork nor discover-and-censor the unannounced motion-spiked frames. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the units, timing, deconvolution, and per-subject adaptation right with no bundled fitter), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the FIR/identifiability conventions but never enumerates the pitfalls (the per-subject TR, the corrupted frames, the shape-omit fork) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`; verified by grep). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
