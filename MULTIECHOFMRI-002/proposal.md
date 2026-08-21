## MULTIECHOFMRI-002

**Proposal Title:** Multi-echo fMRI — per-voxel T2* mapping and the temporal SNR of the optimal echo combination across a heterogeneous cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Multi-echo functional MRI

**Source paper:** Posse et al. 1999, *MRM* (multi-echo BOLD optimal combination, https://doi.org/10.1002/(SICI)1522-2594(199907)42:1<87::AID-MRM13>3.0.CO;2-O); Kundu et al. 2012, *NeuroImage* (multi-echo EPI / tedana, https://doi.org/10.1016/j.neuroimage.2011.12.028). Dataset: a **synthetic** multi-echo fMRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (estimate per-voxel T2*, and the tSNR of the T2*-weighted optimal echo combination, per subject); the difficulty is *execution*, not an un-cued judgement. The agent implements the tedana-style pipeline **from scratch** (no fitter bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — a 3+-echo train supports a validated per-voxel mono-exponential T2*/S0 map, while a 2-echo train does **not** (the fit is exactly determined and un-validatable, like a water-reference-absent absolute concentration) so the T2*/S0 maps must be **omitted** — yet those same 2-echo subjects still need the exact 2-point T2* *internally* to weight the optimal echo combination whose tSNR is graded for **every** subject. A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the log-linear T2*/S0 fit, the Poser optimal-combination weights `w = TE·exp(−TE/T2*)`, and the temporal-SNR of the combined series must **all** be assembled correctly; an error in any one compounds across the (subject × map) panels.
3. **Hidden robustness** — a **majority** (5 of 8) of subjects additionally carry a few grossly motion-corrupted time frames — unannounced — that must be censored **before** the temporal mean (which feeds T2*/S0) *and* before the tSNR, or both are biased on those subjects; a minority carry a susceptibility-dropout region of near-noise-floor late echoes.
4. **Convention-invariant grading** — T2* (ms), S0_norm, and tSNR are uniquely determined given the pinned model; a from-scratch implementation (a different motion detector via a robust MAD z-score, a non-linear magnitude-domain T2* fit) reproduces every computable panel to well within tolerance (proven below), so a correct solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled echo series with a **held-out reference** pipeline (`mefmri_pipeline` + `mefmri_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask. Reward is **fractional**: each of the **24 (subject × map) panels** is its own test, so the score is the fraction of panels correct. A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (T2star rtol 8%/atol 2 ms; S0_norm rtol 6%/atol 0.03; tSNR rtol 8%/atol 3); an unsupported map (T2star/S0_norm for a 2-echo subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (a different motion detector via a robust MAD z-score, a non-linear magnitude-domain T2* fit) reproduces every computable panel to well within tolerance (worst panel 98.6% of voxels within tol; T2*/tSNR 100%). The plausible-but-wrong pipelines (compute the omitted maps, skip motion censoring, drop the TE weight factor, plain-average combine) each fail only their own axis, and a naive uniform pipeline fails 14 of 24 panels — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | k=1 | 0.0 | Solved **16/24 panels**; the 8 it missed fall on the hard axes — the un-cued gross-motion frame censoring (biasing T2* and tSNR on the 5 motion subjects), the 2-echo vs 3+-echo T2*/S0 omit fork, and the Poser optimal-combination weighting. Full-suite gate reward 0. |
| **2nd frontier family (Claude/Gemini)** | pending | pending | to be run by the maintainer at gate calibration |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean multi-echo pipeline and does not discover-and-censor the unannounced motion frames before the temporal mean and tSNR, nor cleanly fork the T2*/S0 omit for the 2-echo subjects. The specific failing set is characterised from the task's hard axes (per-panel identities were not logged for this k=1 run); the 8-panel miss is the count the gate recorded and lands on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the per-subject echo-count fork, the optimal-combination weights, and the motion robustness right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable but never enumerates the pitfalls (the 2-echo omit, the motion frames, the TE weight factor) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
