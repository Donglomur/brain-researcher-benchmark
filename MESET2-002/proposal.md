## MESET2-002

**Proposal Title:** EPG-corrected T2 mapping of a heterogeneous multi-echo spin-echo cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / T2 relaxometry

**Source paper:** Hennig 1988, *Concepts Magn. Reson.* (extended phase graphs); Lebel & Wilman 2010, *MRM* (transverse relaxometry with stimulated echoes); Weigel 2015, *JMRI* (extended phase graphs review, https://doi.org/10.1002/jmri.24619). Dataset: a **synthetic** CPMG multi-echo spin-echo cohort (one magnitude echo train per subject), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth parameters held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the EPG-corrected T2, effective-flip, and normalised-amplitude maps) and the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the CPMG-EPG inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — a per-subject omit fork decided from the sidecar: subjects with a long-enough train (`n_echoes ≥ flip_min_echoes`) identify the effective refocusing flip, so all three maps are reported; **short-train** subjects cannot identify the flip, so it is **not** determinable and must be **omitted** while T2 is still produced under a nominal-refocusing (mono-exponential) assumption. A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the central trap is executional physics: on a **majority of subjects** the refocusing is imperfect (per-voxel flip well below the nominal 180°), so the CPMG train is **not** mono-exponential — stimulated and secondary echoes contaminate it, and a naive mono-exponential fit is biased 10–30% and yields no flip at all. Only a correct EPG forward model (ideal 90° excitation about +y, refocusing κ·180° about +x, decay-only relaxation over ESP/2 half-intervals with the sidecar's assumed T1) inverted for (κ, T2, amplitude) recovers the true T2 *and* the effective flip; the amplitude must be projected out and the optimiser must reach the **global** minimum (a single-start Levenberg-Marquardt with loose tolerances sticks at a spurious high-κ point on the strongly-imperfect subjects).
3. **Hidden robustness** — a **majority (five subjects)** carry a grossly deviant **first echo** (a common CPMG artefact) that a flexible (κ, T2) fit silently absorbs into the flip; it must be detected (fit the rest of the train, test the first echo) and rejected before T2 and the flip are trusted. Nothing in the instruction announces this.
4. **Convention-invariant grading** — T2 (ms), effective flip (deg), and WM-normalised M0 are convention-invariant physical quantities once the excitation/refocusing convention and decay-only EPG model are pinned in `protocol.json`; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled echo train with a **held-out reference** pipeline (`mese_pipeline` + `mese_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel — **24 panels** in all. A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (T2 rtol 4%/atol 2 ms; flip rtol 6%/atol 4 deg; M0_norm rtol 6%/atol 0.03); an unsupported map (the flip for a short-train subject) passes only when the submission **omits** it. Reward is binary (all panels pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent from-scratch EPG (with equilibrium regrowth *included*, per-voxel Levenberg-Marquardt instead of a grid, and a different first-echo screen; **no** import of the reference) reproduces every computable panel at 100% of voxels within tolerance (worst-case p90 relative error: T2 1.9%, flip 3.4%, M0_norm 3.1%). Wrong pipelines each fail only their own axis: a **mono-exponential fit** fails T2/flip/M0 on the imperfect subjects; **keeping the corrupted first echo** fails the artefact subjects; **forcing or omitting the flip map** fails the omit fork. A naive uniform pipeline (mono-exponential, no first-echo rejection, nominal flip) fails 13 of 24 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **15/24 panels**. The 9 failing panels concentrate on the task's designed hard axes: the EPG stimulated-echo correction on the imperfect-refocusing subjects (T2/flip/M0), the short-train flip **omit** fork, and the unannounced first-echo rejection on the 5 artefact subjects. A reproducible multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a clean T2 pipeline and applies it near-uniformly — it recovers the well-refocused subjects but does not fit the full EPG stimulated-echo model on the imperfect subjects, honour the short-train omit fork, or discover-and-reject the corrupted first echo, so the 0.0 is earned on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get many coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the imperfect-refocusing EPG requirement, the corrupted first echo, the flip omit fork) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
