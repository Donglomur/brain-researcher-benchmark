## CONNPLV-002

**Proposal Title:** Leakage-corrected source-space MEG connectivity (orthogonalised AEC-c) over a heterogeneous cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** MEG functional connectivity

**Source paper:** Colclough et al. 2015, *NeuroImage* (symmetric multivariate leakage correction, https://doi.org/10.1016/j.neuroimage.2015.03.071); Hipp et al. 2012, *Nat. Neurosci.* (pairwise orthogonalised amplitude-envelope correlation, https://doi.org/10.1038/nn.3101); Brookes et al. 2012, *NeuroImage* (AEC). Dataset: a **synthetic** source-space MEG connectivity cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth AEC-c matrices held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce each subject's leakage-corrected AEC-c connectivity matrix); the difficulty is *execution*, not an un-cued judgement. The agent implements orthogonalised amplitude-envelope correlation **from scratch** (no connectivity toolbox bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with **hidden robustness** requirements, graded entrywise against a **held-out reference** on a **convention-invariant** quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the leakage-correction scheme is dictated per subject by the recorded `inverse_method`: MNE/distributed sources carry dense zero-lag leakage and require the **multivariate symmetric (Loewdin) orthogonalisation** `L = X (XᵀX)^{-1/2}` of all retained ROIs jointly; LCMV beamformer sources require the **pairwise orthogonalisation** (regress one band-limited ROI out of the other, both directions, average). The two give materially different AEC-c, so applying a single scheme to the whole cohort biases half of it.
2. **Coupled-physics assembly** — dead-ROI detection, artifact-sample removal, the per-subject orthogonalisation, the discrete analytic (Hilbert) envelope, and the Pearson correlation must **all** be assembled correctly; an error in any one compounds across the (subject × panel) grid.
3. **Hidden robustness** — two requirements span a **majority** of the cohort and are never announced: (1) most subjects contain one or two **dead ROIs** whose source projection collapsed to near-zero power — undefined connectivity, which must be dropped (NaN) *and* excluded **before** the joint orthogonalisation of the live ROIs; (2) most subjects contain scattered **gross artifact time samples** (movement/SQUID jumps) that spike every live ROI at once — because a gross sample's spectral leakage contaminates the whole analytic-signal envelope, the samples must be removed **before** enveloping (masking after the Hilbert does not undo it), or every correlation is inflated.
4. **Convention-invariant grading** — AEC-c is invariant to per-ROI sign/scale, so the eigen and SVD routes to the symmetric orthogonaliser agree to machine precision; two independent correct implementations compute every entry the same (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes each subject's AEC-c matrix from the bundled signals with a **held-out reference** pipeline (`connplv_pipeline` + `connplv_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **entrywise** over the off-diagonal. Reward is **fractional** over **16 panels** (8 subjects × {omit, values}): the omit panel requires the off-diagonal finite/NaN structure to match (dead-ROI pairs omitted, determined pairs present); the values panel requires ≥90% of the determined pairs to agree within (rtol 0.10, atol 0.07).

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (SVD Loewdin, a different dead/artifact detector, its own Pearson correlation — importing none of the reference) reproduces every panel (16/16). The plausible-but-wrong pipelines each fail only their own axis: **wrong scheme** fails the mismatched subjects' values; **kept artifacts** fail the artifact subjects' values; **kept dead ROIs** fail the dead-ROI subjects' omit panel. A fully naive uniform pipeline (pairwise for all, no artifact or dead-ROI handling) scores 4/16, so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | k=1 | 0.0 | Solved **6/16 panels**; the 10 it missed fall on the hard axes — the per-subject orthogonalisation scheme fork (symmetric Loewdin for MNE vs pairwise for LCMV), the un-cued dead-ROI omit handling, and the un-cued gross-artifact-sample removal before enveloping. Full-suite gate reward 0. |
| **2nd frontier family (Claude/Gemini)** | pending | pending | to be run by the maintainer at gate calibration |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model applies one orthogonalisation scheme uniformly and does not discover the unannounced dead-ROI and gross-artifact handling, so its correlations are inflated on the affected subjects and the omit structure mismatches. The specific failing set is characterised from the task's hard axes (per-panel identities were not logged for this k=1 run); the 10-panel miss is the count the gate recorded and lands on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the per-subject scheme, the omit set, and the robustness right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable but never enumerates the pitfalls (the scheme fork, the dead ROIs, the gross samples) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted matrices are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
