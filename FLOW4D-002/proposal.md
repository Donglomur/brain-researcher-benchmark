## FLOW4D-002

**Proposal Title:** Phase-contrast / 4D-flow velocity quantification of a heterogeneous cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / phase-contrast flow

**Source paper:** Markl et al. 2012, *JMRI* (4D flow MRI, https://doi.org/10.1002/jmri.23632); Pelc et al. 1991, *JMRI* (phase-contrast cine velocity mapping, https://doi.org/10.1002/jmri.1880010405); Bernstein et al. 1998, *MRM* (concomitant-field / background-phase correction). Dataset: a **synthetic** phase-contrast / 4D-flow cohort (8 subjects), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth velocity fields held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (per-voxel speed, peak velocity, net flow from magnitude + phase); the difficulty is *execution*, not an un-cued judgement. The agent implements the velocity reconstruction **from scratch** (no reconstruction tool bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded per-quantity against a **held-out reference** on **convention-invariant** velocity magnitudes.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar and the data: some encode a single **through-plane** velocity, some encode **3 directions** (speed needs all three components; net flow needs only the plane-normal projection), and some encode a single **in-plane** velocity whose direction is perpendicular to the slice normal — so through-plane net flow is **not determinable** and must be **omitted**. A single "through-plane PC" recipe cannot fit the cohort.
2. **Coupled-physics assembly** — phase→velocity scaling (`v = VENC·φ/π`), background-phase removal, aliasing unwrap, multi-directional speed magnitude, plane-normal projection, and area integration with unit conversion must **all** be assembled correctly; an error in any one compounds across the (subject × quantity) panels.
3. **Hidden robustness** — two un-announced requirements span a majority of the cohort: a **majority** of subjects alias (peak velocity exceeds VENC → a single-band wrap, a physically-impossible negative core inside forward flow) and must be **unwrapped** (add `2·VENC` to the wrapped core) — a computation the within-VENC subjects must **not** apply; and a smooth eddy-current/background **phase drift** must be fitted over static tissue (excluding the lumen and the low-signal air) and removed, with the surrounding air masked out by its low magnitude. Neither is flagged in `instruction.md`.
4. **Convention-invariant grading** — the graded quantities are velocity magnitudes fixed by the pinned convention; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every quantity from the bundled magnitude + phase with a **held-out reference** pipeline (`flow_pipeline` + `flow_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **per (subject × quantity)** — the 24 panels are 8 subjects × {speed, peak_velocity, net_flow}, each its own parametrized test. The speed panel passes when ≥90% of lumen voxels agree within (rtol 8%, atol 4 cm/s); peak within (8%, 3 cm/s); net_flow within (8%, 2 mL/s); an in-plane-only subject's net_flow passes only when the submission **omits** it. Per-panel scoring is fractional-intent, but the Harbor reward is binary — any failed panel zeroes it.

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation — a different lumen threshold, a quadratic (rather than planar) background fit, and a breadth-first region-growing aliasing unwrap — reproduces every panel to <0.5%, well inside tolerance, confirming the graded quantities are convention-invariant magnitudes. The plausible-but-wrong pipelines each fail only their own axis: **ignore background** fails only the drift subjects; **no unwrap** fails only the aliased subjects; **single-component speed** fails only the 3-directional subjects; **emit flow for in-plane** fails only the omit panels; **no noise masking** corrupts peak/flow via air noise. The un-adapted uniform "through-plane PC" pipeline fails 20 of 24 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=3** | **0.0 (all 3)** | Solved **6/24 panels** — a strong majority (18/24) failed. The uniform through-plane pipeline handles only the standard within-VENC subjects and fails the hard axes: aliasing unwrap, eddy-current background-phase removal, multi-directional speed magnitude, and the in-plane-only omit rule. Confirmed reward 0 across all 3 trials. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model applies one clean "through-plane phase-contrast" recipe uniformly — it never unwraps the aliased majority, never fits/removes the background phase drift, does not combine multi-directional components into speed, and emits net flow where it should be omitted. Because the traps are independent axes and it solves none of them, it clears only 6/24. A clean, reproducible multi-axis execution failure.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (thread aliasing, background correction, multi-directional geometry, and omit forks with no bundled tool), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the pinned velocity convention but never enumerates the pitfalls (the aliasing, the phase drift, the in-plane omit, the air noise) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted fields are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
