## MPM-002

**Proposal Title:** Quantitative multi-parameter mapping (R1, R2*, MTsat, PD) of a heterogeneous SPGR cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + declared robustness with hidden realization)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / relaxometry

**Source paper:** Tabelow et al. 2019, *NeuroImage* (hMRI toolbox, https://doi.org/10.1016/j.neuroimage.2019.01.029); Weiskopf et al. 2013, *Front. Neurosci.* (multi-parameter mapping); Weiskopf et al. 2014, *Front. Neurosci.* (ESTATICS R2\*); Helms et al. 2008, *MRM* (MTsat). Dataset: a **paper-parameterized** multi-contrast spoiled-gradient-echo (SPGR) cohort, generated deterministically at `synth_build/generate_fixtures.py`; the true (planted) physiology is held out for grading under `tests/planted_truth.npz`.

**Status: FULL runnable Harbor task (revised per review of PR #59).** This is a **reconstruction** task, not a recognition / "spot-the-confound" task — the instruction names the deliverable (produce R1/R2\*/MTsat/PD maps); the difficulty is *execution*, not an un-cued judgement.

### What changed in this revision (addressing @zjc062's three points on #59)

1. **The robustness requirement is now public (point 3).** `instruction.md` states explicitly, under *Robustness / data-quality contract*, that a minority of subjects carry one or two grossly corrupted echo volumes that must be **detected and rejected robustly** before fitting, and that **B1+ must be applied**. Only the *realization* is hidden — *which* subjects and *which* echoes are corrupted. This follows the reviewer's principle ("hide the nuisance realization, not the estimator contract"): a correct implementation of the stated estimators is no longer penalized for failing to guess an undeclared analysis step.
2. **Grading is against the true physiology, not one reference fitter (point 3, corollary).** The verifier no longer recomputes with a private pipeline and demands agreement with *its* estimator choices. It compares each submitted map, voxelwise, to the **held-out planted ground-truth map** that generated the signals. **Any scientifically valid estimator passes** (OLS/WLS, closed-form or iterative VFA, any robust echo-rejection scheme). The hidden-reference modules were removed from `tests/`.
3. **The reproduced result is named (point 2).** The estimators are the standard hMRI-toolbox ones, cited by equation in `instruction.md`: ESTATICS joint R2\* (Weiskopf 2014), rational-SPGR VFA for R1/PD (Helms 2008 §2), Helms 2008 MTsat (δ formula). The planted physiology reproduces literature 3 T quantitative values (WM R1 ≈ 1.05 s⁻¹, R2\* ≈ 22 s⁻¹, MTsat ≈ 3 p.u., PD ≈ 70 %), varied by field and tissue.
4. **Data substrate (point 1) — open for maintainer direction.** Point 1 asked for the public **hMRI example dataset** as the substrate. That dataset is multi-GB of raw multi-echo DICOM and cannot be bundled into a self-contained, offline (`allow_internet=false`), deterministic task with a known voxelwise ground truth. This revision therefore keeps a **paper-parameterized simulation** (hMRI signal model + published tissue values), which is the bar @brain-researcher accepted for the CEST task on #60 ("a genuinely paper-parameterized simulation reproducing a named result"). **If you prefer real data, I will recut the task around the hMRI example set** (build-time fetch + crop to a small ROI, ground truth from the toolbox's own maps) — flagging that this trades the exact planted ground truth for a fetch dependency.

### Why this is hard (unchanged; still hard with the contract public)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar: 2-point vs 3+-flip VFA sets; MT-weighted contrast present for some, **absent** for others (→ omit MTsat); multi-echo vs single-echo (→ R2\* determinable or not).
2. **Coupled-physics assembly** — the rational-SPGR model, the joint log-linear ESTATICS R2\* fit, the a/S-vs-a² VFA regression, the Helms MTsat correction, and the per-voxel B1+ correction must **all** be assembled correctly; an error in any one compounds across the 28 (subject × map) panels.
3. **Declared robustness, hidden realization** — the agent is *told* corrupted echoes exist and must be rejected, but must still (a) find *which* echoes without dropping clean ones, and (b) thread the per-voxel B1+ correction through the strong-B1 subjects. This is genuine estimation, not spec-guessing.
4. **Convention-invariant grading** — grading against the planted physiology with physics-level tolerances means there is one right answer and no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` grades **voxelwise** over the brain mask against `tests/planted_truth.npz` (the held-out true maps; never under `/app/data`), one parametrized test per (subject × map) panel. A computable map passes when ≥90 % of brain voxels match the planted value within a per-map physics-level tolerance (R1 rtol 8 %/atol 0.04; R2\* rtol 12 %/atol 2.5; MTsat rtol 15 %/atol 0.4; PD_norm rtol 8 %/atol 0.04); an unsupported map (R2\* for single-echo, MTsat with no MTw) passes only when the submission **omits** it. Reward is binary (all 28 panels pass → 1.0).

**Validity / discrimination evidence (recomputed for this revision, in-repo):**

| Submission | Panels pass / 28 | Note |
|---|---|---|
| Oracle (robust + B1 + omit) | **28/28** → reward 1.0 | deterministic |
| Naive — no echo rejection | 19/28 | fails only the corrupted-echo subjects |
| Ignores B1+ | 23/28 | fails only the strong-B1 subjects |
| Computes all maps (no omit) | 23/28 | fails only the 5 unsupported panels |

The robust estimator recovers the planted physiology on **23/23 computable panels at 100 % voxel agreement**, i.e. comfortably inside tolerance — while each plausible-but-wrong pipeline loses exactly the panels its error corrupts. So a from-scratch correct solver passes and the wrong-but-reasonable ones fail, on axes the instruction *declares*.

### Difficulty — frontier gate

Oracle **reward 1.0** verified in-container. On the *previous* (hidden-contract) version, **gpt-5.6-sol (codex, xhigh) scored 0.0 at k=3**, solving 17/28 panels each run (missing R1 on strong-B1 subjects and R2\* on corrupted-echo subjects).

**Frontier re-gate on this revised (public-contract) version: PENDING.** Because the revision *discloses* the robustness requirement, the old gate number does not transfer and must be re-measured — I have not overclaimed it. The expectation (per @brain-researcher's note on #61, that such a task "should remain difficult even after the robustness contract is public") is that the multi-axis assembly — per-voxel B1+, discover-and-reject the hidden corrupted echoes without dropping clean ones, per-subject omit forks, the coupled VFA/ESTATICS/Helms chain — remains hard; the local discrimination table above shows every single-axis shortcut still fails. A 2nd frontier family (Claude/Gemini) gate is likewise pending at maintainer calibration.

### Notes / honesty

- **Reconstruction paradigm** (differs from the repo's recognition definition-of-done): the difficulty is executional. `instruction.md` now names the deliverable, the physics conventions, *and* the robustness contract; only the corrupted-echo realization and the per-subject omit forks are left to be discovered from the data.
- **Data.** Paper-parameterized, small, deterministic, leakage-clean (the planted truth lives only in `tests/`, never under `/app/data`; verified by grep). Regenerable via `synth_build/generate_fixtures.py`. Real-data recut available on request (point 1 above).
- **allow_internet=false.** Self-contained (dependencies baked into the image; no network at run or verify time).
