## DIFFTIME-002

**Proposal Title:** Time-dependent diffusion — restriction and structure from D(t) — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure

**Source paper:** Mitra, Sen, Schwartz & Le Doussal 1992, *Phys. Rev. Lett.* (short-time diffusion / surface-to-volume ratio, https://doi.org/10.1103/PhysRevLett.68.3555); Novikov, Jensen, Helpern & Fieremans 2014, *PNAS* (long-time structural universality classes, https://doi.org/10.1073/pnas.1316944111). Dataset: a **synthetic** time-dependent-diffusion cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth diffusivities and structural parameters held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce Dref/D0/SV/Dinf maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the time-dependent-diffusion inversion **from scratch** (no fitter bundled), over a **heterogeneous 8-subject cohort where subjects need structurally different estimators**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *structurally different estimators*, discoverable only from each sidecar's declared diffusion-time regime. **Short-time** subjects sample the √t rise, so D(t) is fit against [1, √t]: the intercept is the free diffusivity D0 and the √t slope fixes the Mitra surface-to-volume ratio S/V — but the long-time plateau is not sampled and Dinf must be **omitted**. **Long-time** subjects sample the power-law approach to the tortuosity plateau, so D(t) is fit against [1, t^(−θ)] with the subject's **declared** structural-class exponent θ (1/2 for random-barrier, 1 for strong-disorder subjects); the intercept is Dinf — but D0 and S/V must be **omitted**. **Single-time** subjects sample one diffusion time, so only the measured D is reportable.
2. **Coupled-physics assembly** — the regime basis, the intercept/slope extraction, the Mitra S/V formula (coupling slope, intercept, and structural dimension d), and the reference-time arithmetic must **all** be assembled correctly; an error in D0 propagates into S/V, and choosing the wrong basis biases the extrapolated intercepts.
3. **Hidden robustness** — a majority of subjects carry one or two grossly corrupted diffusion-time volumes (motion / low-SNR long-time artefacts) that must be **detected and rejected** before the linear fit, or the extrapolated intercepts and slopes are biased on exactly those subjects; this is never announced in `instruction.md`.
4. **Convention-invariant grading** — every graded quantity is a physical diffusivity or S/V obtained by ordinary least squares in a protocol-stated basis after rejecting unambiguous gross-outlier volumes, so two independent correct implementations compute them identically (proven below); a from-scratch solver passes while wrong pipelines fail.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled D(t) with a **held-out reference** pipeline (`dt_pipeline` + `dt_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel — 32 panels total. Reward is **fractional** (fraction of panels correct). A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (Dref/D0/Dinf rtol 6%/atol 0.03 µm²/ms; SV rtol 15%/atol 0.02 1/µm); an unsupported map (Dinf for a short/single subject, D0/SV for a long/single subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (RANSAC-consensus outlier rejection instead of least-trimmed-squares, scipy instead of numpy least squares, its own Mitra and reference-time arithmetic; **no** import of the reference) reproduces every computable panel to well within tolerance. The plausible-but-wrong pipelines each fail only their own axis: **wrong regime basis** biases the extrapolated intercepts; a **hard-coded exponent** biases the strong-disorder subjects; **no outlier rejection** biases only the corrupted subjects; a **wrong Mitra dimension** biases S/V; **always-emit-all-maps** fails the omit panels. Partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **22/32 panels**; the failures fall on the task's hard axes — the per-regime basis fork and its omit rule (emitting Dinf from short-only data, or D0/SV from long-only data), the declared-θ handling on the strong-disorder subjects, the Mitra S/V coupling, and the unannounced corrupted-volume rejection. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model fits a diffusivity but does not correctly split the cohort into its three regimes, thread the declared θ, or discover-and-reject the unannounced corrupted diffusion-time volumes, so the residual failures land on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get many coupled quantitative decisions right with no recipe). `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the regime forks, the corrupted volumes) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
