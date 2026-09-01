## MSDKI-002

**Proposal Title:** Mean-signal diffusion-kurtosis (MSDKI) inversion of a heterogeneous multi-shell cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + declared robustness with hidden realization)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure

**Source paper:** Jensen & Helpern 2010, *NMR Biomed.* (diffusion kurtosis imaging, https://doi.org/10.1002/nbm.1518); Henriques et al. 2021, *Magn. Reson. Med.* (robust mean-signal / powder-averaged DKI, https://doi.org/10.1002/mrm.28730). Dataset: a **paper-parameterized** multi-shell diffusion-MRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; the true physiology is held out for grading under `tests/planted_truth.npz` (the MSDKI reference run on the noise-free, corruption-free signal, built by `synth_build/build_truth.py`; never under `/app/data`).

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce per-voxel MSD and, where determinable, MSK maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the MSDKI inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **publicly-declared robustness** requirement (the corrupted-volume realization hidden), graded voxelwise against the **planted physiology** on **convention-invariant** physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each subject's b-values: with ≥2 distinct non-zero shells both MSD and MSK are determined by the quadratic log-signal fit, whereas a single-non-zero-shell subject determines **only** MSD from the two-point mono-exponential slope and MSK is **not computable and must be omitted** (like an absolute concentration with no water reference). The b-value schemes differ per subject, so shells must be read from the data — a hard-coded scheme cannot fit the cohort.
2. **Coupled-physics assembly** — shell grouping, the **arithmetic** powder average per shell, the `b=0` normalisation, the log-linear design `[1, −b, b²/6]` with `b` in ms/µm² (`= bval/1000`), and the `MSK = (quadratic coeff)/MSD²` unpacking must **all** be assembled correctly; an error in any one compounds.
3. **Declared robustness, hidden realization** — a majority of subjects (6 of 8) carry one or two grossly corrupted diffusion volumes (dropout or spike) that bias the per-shell powder mean and must be **rejected** before averaging. `instruction.md` now *declares* this requirement (under *Robustness / data-quality contract*), but *which* subjects and *which* volumes are affected is hidden and must be discovered from the data.
4. **Convention-invariant grading** — the powder (direction) average makes MSD and MSK rotation-invariant by construction, and with `b=0` plus two shells the three-point fit is exactly determined, so MSD and MSK are implementation-independent physical quantities; two independent correct implementations agree to ~5e-8 (proven below).

### What changed in this revision (addressing the review of #59/#61)

1. **Robustness contract made public.** `instruction.md` now states, under *Robustness / data-quality contract*, that a majority of subjects carry grossly corrupted diffusion volumes that must be detected and rejected robustly before the powder average — only the *realization* (which subjects/volumes) is hidden. A correct fit of the stated estimator is no longer penalized for failing to guess an undeclared step.
2. **Graded against the true physiology, not one fitter.** The verifier no longer recomputes with a private pipeline on the real data and demands agreement. It compares each submitted map, voxelwise, to the **held-out planted target** = the MSDKI reference run on the **noise-free, corruption-free** signal (`tests/planted_truth.npz`, built by `synth_build/build_truth.py`). That target is the convention-invariant physical truth; **any valid estimator** applied to the real data recovers it within tolerance. The hidden reference modules were removed from `tests/`.

### Verifier

`tests/test_outputs.py` grades **voxelwise** over the brain mask against `tests/planted_truth.npz`, one parametrized test per (subject × map). There are **16 panels** (8 subjects × {MSD, MSK}). A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (MSD rtol 6%/atol 0.02; MSK rtol 14%/atol 0.08 — kurtosis is the noisiest MSDKI metric, so a slightly wider physics-level band comparable to DKI kurtosis tolerances); an unsupported map (MSK for a single-non-zero-shell subject, encoded by ABSENCE of the key) passes only when the submission **omits** it. Reward is binary (1 only if every panel passes).

**Validity / discrimination evidence (recomputed for this revision).** The oracle recovers the planted target on **all 16 panels** (13 computable at 0.96–1.00 voxel agreement, 3 MSK correctly omitted) — comfortably inside tolerance. A **naive fit that skips the volume rejection fails 9 panels**, on the corrupted subjects' MSD/MSK, while the clean subject (sub-01) passes both and the single-shell subjects pass MSD. So a from-scratch correct solver passes and the single-axis shortcut fails, on an axis the instruction now *declares* (realization hidden).

### Difficulty — frontier gate

Oracle **reward 1.0** verified in-container. On the *previous* (hidden-contract) version, **gpt-5.6-sol (codex, xhigh) scored 0.0**, solving 7/16 panels — failing the (then-undeclared) corrupted-volume rejection on the 6 motion-affected subjects and the MSK omit rule on the single-non-zero-shell subjects.

**Frontier re-gate on this revised (public-contract) version: PENDING.** Because the revision *discloses* the corrupted-volume robustness requirement, the old gate number does not transfer and must be re-measured — not overclaimed here. The expectation is that the multi-axis assembly remains hard (per-subject shell reading and the single-shell MSK omit fork, the coupled powder-average / log-linear-fit / MSK-unpacking physics, discover-and-reject the hidden corrupted volumes without dropping clean ones); the local discrimination above shows the corrupted-volume shortcut still fails. A 2nd frontier family (Claude/Gemini) gate is likewise pending at maintainer calibration.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (assemble a coupled per-voxel inversion with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the powder-average/estimator conventions but never enumerates the pitfalls (the corrupted volumes, the single-shell omit fork) — the agent must discover them from the data.
- **Data.** Paper-parameterized, small, deterministic, and **leakage-clean** (the planted truth lives only in `tests/planted_truth.npz`, never under `/app/data`; `fixture_spec.json` is build-provenance only). Regenerable via `synth_build/generate_fixtures.py` + `synth_build/build_truth.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
