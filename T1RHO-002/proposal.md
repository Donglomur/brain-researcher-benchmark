## T1RHO-002

**Proposal Title:** Quantitative T1rho relaxometry of a heterogeneous spin-lock cohort — an execution-hard reconstruction task (recipe divergence + delicate model fitting + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / T1rho relaxometry

**Source paper:** Gilani & Sepponen 2016, *NMR Biomed.* (quantitative rotating-frame relaxometry methods); Sharafi et al. 2017, *JMRI* (bi-component T1rho relaxation mapping). Dataset: a **synthetic** spin-lock (T1rho) relaxometry cohort (one magnitude spin-lock series per subject over a set of spin-lock times), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth parameters held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the rotating-frame relaxation maps) and the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the mono- and bi-exponential inversions **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the model order forks per subject, decided only from each sidecar's spin-lock-time (TSL) list: a subject sampling **≥ 8 distinct TSLs** resolves two rotating-frame water pools and the four-parameter bi-exponential decay (S0, fraction, T1rho_short, T1rho_long) is determinable, so the three component maps are reported and the single mono-exponential T1rho is **omitted**; a subject sampling **< 8 TSLs** cannot constrain four parameters, so only the mono-exponential T1rho is determinable and the three bi-exponential maps must be **omitted** (like an unsupported absolute concentration). A single fixed recipe cannot fit the cohort.
2. **Delicate coupled model fitting** — the bi-exponential fit is itself delicate: the two components trade off, so a naive `curve_fit` from a generic seed lands in the wrong local minimum on many voxels (a coarse (T_short, T_long) grid with a linear amplitude solve must seed a bounded nonlinear refine), and the two labels must be **ordered** (T1rho_short ≤ T1rho_long) or the per-voxel component assignment is arbitrary and half the parenchyma swaps.
3. **Hidden robustness** — a **majority of subjects (7 of 8)** carry grossly corrupted spin-lock images — a B0/B1 spin-lock **banding** image (a whole image scaled down) and/or one or two **over-long TSL** images that have decayed into the noise floor (magnitude ~ pure Rician noise) — that must be detected and rejected before fitting, or the recovered relaxation times and fraction are biased. Nothing in the instruction announces them.
4. **Convention-invariant grading** — T1rho, T1rho_short, T1rho_long (ms) and the short-pool fraction are the parameters of the ordered least-squares fit, convention-invariant once the model and ordering are pinned in `protocol.json`; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled spin-lock signals with a **held-out reference** pipeline (`t1rho_pipeline` + `t1rho_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise**, one parametrized test per (subject × map) panel — **32 panels** in all; the score is the fraction of panels correct. A computable map passes when ≥90% of its region voxels agree within a per-map tolerance (T1rho rtol 6%/atol 2 ms over the brain mask; T1rho_short rtol 12%/atol 2 ms, T1rho_long rtol 10%/atol 3 ms, fraction rtol 15%/atol 0.04 over GM+WM parenchyma); an unsupported map (the three bi-exponential maps for a <8-TSL subject, or the single T1rho for a ≥8-TSL subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (different gross-image rejection, a multi-start nonlinear solver instead of a grid seed; **no** import of the reference) reproduces every computable panel to machine agreement (median and 90th-percentile voxel relative error 0.000 across all 20 computable panels). Wrong pipelines each fail only their own axis: a single naive **mono-exponential-everywhere** pipeline fails 22/32 panels; **skipping image rejection** fails 17/32 (the corrupted-subject panels); the two wrong **model-order** choices fail 20/32 and 12/32 (the mis-forked subjects); **unordered components** fail 15/32 (the component maps) — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **15/32 panels**. The 17 failing panels concentrate on the task's designed hard axes: the ≥8-vs-<8-TSL model-order **omit** fork, the unannounced gross-image rejection spanning 7 of 8 subjects, the component **ordering** convention, and the well-seeded bi-exponential fit. A reproducible multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a clean relaxometry pipeline and applies it near-uniformly — it recovers the straightforward mono-exponential panels but does not honour the model-order omit fork, discover-and-reject the unannounced corrupted images, order the two components, or seed the bi-exponential fit to the global minimum, so the 0.0 is earned on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get many coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the model conventions but never enumerates the pitfalls (the model-order omit fork, the corrupted images, the ordering, the fit seeding) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
