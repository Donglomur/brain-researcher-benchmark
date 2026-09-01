## DKI-002

**Proposal Title:** Diffusion-kurtosis imaging (DKI) of a heterogeneous multi-shell cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + declared robustness with hidden realization)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure (kurtosis imaging)

**Source paper:** Jensen et al. 2005, *MRM* (diffusional kurtosis imaging, https://doi.org/10.1002/mrm.20508); Tabesh et al. 2011, *MRM* (estimation of tensors and tensor-derived measures in DKI); Jensen & Helpern 2010, *NMR Biomed.* (DKI review). Dataset: a **paper-parameterized** multi-shell diffusion-MRI cohort (Jensen 2005 DKI signal model), generated deterministically at `synth_build/generate_fixtures.py`; the true physiology is held out for grading under `tests/planted_truth.npz` (the reference run on the noise-free signal, built by `synth_build/build_truth.py`).

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the DKI scalar maps) and the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the tensor+kurtosis inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **publicly-declared robustness** requirement (the corrupted-volume realization hidden), graded voxelwise against the **planted physiology** on **convention-invariant** rotation-invariant scalars.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each gradient table: subjects with **≥ 2 distinct non-zero b-shells** determine the b² term, so the full diffusion-kurtosis model is fittable (report MD/FA plus MK/AK/RK); **single-non-zero-shell** subjects leave the b² term unconstrained, so only the mono-exponential diffusion tensor is determinable (report MD/FA and **omit** MK/AK/RK, like an absolute concentration with no water reference). A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the 22-parameter log-linear fit (ln S0 + the 6 unique diffusion-tensor and 15 unique kurtosis-tensor elements) must be assembled with the correct direction monomials and multiplicities; MD/FA taken from the fitted tensor D (**not** a separate mono-exponential fit over the mixed shells, which the kurtosis biases); and the apparent kurtosis `K(n)=W̃(n)/D(n)²` averaged the right way for each scalar (MK over the whole sphere, AK along the principal eigenvector, RK over the perpendicular ring). An error in any stage compounds.
3. **Declared robustness, hidden realization** — a **majority of subjects (6 of 8)** carry a handful of grossly motion-corrupted diffusion-weighted volumes (spikes / dropouts) that bias the joint tensor+kurtosis fit unless detected and rejected before the least-squares solve; nothing in the instruction announces them.
4. **Convention-invariant grading** — MD (µm²/ms), FA, MK, AK, RK are rotation-invariant physical quantities uniquely determined by the pinned model; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### What changed in this revision (addressing the review of #59/#61)

1. **Robustness contract made public.** `instruction.md` now states, under *Robustness / data-quality contract*, that a minority of DW volumes are grossly motion-corrupted and must be detected and rejected robustly — only the *realization* (which subjects/volumes) is hidden. A correct fit of the stated estimator is no longer penalized for failing to guess an undeclared step.
2. **Graded against the true physiology, not one fitter.** The verifier no longer recomputes with a private pipeline on the real data and demands agreement. It compares each submitted map, voxelwise, to the **held-out planted target** = the DKI/DTI reference run on the **noise-free, corruption-free** signal (`tests/planted_truth.npz`, built by `synth_build/build_truth.py`). That target is the convention-invariant physical truth; **any valid estimator** applied to the real data recovers it within tolerance. The hidden reference modules were removed from `tests/`.

### Verifier

`tests/test_outputs.py` grades **voxelwise** over the brain-tissue (WM+GM) mask against `tests/planted_truth.npz`, one parametrized test per (subject × map) panel — **40 panels**. A computable map passes when ≥90% of masked voxels match the planted value within a per-map physics-level tolerance (MD rtol 6%/atol 0.04; FA rtol 10%/atol 0.05; MK rtol 12%/atol 0.12; AK/RK rtol 15%/atol 0.15); an unsupported map (MK/AK/RK for a single-non-zero-shell subject) passes only when the submission **omits** it. Reward is binary (pytest rc==0 → 1 else 0), so every panel must pass.

**Validity / discrimination evidence (recomputed for this revision).** The oracle recovers the planted target on **all 40 panels (31 computable at 96–100 % voxel agreement, 9 correctly omitted)** — comfortably inside tolerance. A **naive fit that skips the gross-volume rejection fails 20 panels**, exactly on the corrupted subjects (the two uncorrupted subjects still pass); single-shell MD is targeted at the identifiable *apparent* diffusivity (the clean-signal DTI fit), which the real-data oracle recovers. So a from-scratch correct solver passes and single-axis shortcuts fail, on axes the instruction *declares*.

### Difficulty — frontier gate

Oracle **reward 1.0** verified in-container. On the *previous* (hidden-contract) version, **gpt-5.6-sol (codex, xhigh) scored 0.0**, solving 20/40 panels — failing on the single-shell omit fork, the corrupted-volume rejection, and the mono-exponential-vs-joint-DKI bias.

**Frontier re-gate on this revised (public-contract) version: PENDING.** Because the revision *discloses* the robustness requirement, the old gate number does not transfer and must be re-measured — not overclaimed here. The expectation is that the multi-axis assembly remains hard (per-subject shell-rule omit forks, discover-and-reject the hidden corrupted volumes without dropping clean ones, MD/FA from the joint fit, the three kurtosis directional averages); the local discrimination above shows every single-axis shortcut still fails. A 2nd frontier family (Claude/Gemini) gate is likewise pending at maintainer calibration.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get a hundred coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the model conventions but never enumerates the pitfalls (the shell-rule omit fork, the corrupted volumes) — the agent must discover them from the data.
- **Data.** Paper-parameterized, small, deterministic, and **leakage-clean** (the planted truth lives only in `tests/`, never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py` + `synth_build/build_truth.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
