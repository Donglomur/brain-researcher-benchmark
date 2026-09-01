## FLOW4D-002

**Proposal Title:** Phase-contrast / 4D-flow velocity quantification of a heterogeneous cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / phase-contrast flow

**Source paper:** Markl et al. 2012, *JMRI* (4D flow MRI, https://doi.org/10.1002/jmri.23632); Pelc et al. 1991, *JMRI* (phase-contrast cine velocity mapping, https://doi.org/10.1002/jmri.1880010405); Bernstein et al. 1998, *MRM* (concomitant-field / background-phase correction). Dataset: a **paper-parameterized** phase-contrast / 4D-flow cohort (8 subjects), generated deterministically at `synth_build/generate_fixtures.py`; the true physiology is held out for grading under `tests/planted_truth.npz` (the reference run on the noise-free, artifact-free signal, built by `synth_build/build_truth.py`).

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (per-voxel speed, peak velocity, net flow from magnitude + phase); the difficulty is *execution*, not an un-cued judgement. The agent implements the velocity reconstruction **from scratch** (no reconstruction tool bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **publicly-declared robustness** requirement (the realization — which subjects carry the drift / alias — hidden), graded per-quantity against the **planted physiology** on **convention-invariant** velocity magnitudes.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar and the data: some encode a single **through-plane** velocity, some encode **3 directions** (speed needs all three components; net flow needs only the plane-normal projection), and some encode a single **in-plane** velocity whose direction is perpendicular to the slice normal — so through-plane net flow is **not determinable** and must be **omitted**. A single "through-plane PC" recipe cannot fit the cohort.
2. **Coupled-physics assembly** — phase→velocity scaling (`v = VENC·φ/π`), background-phase removal, aliasing unwrap, multi-directional speed magnitude, plane-normal projection, and area integration with unit conversion must **all** be assembled correctly; an error in any one compounds across the (subject × quantity) panels.
3. **Declared robustness, hidden realization** — two requirements span a majority of the cohort and are now **declared publicly** in `instruction.md` (only the realization — *which* subjects — is hidden): a **majority** of subjects alias (peak velocity exceeds VENC → a single-band wrap, a physically-impossible negative core inside forward flow) and must be **unwrapped** (add `2·VENC` to the wrapped core) — a computation the within-VENC subjects must **not** apply; and a smooth eddy-current/background **phase drift** must be fitted over static tissue (excluding the lumen and the low-signal air) and removed, with the surrounding air masked out by its low magnitude.
4. **Convention-invariant grading** — the graded quantities are velocity magnitudes fixed by the pinned convention; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### What changed in this revision (addressing the review)

1. **Robustness contract made public.** `instruction.md` now states, under *Robustness / data-quality contract*, that a majority of subjects carry an eddy-current background-phase drift that must be fitted over static tissue and removed, and that a majority alias (peak > VENC) and must be single-band-unwrapped — only the *realization* (which subjects) is hidden. A correct fit of the stated convention is no longer penalized for failing to guess an undeclared step.
2. **Graded against the true physiology, not one fitter.** The verifier no longer recomputes with a private pipeline on the real data and demands agreement. It compares each submitted quantity to the **held-out planted target** = the phase-contrast reference run on the **noise-free, artifact-free** signal (the encoded true velocity only — no eddy background, no air noise — wrapped so aliasing is present exactly as in the real data), stored in `tests/planted_truth.npz` and built by `synth_build/build_truth.py`. That target is the convention-invariant physical truth; **any valid estimator** applied to the real data recovers it within tolerance. The hidden reference modules (`flow_pipeline.py`, `flow_ref.py`) were removed from `tests/` (the oracle's copies remain under `solution/`).

### Verifier

`tests/test_outputs.py` grades **per (subject × quantity)** against `tests/planted_truth.npz` — the 24 panels are 8 subjects × {speed, peak_velocity, net_flow}, each its own parametrized test. The speed panel passes when ≥90% of lumen voxels match the planted value within (rtol 8%, atol 4 cm/s); peak within (8%, 3 cm/s); net_flow within (8%, 2 mL/s); an in-plane-only subject's net_flow (key absent in the planted truth) passes only when the submission **omits** it. Per-panel scoring is fractional-intent, but the Harbor reward is binary — any failed panel zeroes it.

**Validity / discrimination evidence (recomputed for this revision).** The oracle recovers the planted target on **all 24 panels at 100% lumen-voxel agreement** (peak deltas ≤ 0.66 cm/s, flow deltas ≤ 0.34 mL/s) — comfortably inside tolerance, confirming the graded quantities are convention-invariant magnitudes. The plausible-but-wrong pipelines each fail their own axis, measured through the real verifier: **no background removal** fails 10 panels (the drift subjects); **no aliasing unwrap** fails 11 panels (the aliased subjects); **single-component speed** fails 3 panels (the 3-directional subjects); **emit flow for in-plane** fails the 2 omit panels; a combined all-naive pipeline fails 19 of 24. So any valid pipeline passes and every single-axis shortcut fails, on axes the instruction now declares.

### Difficulty — frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle recovers all 24 planted panels).

On the *previous* (hidden-contract) version, **gpt-5.6-sol (codex, xhigh)** scored **0.0 across k=3**, solving only 6/24 panels — failing the aliasing unwrap, the eddy-current background-phase removal, the multi-directional speed magnitude, and the in-plane-only omit rule.

**Frontier re-gate on this revised (public-contract) version: PENDING.** Because the revision *discloses* the robustness requirements, the old gate number does not transfer and must be re-measured — not overclaimed here. The expectation is that the multi-axis assembly remains hard (per-subject encoding-geometry omit forks, discover-and-unwrap only the aliased subjects, discover-and-remove only the drift subjects, combine all encoded directions into speed); the local discrimination above shows every single-axis shortcut still fails through the public-contract verifier. A 2nd frontier family (Claude/Gemini) gate is likewise pending at maintainer calibration.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (thread aliasing, background correction, multi-directional geometry, and omit forks with no bundled tool), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the pinned velocity convention but never enumerates the pitfalls (the aliasing, the phase drift, the in-plane omit, the air noise) — the agent must discover them from the data.
- **Data.** Paper-parameterized, small, deterministic, and **leakage-clean** (the planted truth lives only in `tests/planted_truth.npz`, never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py` + `synth_build/build_truth.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
