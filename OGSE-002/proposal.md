## OGSE-002

**Proposal Title:** Frequency-dependent diffusion (OGSE) of a heterogeneous diffusion cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure

**Source paper:** Does, Parsons & Gore 2003, *MRM* (Oscillating gradient measurements of water diffusion in normal and globally ischemic rat brain, https://doi.org/10.1002/mrm.10508); Gore et al. 2010, *NMR in Biomedicine* (temporal diffusion spectroscopy / frequency-dependent diffusion, https://doi.org/10.1002/nbm.1509). Dataset: a **synthetic** OGSE/PGSE diffusion cohort (8 subjects, one or more diffusion-encoding frequency shells each), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the zero-frequency diffusivity `D_ref`, and the dispersion slope `beta` where determinable); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the OGSE inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need different computations, discoverable only from each sidecar: five subjects sample several diffusion-encoding frequencies (the linear dispersion slope `beta = dD/df` is identifiable and must be produced) while three are single-frequency / PGSE-only, where `beta` is **not** identifiable and must be **omitted** (its column is degenerate — like a water-reference-absent absolute concentration). Emitting `beta` for a single-frequency subject, or omitting it for a multi-frequency one, is scored wrong.
2. **Coupled-physics assembly** — every frequency shell carries its **own echo time** (higher OGSE frequency → longer TE → more T2 attenuation → a different non-diffusion-weighted baseline *and* lower SNR), so each shell needs a **separate `S0` intercept**; a single global baseline lets the TE-driven, frequency-correlated offset leak into the dispersion and biases `D0`/`beta` on every multi-frequency subject. The per-shell-intercept joint log-linear fit (or the equivalent two-stage per-frequency-ADC-then-line fit), the outlier rejection, and the omit decision must all be assembled correctly.
3. **Hidden robustness** — a *majority* of the cohort (5 of 8) carries one or two grossly motion-corrupted diffusion volumes (signal dropout / spike) that must be **detected** and rejected before the fit; this robustness requirement is never stated in the instruction.
4. **Convention-invariant grading** — `D_ref` (D0) and `beta` are the fitted asymptotes on the pinned model; a genuinely different route (two-stage per-frequency-ADC-then-line with robust rejection) reproduces them, so two independent correct implementations agree — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled signals with a **held-out reference** pipeline (`ogse_pipeline` + `ogse_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain-tissue mask, one parametrized subtest per (subject × map); the authoritative reward is binary (all 16 panels must pass). A computable map passes when ≥90% of brain-tissue voxels agree within a per-map tolerance (`D_ref` rtol 6%/atol 0.03; `beta` rtol 12%/atol 0.00035); an unsupported map (`beta` for a single-frequency subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (a two-stage per-frequency-ADC-then-line fit with Theil-Sen robust rejection; **no** shared code with the reference) reproduces every computable panel to well within tolerance — machine precision on the balanced no-drop subjects, ~0.1% (`D_ref`) / ~1–2% (`beta`) on the drop subjects. The plausible-but-wrong pipelines each fail only their own axis: **single global baseline** biases `D0`/`beta` on the multi-frequency subjects; **no outlier rejection** biases only the drop subjects; **beta emitted for all** fails the omit panels — and a naive uniform pipeline fails 14 of the 16 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **9/16 panels**, failing the genuine hard axes — the per-shell TE-driven baselines (a global baseline biases the dispersion), the unannounced gross-volume rejection, and the single-vs-multi-frequency `beta` omit rule. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one clean OGSE fit and applies it uniformly — it uses a single global baseline (leaking the TE-correlated offset into the dispersion), does not discover-and-reject the corrupted volumes, and does not honour the `beta` omit fork. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (group shells, fit with per-shell intercepts, reject gross volumes, and decide the `beta` omit — with no bundled fitter), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the model but never enumerates the pitfalls (the per-shell TE baselines, the corrupted volumes) beyond pinning the estimator — the agent must discover the robustness axis from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
