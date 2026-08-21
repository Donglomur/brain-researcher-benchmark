## PETMOTION-002

**Proposal Title:** Inter-frame motion correction and kinetic outcome for a dynamic-PET cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** PET kinetic modeling / motion correction

**Source paper:** Patlak, Blasberg & Fenstermacher 1983, *JCBFM* (Patlak graphical analysis, https://doi.org/10.1038/jcbfm.1983.1); Patlak & Blasberg 1985, *JCBFM* (https://doi.org/10.1038/jcbfm.1985.87); Lopresti et al. 2005, *J. Nucl. Med.* (reference-tissue SUVR). Dataset: a **synthetic** dynamic-PET (motion + kinetics) cohort (8 subjects), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth shifts and outcomes held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (register frames, correct motion, then compute the per-region kinetic outcome); the difficulty is *execution*, not an un-cued judgement. The agent implements the registration + kinetic pipeline **from scratch** (no tool bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded region-wise against a **held-out reference** on **convention-invariant** outcomes.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar and the data: the kinetic model is per subject — an **irreversible** tracer yields Patlak `Ki` from the provided arterial plasma input, a **reversible** tracer yields a reference-tissue `SUVR` — and the unsupported output must be **omitted** (writing it fails). The registrable frame set also differs: a majority have short, under-sampled (low-count) frames inside the analysis window that must be **held** from a neighbouring adequately-sampled frame, not registered, while other subjects are adequately sampled throughout. A single uniform recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the reference-frame NCC registration, the exact roll-based correction, the fixed-mask region-TAC extraction, the trapezoidal plasma integral, and the Patlak / SUVR graphical fits must **all** be assembled correctly; an error in any one propagates to the (subject × output) outcome.
3. **Hidden robustness** — un-announced, a **majority** of subjects carry one grossly corrupted frame (a bright artefact) inside the window that must be detected as an outlier and excluded, and a **majority** carry gross (≥2 voxel) motion that a too-small search window silently clips. Neither is flagged in `instruction.md`.
4. **Convention-invariant grading** — the inter-frame motion is genuinely integer-voxel translation applied by `numpy.roll` on a grid whose brain has a zero-background margin ≥ the largest shift, so registration reduces to a **discrete NCC argmax** with no interpolation kernel and no convergence tolerance to disagree about; two independent correct implementations recover bit-identical shifts (proven below) — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every outcome from the bundled frames with a **held-out reference** pipeline (`petmc_pipeline` + `petmc_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **region-wise**. The binary Harbor reward requires **every** one of the 16 (subject × {ki, suvr}) panels to pass. A computable output passes when ≥90% of its regions agree within a per-output tolerance (Ki rtol 6% / atol 2e-4; SUVR rtol 6% / atol 0.03); an unsupported output passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation — no smoothing, brain-masked NCC, reverse loop order, `np.polyfit` Patlak, and a different corruption statistic — recovers **bit-identical integer shifts** and reproduces every panel to ~5e-8 relative. The plausible-but-wrong pipelines each fail only their own axis: **no motion correction** biases every subject; **registering the low-count frames** instead of holding them biases only the low-count subjects; **keeping the corrupted frames** biases only the corrupted subjects; a **±1 search window** biases only the gross-motion subjects; a **single uniform kinetic model** fails the omit rule and drops the other tracer class. The naive uniform pipeline fails a majority (11/16).

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **11/16 panels** — the remaining 5 fail on the registration-robustness axes (holding the low-count frames, excluding the corrupted frames, and sizing the search window for gross motion) and/or the tracer-class omit fork; the binary Harbor reward zeroes on any failed panel. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model gets the standard, adequately-sampled subjects and the basic kinetic fits, but does not fully thread the un-announced robustness (low-count-frame hold, corrupted-frame exclusion, adequate search radius) across the cohort — leaving a residual set of panels biased. A reproducible multi-axis execution failure on the genuine hard axes.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (assemble a discrete NCC registration with per-subject frame handling, robust outlier rejection, and the tracer-class omit fork, with no bundled tool), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the pinned conventions but never flags the corrupted frames or the gross-motion magnitude — the agent must discover them.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted shifts are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
