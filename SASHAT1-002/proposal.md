## SASHAT1-002

**Proposal Title:** Saturation-recovery T1 mapping of a heterogeneous SASHA-style cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / relaxometry (T1 mapping)

**Source paper:** Chow et al. 2014, *MRM* (Saturation-recovery single-shot acquisition, SASHA, for myocardial T1 mapping, https://doi.org/10.1002/mrm.24878). Dataset: a **synthetic** saturation-recovery (SASHA) T1 cohort (8 subjects), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth T1 and residual-ratio maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (per-voxel T1, and the residual ratio where supported, from each recovery series); the difficulty is *execution*, not an un-cued judgement. The agent implements the saturation-recovery inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-free** relaxometry quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar: the saturation scheme selects the recovery model — a validated-complete saturation **train** fixes the residual (`f = 1`) and is fit with the **2-parameter** model `S = A(1 − exp(−TS/T1))`, whereas a **single** B1-sensitive prep leaves a residual and is fit with the **3-parameter** model `S = A(1 − f·exp(−TS/T1))`. Forcing the 2-parameter model on a single-prep exam biases T1 (a model-misspecification bias); fitting the 3-parameter model on a train exam invents a residual ratio that must instead be **omitted**. A subject whose TS schedule has too few distinct points to constrain its model (fewer than 4 for the 3-parameter, fewer than 3 for the 2-parameter) does **not** determine T1, which must be omitted like an absent measurement. A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — model selection, the per-voxel nonlinear least-squares fit, the residual-ratio read-out, and the determinability rule must **all** be assembled correctly; an error in any one corrupts a different subset of the 16 (subject × map) panels.
3. **Hidden robustness** — un-announced, a **majority** of subjects carry one or two grossly motion-corrupted recovery frames (a whole frame scaled by a gross factor) that must be detected and rejected (gross outliers of the per-frame fit residual, well above the ~1–2% noise floor) before the nonlinear fit, or T1 and B/A are biased. This is never flagged in `instruction.md`.
4. **Convention-free grading** — saturation recovery has no inversion-efficiency or Look–Locker ambiguity, so the recovery time constant T1 and the residual ratio B/A are uniquely determined and reproduced by any correct least-squares fit (proven below) — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes T1 and B/A from the bundled recovery series with a **held-out reference** fit (`srt1_pipeline` + `srt1_ref`: a vectorised damped Gauss–Newton least-squares with model selection and robust frame rejection; shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask. Each of the 16 (subject × map) panels is its own parametrized test; per-panel scoring is fractional-intent, but the Harbor reward is binary — any failed panel zeroes it. A determinable map passes at ≥90% agreement within a per-map tolerance (T1 rtol 6%/atol 15 ms; Bratio rtol 6%/atol 0.03); an undeterminable map (Bratio for a 2-parameter train exam, or either map for a too-sparse TS schedule) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation — per-voxel `scipy.optimize.curve_fit` with a different initialisation and a different batch-sigma-clip frame rejection — reproduces every determinable panel to well within tolerance. The plausible-but-wrong pipelines each fail only their own axis: **force 2-parameter everywhere** biases the single-prep subjects; **force 3-parameter everywhere** invents B/A on the train subjects (omit-rule failure); **no frame rejection** biases only the motion-corrupted subjects; **never omit** fails the too-sparse / fixed-saturation panels — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **9/16 panels** — the remaining 7 fail on the model-selection (2- vs 3-parameter), the determinability / omit rule, and the un-announced corrupted-frame robustness axes; the binary Harbor reward zeroes on any failed panel. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model fits a basic saturation-recovery curve but does not correctly select the 2- vs 3-parameter model per scheme, does not apply the too-sparse / fixed-saturation omit rules, and does not discover-and-reject the corrupted recovery frames — leaving a residual set of panels biased or wrongly emitted. A reproducible multi-axis execution failure on the genuine hard axes.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (thread the model-selection and determinability forks and a robust frame rejection with no bundled fitter), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the pinned model but never flags the corrupted frames — the agent must discover them.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
