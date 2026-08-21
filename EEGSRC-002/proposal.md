## EEGSRC-002

**Proposal Title:** dSPM noise-normalised minimum-norm source reconstruction of a heterogeneous EEG cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** EEG source reconstruction / distributed inverse problem

**Source paper:** Dale et al. 2000, *Neuron* (dynamic statistical parametric mapping / dSPM, https://doi.org/10.1016/S0896-6273(00)81138-1); Hämäläinen & Ilmoniemi 1994, *Med. Biol. Eng. Comput.* (minimum-norm estimate, https://doi.org/10.1007/BF02512476). Dataset: a **synthetic** EEG evoked-response cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth source distribution held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the noise-normalised dSPM source-power map per subject); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the dSPM inverse **from scratch** (no inverse solver bundled), over a **heterogeneous cohort where subjects need structurally different inverse operators**, with a **hidden robustness** requirement, graded sourcewise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *structurally different operators*, discoverable only from each sidecar and the data: average-referenced recordings have a rank `n_chan−1` noise covariance and the inverse must be built on its **reduced-rank pseudo-whitener** (a full-rank inversion blows up the near-null direction), whereas mastoid-referenced recordings are full rank; some subjects ship a noise covariance while others ship only a pre-stimulus baseline from which the **empirical covariance must be estimated** (assuming identity noise is wrong). A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the rank-truncated whitener, the trace-normalised regularisation `lambda^2 = trace(Gtil Gtil^T)/(r·SNR^2)`, the regularised minimum-norm kernel `Mtil = Gtil^T (Gtil Gtil^T + lambda^2 I_r)^{-1}`, and the `(Mtil Mtil^T)` noise normalisation must **all** be assembled correctly; an error in any one compounds.
3. **Hidden robustness** — a majority of subjects carry one to three grossly corrupted sensors (a huge transient on the evoked topography with otherwise-normal noise statistics, so whitening does not suppress them) that must be **detected and excluded** from the leadfield, data, and covariance before inversion; this robustness requirement is never stated in `instruction.md`.
4. **Convention-invariant grading** — the dSPM source power is orientation/sign-invariant and, with identity source covariance and the trace-normalised lambda, invariant to the global leadfield scale; two independent correct implementations agree to ~1e-8 (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes the dSPM power map from the bundled leadfield + evoked + noise model with a **held-out reference** pipeline (`dspm_pipeline` + `dspm_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **sourcewise** over the well-constrained source grid (leadfield column norm above a floor, defined on the full leadfield so it is implementation-independent), one parametrized test per subject (**8 panels**). A subject passes when ≥90% of graded sources agree within (rtol 8%, atol 2% of the median graded power). Reward is binary (all 8 subjects must pass).

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (symmetric-square-root whitener, SVD-based inverse, a different bad-channel statistic; **no** shared code) reproduces every subject to a worst-case median relative error of ~2e-8 (0% of graded sources disagree beyond tolerance), confirming the graded quantity is convention-invariant. The plausible-but-wrong pipelines each fail only their axis: **ignore bad channels** fails the 5 corrupted subjects; **full-rank whitening** fails the 2 average-referenced subjects; **assume identity noise** fails the 2 baseline-only subjects. The naive uniform pipeline (keep all channels + full-rank whitening) fails 7 of 8, so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **3/8 subjects**: correct on the well-conditioned mastoid-referenced, covariance-shipped, clean-sensor subjects, but failed the hard axes — the unannounced grossly-corrupted-sensor detection/exclusion, the reduced-rank pseudo-whitener on the average-referenced subjects, and the baseline covariance estimation on the covariance-absent subjects. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean dSPM pipeline and applies it uniformly — it handles the standard subjects but does not discover-and-exclude the unannounced corrupted sensors, nor rank-truncate the whitener for the average-referenced subjects, nor estimate the covariance from the baseline where none is shipped. Its underlying inverse is otherwise correct (the standard subjects pass), so the 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (assemble a coupled inverse operator with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the whitening/regularisation conventions but never enumerates the pitfalls (the corrupted sensors, the rank-deficient reference, the baseline-only covariance) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted sources are never under `/app/data`; `fixture_spec.json` is build-provenance only). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
