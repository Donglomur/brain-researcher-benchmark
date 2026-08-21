## MWFEPG-002

**Proposal Title:** Myelin water fraction from an EPG-corrected multi-echo-T2 cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / relaxometry

**Source paper:** Prasloski et al. 2012, *MRM* (stimulated-echo (EPG) correction for multicomponent T2 / myelin-water analysis, https://doi.org/10.1002/mrm.23157); MacKay et al. 1994, *MRM* (in-vivo myelin-water imaging, https://doi.org/10.1002/mrm.1910310614). Dataset: a **synthetic** multi-echo spin-echo (CPMG) cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (produce per-voxel MWF and, where supported, gmT2); the difficulty is *execution*, not an un-cued judgement. The agent implements an EPG-corrected myelin-water inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar: **many-echo** subjects (32 echoes) support the full regularized T2 spectrum and report **MWF + gmT2**; **few-echo** subjects (8 echoes) cannot resolve a spectrum and must instead be fit with the pinned **3-pool model**, reporting **MWF and omitting** the spectrum-derived gmT2. A uniform recipe is wrong on one fork.
2. **Coupled-physics assembly** — the CPMG echo train is **non-mono-exponential** because the refocusing flip departs from 180° (nominal <180° for most subjects, times a per-voxel B1 transmit map), so the per-T2 basis must be the **extended-phase-graph (EPG) stimulated-echo amplitude** at the true flip α = B1·nominal (a plain exp(−TE/T2) basis biases MWF on every non-180° subject); the ill-posed spectrum is recovered by a pinned **first-derivative-regularized non-negative least squares** (fixed μ=1.5) on a pinned log-spaced grid; MWF is the short-T2 (≤40 ms) fraction and gmT2 the amplitude-weighted geometric-mean T2 over the intra/extra-cellular window. Errors compound.
3. **Hidden robustness** — a majority of subjects carry one or two grossly motion-corrupted echo volumes that must be **detected and rejected** before the fit, or the whole spectrum (and thus MWF and gmT2) is wrong; never announced in `instruction.md`.
4. **Convention-invariant grading** — the regularized fit is strictly convex and the flip is supplied, so MWF and gmT2 are uniquely determined; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled signal with a **held-out reference** pipeline (`mwf_pipeline` + `mwf_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel — **16 panels** in all. Reward is **fractional** (each panel its own test). A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (MWF rtol 8%/atol 0.02; gmT2 rtol 6%/atol 4 ms); an unsupported map (gmT2 for a few-echo subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (an isochromat Bloch simulation of the echo train instead of the EPG recursion, a bounded-variable-least-squares solver instead of Lawson-Hanson NNLS, and a batch sigma-clip echo rejection) reproduces every computable panel to a median voxel difference below 1e-8 in MWF. The plausible-but-wrong pipelines each fail only their own axis: **ignore the EPG correction** fails only the low-flip subjects; a **minimum-norm regularizer** fails the many-echo spectra; **forcing a spectrum / emitting gmT2** on a few-echo subject fails the omit rule; a **non-robust fit** fails only the motion-corrupted subjects — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **8/16 panels**, failing the EPG stimulated-echo basis at the true (B1×nominal) flip, the first-derivative-regularized NNLS spectrum, the few-echo 3-pool / gmT2-omit fork, and the unannounced corrupted-echo rejection. |
| **2nd frontier family (Claude/Gemini)** | _pending_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model builds one clean MWF pipeline and applies it uniformly — it does not thread the EPG flip correction, use the pinned first-derivative regularizer, fork to the 3-pool model with gmT2 omitted, nor discover-and-reject the unannounced corrupted echoes. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the spin physics, regularized inversion, and per-subject forks right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the conventions but never enumerates the pitfalls (the EPG flip, the many/few-echo fork, the corrupted echoes) — the agent must discover them.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
