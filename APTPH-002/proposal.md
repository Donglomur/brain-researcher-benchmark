## APTPH-002

**Proposal Title:** pH-weighted amide-proton-transfer (APT) CEST ratiometric indices over a heterogeneous Z-spectrum cohort — an execution-hard reconstruction task (recipe divergence + coupled B0/robustness assembly + convention-invariant grading)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** CEST / molecular MRI

**Source paper:** McVicar et al. 2014, *J. Cereb. Blood Flow Metab.* (concentration-independent AACID pH imaging, https://doi.org/10.1038/jcbfm.2014.12); Zhou et al. 2003, *Nat. Med.* (amide proton transfer / APT-CEST). Dataset: a **paper-parameterized** APT-CEST saturation Z-spectrum cohort, generated deterministically at `synth_build/generate_fixtures.py`; the true physiology is held out for grading under `tests/planted_truth.npz` (the reference run on the noise-free, corruption-free spectrum, built by `synth_build/build_truth.py`).

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the per-voxel ratiometric APT indices APTR and AACID); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's reconstruction tasks (e.g. `pcasl-cbf-quantifier`): the agent implements the ratiometric pH-weighted analysis **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **publicly-declared robustness** requirement (the corrupted-frame realization hidden), graded voxelwise against the **planted physiology** on **convention-invariant** ratio quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar's acquired-offset list. Four subjects densely sample the guanidinium/amine region (~2.5–3.0 ppm), so the concentration-independent AACID pH index is determinable; four **gap** that region (only the amide side is sampled), so AACID is **not computable and must be omitted** (like a water-reference-absent absolute concentration) while the always-determinable ratiometric APTR index is still produced. A single fixed offset schedule cannot fit the cohort.
2. **Coupled-physics assembly** — the graded indices are exact ratios of B0-corrected Z-values, but their definitions (which offsets; the direct spectrum, not a parametric pool-model fit; amine at 2.75 ppm, not 2.0 ppm) must all be assembled correctly, and each mistake corrupts a different subset of the (subject × index) panels.
3. **Declared robustness, hidden realization** — threaded through every subject is a per-voxel B0 correction (the B0-corrected Z-value at pinned offset Ω is the cleaned spectrum interpolated at Ω+b0); six of eight subjects carry strong ±0.30 ppm shifts, and skipping it biases both indices. Independently, a **majority** of subjects (six of eight) carry one or two grossly motion-corrupted whole-offset frames that must be **detected as outliers** of the otherwise-smooth Z-spectrum and rejected before the pinned offsets are read. `instruction.md` now *declares* both requirements; only the *realization* (which subjects/offsets are corrupted) is hidden.
4. **Convention-invariant grading** — both indices are ratios of B0-corrected Z-values, so the M0/normalisation scale cancels; two independent correct implementations compute them identically, so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### What changed in this revision (addressing the review of #59/#61)

1. **Robustness contract made public.** `instruction.md` now states, under *Robustness / data-quality contract*, that a minority of offset frames are grossly corrupted and must be detected and rejected robustly, and that per-voxel B0 must be applied everywhere — only the *realization* (which subjects/frames) is hidden. A correct implementation of the stated analysis is no longer penalized for failing to guess an undeclared step.
2. **Graded against the true physiology, not one fitter.** The verifier no longer recomputes with a private pipeline on the real data and demands agreement. It compares each submitted index, voxelwise, to the **held-out planted target** = the ratiometric reference run on the **noise-free, corruption-free** Z-spectrum (`tests/planted_truth.npz`, built by `synth_build/build_truth.py`). That target is the convention-invariant physical truth; **any valid estimator** applied to the real data recovers it within tolerance. The hidden reference modules were removed from `tests/` (the oracle's copies remain under `solution/`).

### Verifier

`tests/test_outputs.py` grades **voxelwise** over the brain mask against `tests/planted_truth.npz`, one parametrized test per (subject × index) panel — **16 panels**. A computable index passes when ≥90% of brain voxels match the planted value within a per-index tolerance (rtol 10%, atol 0.08); an unsupported index (AACID where the amine offset 2.75 ppm is not bracketed) passes only when the submission **omits** it. Reward is binary (pytest rc==0 → 1 else 0), so every panel must pass.

**Tolerance rationale.** The target is the noise-free planted truth, so the per-voxel tolerance must cover the *irreducible* Rician-noise scatter of these ratiometric indices at the acquired SNR (empirically ~4 % median / ~14 % p95 for a correct estimator — visible even on the two uncorrupted subjects). It is far tighter than the whole-frame corruption bias (×0.5–1.7), which collapses the affected panels to <0.62 voxel agreement, so it does not blunt discrimination.

**Validity / discrimination evidence (recomputed for this revision).** The oracle recovers the planted target on **all 16 panels (12 computable at 0.96–1.00 voxel agreement, 4 correctly omitted)** — comfortably inside tolerance. A **naive fit that skips the gross-frame rejection fails 9 panels**, exactly the (subject × index) combinations that read a corrupted offset (e.g. sub-07 APTR, whose reference frame at 6.0 ppm is corrupted, drops to 0.00 voxel agreement); the two uncorrupted subjects still pass. So a from-scratch correct solver passes and single-axis shortcuts fail, on axes the instruction *declares*.

### Difficulty — frontier gate

Oracle **reward 1.0** verified in-container. On the *previous* (hidden-contract) version, **gpt-5.6-sol (codex, xhigh) scored 0.0**, solving 7/16 panels — failing the per-voxel B0 correction, the corrupted-frame rejection, and the AACID omit fork.

**Frontier re-gate on this revised (public-contract) version: PENDING.** Because the revision *discloses* the robustness requirement, the old gate number does not transfer and must be re-measured — not overclaimed here. The expectation is that the multi-axis assembly remains hard (per-subject AACID omit fork, per-voxel B0 threading, discover-and-reject the hidden corrupted frames without dropping clean ones, the exact ratio definitions); the local discrimination above shows every single-axis shortcut still fails. A 2nd frontier family (Claude/Gemini) gate is likewise pending at maintainer calibration.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get many coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions and now declares the robustness axes, but never enumerates the *realization* (which subjects/frames are corrupted, the per-subject AACID omit fork) — the agent must discover those from the data.
- **Data.** Paper-parameterized, small, deterministic, and **leakage-clean** (the planted truth lives only under `tests/`, never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py` + `synth_build/build_truth.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
