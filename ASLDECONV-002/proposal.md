## ASLDECONV-002

**Proposal Title:** Model-free deconvolution of a heterogeneous multi-PLD ASL cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Perfusion MRI / arterial spin labeling

**Source paper:** Wu et al. 2003, *MRM* (block-circulant SVD deconvolution, https://doi.org/10.1002/mrm.10522); Alsop et al. 2015, *MRM* (recommended pCASL implementation / single-compartment general kinetic model, https://doi.org/10.1002/mrm.25197). Dataset: a **synthetic** multi-post-labeling-delay (multi-PLD) ASL cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (produce per-voxel CBF/ATT/aBV maps); the difficulty is *execution*, not an un-cued judgement. It follows the maintainer's `pcasl-cbf-quantifier` shape: the agent implements two ASL kinetic inversions **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar's series list: a subject with a flow-**crushed** plus a **non-crushed** series carries a *measured* local arterial input (non-crushed − crushed), so its curve must be **deconvolved model-free by pinned block-circulant SVD** (Wu 2003, cSVD) and its aBV is determinable; a subject with a **single unpaired** series has no measured input, so it must be fit with the **single-compartment pCASL general kinetic model** (Alsop 2015) and aBV **must be omitted**. A majority of the cohort is the model-free fork, so a uniform pipeline is wrong on most subjects. The PLD schedule (dt, count, first PLD) also differs per subject and must be read, not assumed.
2. **Coupled-physics assembly** — the block-circulant construction (zero-pad to L=2N, circulant AIF matrix scaled by dt, truncate singular values below the pinned `p_svd` fraction), the dt quadrature, the local-AIF subtraction, the residue-peak read-out (CBF at the peak, ATT at its delay), and the linear-in-CBF kinetic fit must **all** be assembled correctly; an error in any one compounds across the (subject × map) panels.
3. **Hidden robustness** — a majority of subjects carry one or two grossly motion-corrupted label-control repetitions that must be **detected and rejected** before averaging; never announced in `instruction.md`, and both the deconvolution and the fit are biased if they survive.
4. **Convention-invariant grading** — CBF (mL/100g/min), ATT (s), and calibrated aBV are uniquely determined given the pinned cSVD truncation and kinetic model; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled ASL signals with a **held-out reference** pipeline (`asl_pipeline` + `asl_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel — **24 panels** in all. A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (CBF rtol 5%/atol 1.5; ATT atol 0.15 s; aBV rtol 5%/atol 0.08); an unsupported map (aBV for a single-series subject) passes only when the submission **omits** it. Reward is **fractional** (each panel its own test).

**Grading-invariance proof (the key check).** Two genuinely-correct independent implementations — one with batched numpy SVD + a variable-projection kinetic fit, one with looped scipy SVD + Levenberg-Marquardt, different robust-rep statistics, and trapezoid vs rectangular aBV — reproduce every computable panel (CBF and aBV to machine precision on the model-free fork, ATT argmax exactly, both to <0.02% on the model-based fork). The plausible-but-wrong pipelines each fail only their own axis: a **uniform kinetic fit** fails the model-free fork; **always-emit-aBV** or omitting it where determinable fails the omit rule; **non-robust averaging** is biased only on the corrupted subjects; a **wrong SVD truncation** biases only the model-free CBF/ATT; a **fixed dt** is wrong only on the off-schedule subjects. A single uniform pipeline fails 17 of 24 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **15/24 panels**, failing the model-free block-circulant SVD deconvolution fork (CBF/ATT), the unannounced corrupted-repetition rejection, and the per-subject aBV omit rule. |
| **2nd frontier family (Claude/Gemini)** | _pending_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one clean ASL pipeline and applies it uniformly — it handles the subjects on the fork it chose but does not thread the model-free cSVD deconvolution, discover-and-reject the unannounced corrupted repetitions, nor honour the aBV omit rule across the heterogeneous cohort. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get many coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the physics conventions but never enumerates the pitfalls (the crushed/non-crushed fork, the corrupted repetitions, the aBV omit, the per-subject PLD schedule) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
