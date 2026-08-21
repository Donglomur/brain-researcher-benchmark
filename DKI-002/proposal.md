## DKI-002

**Proposal Title:** Diffusion-kurtosis imaging (DKI) of a heterogeneous multi-shell cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure (kurtosis imaging)

**Source paper:** Jensen et al. 2005, *MRM* (diffusional kurtosis imaging, https://doi.org/10.1002/mrm.20508); Tabesh et al. 2011, *MRM* (estimation of tensors and tensor-derived measures in DKI); Jensen & Helpern 2010, *NMR Biomed.* (DKI review). Dataset: a **synthetic** multi-shell diffusion-MRI cohort (b=0 plus one or more diffusion-weighted shells per subject), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth parameters held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the DKI scalar maps) and the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the tensor+kurtosis inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** rotation-invariant scalars.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each gradient table: subjects with **≥ 2 distinct non-zero b-shells** determine the b² term, so the full diffusion-kurtosis model is fittable (report MD/FA plus MK/AK/RK); **single-non-zero-shell** subjects leave the b² term unconstrained, so only the mono-exponential diffusion tensor is determinable (report MD/FA and **omit** MK/AK/RK, like an absolute concentration with no water reference). A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the 22-parameter log-linear fit (ln S0 + the 6 unique diffusion-tensor and 15 unique kurtosis-tensor elements) must be assembled with the correct direction monomials and multiplicities; MD/FA taken from the fitted tensor D (**not** a separate mono-exponential fit over the mixed shells, which the kurtosis biases); and the apparent kurtosis `K(n)=W̃(n)/D(n)²` averaged the right way for each scalar (MK over the whole sphere, AK along the principal eigenvector, RK over the perpendicular ring). An error in any stage compounds.
3. **Hidden robustness** — a **majority of subjects (6 of 8)** carry a handful of grossly motion-corrupted diffusion-weighted volumes (spikes / dropouts) that bias the joint tensor+kurtosis fit unless detected and rejected before the least-squares solve; nothing in the instruction announces them.
4. **Convention-invariant grading** — MD (µm²/ms), FA, MK, AK, RK are rotation-invariant physical quantities uniquely determined by the pinned model; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled signals with a **held-out reference** pipeline (`dki_pipeline` + `dki_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the brain-tissue (WM+GM) mask, one parametrized test per (subject × map) panel — **40 panels** in all. A computable map passes when ≥90% of masked voxels agree within a per-map tolerance (MD rtol 6%/atol 0.04; FA rtol 8%/atol 0.04; MK rtol 10%/atol 0.10; AK/RK rtol 12%/atol 0.12); an unsupported map (MK/AK/RK for a single-non-zero-shell subject) passes only when the submission **omits** it. Reward is binary (test.sh: pytest rc==0 → 1 else 0), so every panel must pass.

**Grading-invariance proof (the key check).** A fully independent implementation (weighted rather than ordinary least squares, batch rather than one-at-a-time outlier rejection, a different dense direction set and ring sampling for the kurtosis averages; **no** import of the reference) reproduces every computable panel to well within tolerance (worst-panel voxel agreement 97–100%). Wrong pipelines each fail only their own axis: **compute kurtosis on single-shell subjects** fails the omit rule; **skip the corrupted-volume rejection** is biased only on the corrupted subjects; a **mono-exponential DTI over mixed shells** biases MD/FA only on the multi-shell subjects; **wrong MD units** (mm²/s vs µm²/ms) fails every MD panel. A naive uniform pipeline (DKI everywhere, no rejection, all five maps) fails 33 of 40 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **20/40 panels**. The 20 failing panels concentrate on the task's designed hard axes: the single-shell **omit** rule for MK/AK/RK, the unannounced corrupted-volume rejection on the 6 affected subjects, and the mono-exponential-vs-joint-DKI bias on MD/FA over the multi-shell subjects. A reproducible multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean DKI pipeline and applies it near-uniformly — it recovers the standard well-behaved panels but does not honour the single-shell omit fork, discover-and-reject the unannounced corrupted volumes, or take MD/FA from the joint fit rather than a mixed-shell mono-exponential, so the 0.0 is earned on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get a hundred coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the model conventions but never enumerates the pitfalls (the shell-rule omit fork, the corrupted volumes) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
