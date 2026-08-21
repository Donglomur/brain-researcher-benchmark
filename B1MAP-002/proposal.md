## B1MAP-002

**Proposal Title:** Relative transmit-field (B1+) mapping of a heterogeneous multi-sequence cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / B1+ transmit mapping

**Source paper:** Insko & Bolinger 1993, *JMR* (double-angle B1 mapping); Yarnykh 2007, *MRM* (actual flip-angle imaging / AFI, https://doi.org/10.1002/mrm.21120); Sacolick et al. 2010, *MRM* (B1 mapping by Bloch-Siegert shift, https://doi.org/10.1002/mrm.22357). Dataset: a **synthetic** heterogeneous B1-transmit mapping cohort (8 subjects at 1.5/3/7 T), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth transmit fields held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the per-voxel relative transmit field `B1rel` for every subject); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the transmit-field estimators **from scratch** (no solver bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *structurally different estimators*, discoverable only from each sidecar's `images` list: a **double-angle** acquisition (two magnitudes at flip α and 2α, long TR) needs `arccos(S_2α / 2S_α)`; an **actual-flip-angle (AFI)** acquisition (two magnitudes at one flip, two TRs) needs the rational `cos(α) = (rn−1)/(n−r)` with `n = TR2/TR1`; a **Bloch-Siegert** acquisition (two phase images at ±off-resonance, plus a reliability magnitude) needs the `sqrt(Δφ/kbs)` phase-shift estimator. These are three genuinely different computations — a single fixed formula fits none of the others — and each carries its own conventions (which image is 2α; the ratio direction and `n`; the phase-difference sign and the provided `kbs`; normalisation to the nominal flip). A single fixed recipe cannot map the cohort.
2. **Coupled-physics assembly** — the per-sequence estimator, the arccos clip, the AFI ratio direction, the Bloch-Siegert phase differencing against the supplied `kbs`, and the final normalisation to the nominal flip must **all** be assembled correctly; an error in any one corrupts a different subset of the (subject × panel) grid, and errors do not cancel (a wrong estimator, an inverted ratio, or a dropped `kbs` each biases a different subset).
3. **Hidden robustness** — a *majority* of subjects carry an unannounced receive/signal **dropout** where the weakest contributing magnitude collapses into the noise floor; there the ratio / phase difference is meaningless and the naive estimator returns a spurious finite transmit value, so those voxels must be **detected** (weakest contributing magnitude below the noise floor) and **excluded**. This is never announced in `instruction.md`.
4. **Convention-invariant grading** — `B1rel` = actual/nominal flip is a receive-invariant physical field; two independent correct implementations (different linear algebra, a different SNR threshold, a different clip/branch convention) recover the same value, so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes `B1rel` from the bundled images with a **held-out reference** pipeline (`b1map_pipeline` + `b1map_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise**. Each subject contributes two parametrized panels (16 total): a **value** panel — `B1rel` over the adequate-signal voxels must agree with the reference within rtol 0.05 / atol 0.02 for ≥90% of voxels — and an **exclusion** panel — the noise-floor voxels must be excluded (non-finite or `|·|≤0.10`) for ≥90% (vacuous where a subject has no dropout). Reward is binary (all panels pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (different linear algebra, a different SNR threshold and noise handling, a different clip/branch convention; **no** import of the reference) reproduces every valid voxel to <2% and reproduces the void partition (the signal gap is >100×, so any reasonable threshold agrees), passing all 16 panels. The plausible-but-wrong pipelines each fail only their own axis: a **single fixed estimator** fails the value panels on the other two sequences; **no noise-floor rejection** fails the exclusion panels; an **inverted ratio** or a **dropped kbs** biases only that sequence's subjects.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **10/16 panels**, failing the genuine hard axes — the per-sequence estimator dispatch (double-angle vs AFI vs Bloch-Siegert conventions) and the unannounced noise-floor dropout exclusion — while passing the panels its uniform recipe happened to fit. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one clean B1-estimator and applies it broadly — it handles the sequences that match its assumed recipe but does not correctly thread the per-subject estimator choice and its conventions, nor discover-and-reject the unannounced noise-floor dropout voxels. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (choose the right estimator per subject, get its conventions right, and reject noise-floor voxels — a hundred coupled decisions with no bundled solver), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the shared conventions but never enumerates the pitfalls (the per-subject estimator fork, the dropout exclusion) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
