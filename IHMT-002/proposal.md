## IHMT-002

**Proposal Title:** Quantitative inhomogeneous magnetization transfer (ihMT) of a heterogeneous cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / magnetization transfer

**Source paper:** Varma et al. 2015, *MRM* (inhomogeneous magnetization transfer from dipolar-broadened lines; the ihMTR difference-of-differences and the dipolar relaxation time T1D, https://doi.org/10.1002/mrm.25174). Dataset: a **synthetic** ihMT cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (produce per-voxel MTR/ihMTR/T1D maps); the difficulty is *execution*, not an un-cued judgement. The agent implements a full quantitative ihMT analysis **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar's acquisition list: some collected **only single-frequency** saturations (a +offset and a −offset scan) so **MTR is computable but ihMTR is not** and must be **omitted**; others add **dual-frequency** (simultaneous ±) saturation, making ihMTR (the difference-of-differences ratio) computable at the reference dual condition; only a subset **sweep the dual interpulse spacing dt over ≥3 distinct values**, so **T1D is fittable** — a subject with a single dt (even acquired twice for averaging) does not determine T1D and must **omit** it. Maps: MTR (all 8), ihMTR (6), T1D (4).
2. **Coupled-physics assembly** — MT/ihMT attenuation scales with transmit power (~B1²), so MTR and ihMTR must be **corrected to nominal B1** by the B1+ map (T1D, a decay rate, is B1-invariant); the difference-of-differences must be assembled at the smallest-dt reference dual; and the single-exponential ln-ihMTR-vs-dt fit must be done per voxel. An error in any one compounds.
3. **Hidden robustness** — every acquisition is stored as repeated dynamics and a majority of subjects carry one or two grossly motion-corrupted dynamics that must be **detected and rejected** before the dynamics are combined; never announced in `instruction.md`.
4. **Convention-invariant grading** — MTR, ihMTR, and T1D are uniquely determined given the pinned B1 correction and reference-dual condition; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled signals with a **held-out reference** pipeline (`ihmt_pipeline` + `ihmt_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise**, one parametrized test per (subject × map) panel — **24 panels** in all; the Harbor reward (`test.sh`) is **binary** (1 only if every panel passes). MTR/ihMTR are graded over parenchyma (GM+WM; CSF excluded) at rtol 0.10/atol 0.01 and rtol 0.12/atol 0.004; T1D over WM at rtol 0.18/atol 0.6; a panel passes when ≥90% of graded-region voxels agree. An unsupported map (ihMTR with no dual scan, T1D with <3 distinct dt) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (different gross-dynamic rejection statistic, iteratively-reweighted T1D fit) reproduces every computable panel to well within tolerance (MTR/ihMTR agree to ~1e-8, T1D within a few percent). The plausible-but-wrong pipelines each fail only their own axis: **ignore B1** biases MTR/ihMTR only on the inhomogeneous-B1 subjects; **non-robust dynamic averaging** biases whatever map the corrupted acquisition feeds, only on the corrupted subjects; **emitting ihMTR/T1D** where the scheme does not support them fails the omit rule. The one-recipe naive pipeline fails a majority (17/24).

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **22/24 panels**, failing 2 on the hard axes — the B1-corrected ihMTR / per-voxel T1D fit under the unannounced corrupted-dynamic rejection and the ihMTR/T1D omit forks. Reward is still binary, so the 2 residual failures score 0.0. |
| **2nd frontier family (Claude/Gemini)** | _pending_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model reconstructs most of the cohort correctly but leaves a residual pair of failing panels on the coupled B1-correction / robust-dynamic-rejection / omit-fork axes. Because reward is binary, near-solves score 0.0 — the failure is on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the coupled ihMT physics and per-subject forks right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the conventions but never enumerates the pitfalls (the single/dual/dt-sweep forks, the corrupted dynamics, the B1 correction) — the agent must discover them.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
