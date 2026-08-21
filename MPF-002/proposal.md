## MPF-002

**Proposal Title:** Macromolecular-proton-fraction (MPF) mapping of a heterogeneous fast-qMT cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / magnetization transfer (qMT)

**Source paper:** Yarnykh 2012, *MRM* (fast single-point macromolecular-proton-fraction mapping, https://doi.org/10.1002/mrm.23224); Sled & Pike 2001, *MRM* (quantitative two-pool MT model); Morrison & Henkelman 1995, *MRM* (super-Lorentzian bound-pool lineshape). Dataset: a **synthetic** fast-qMT cohort (unsaturated reference + one or more MT-weighted images, with `R1f`/`B1+`/`B0` maps), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the MPF map, and the forward exchange rate kf where determinable); the difficulty is *execution*. The agent implements single-point / full-Z-spectrum qMT MPF mapping **from scratch** (no fitter is bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with **hidden robustness** requirements, graded voxelwise against a **held-out reference**.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar's MT sampling. **Single-point** subjects acquire one MT-weighted image, so MPF is the unique root of the two-pool steady-state model with the exchange rate **pinned**, and kf is not independently determinable and must be **omitted** (like an absent water reference). **Full-Z-spectrum** subjects acquire many offsets × powers, so MPF and the exchange rate are jointly fit and kf is produced — and, critically, the single-point formula is *biased* on them because their tissue exchange rate departs from the pinned value, so a uniform single-point pipeline fails them.
2. **Coupled-physics assembly** — the MT ratio `S_MT/S_ref`, the B1+-scaled saturation amplitude (`w1 ∝ b1`, saturation `∝ w1²`), the B0-corrected effective offset, the super-Lorentzian bound-pool lineshape, the two-pool 2×2 steady-state solve, and a monotone 1-D inversion (single-point) or nonlinear (MPF, exchange) fit (full-Z) must **all** be assembled correctly; an error in any one compounds.
3. **Hidden robustness** — two off-critical-path axes, both unannounced. A per-voxel B1+ transmit field is uniform on some subjects and ±25% inhomogeneous on a *majority* (six of eight) — ignoring it biases MPF well past tolerance. And a *majority* — five of the six full-Z subjects — carry one grossly **motion-corrupted MT volume** that must be rejected before the joint fit; because every full-Z subject's exchange rate sits below the single-point pin, an un-rejected corruption biases **both** MPF and kf on each of those five subjects (10 of 16 panels), while one clean full-Z subject penalizes a "always drop a volume" hack.
4. **Convention-invariant grading** — with the constrained-model constants pinned, MPF (p.u.) and kf (1/s) are uniquely determined by the two-pool physics; two independent correct implementations compute them identically (proven below), and kf must be omitted where the single-point acquisition cannot determine it.

### Verifier

`tests/` recomputes MPF (and kf) from the bundled signals with a **held-out reference** pipeline (`mpf_pipeline` + `mpf_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the analysis (GM+WM) mask — 16 (subject × map) panels (8 subjects × {MPF, kf}), each its own test; the Harbor reward is binary (all panels must pass). A computable map passes when ≥90% of masked voxels agree within a per-map tolerance (MPF rtol 8%/atol 0.6 p.u.; kf rtol 12%/atol 0.35); kf for a single-point subject passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (direct-quadrature super-Lorentzian, per-voxel `brentq` single-point root-find, per-voxel trust-region (MPF, exchange) least squares, batch sigma-clip outlier rejection; **no** import of the reference) reproduces every computable panel to median relative error ~1e-5 (100% of voxels within tolerance), confirming MPF and kf are convention- and method-invariant. The plausible-but-wrong pipelines each fail their own axis: **ignore B1** fails 6 MPF panels; **single-point-everywhere** fails all six full-Z subjects on MPF plus their required kf; **full-fit-everywhere** fails the two single-point subjects; and — the design's core — the **non-robust** pipeline that skips motion-volume rejection fails **both** maps on all five corrupted subjects (10 of 16 panels). Partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **6/16 panels** — failed the hard axes: the single-point vs full-Z recipe fork (kf omitted for single-point; the single-point formula biased on the full-Z subjects), the per-voxel B1+ transmit correction (six of eight subjects inhomogeneous), and rejecting the grossly motion-corrupted MT volume before the joint fit (five of six full-Z subjects, biasing both MPF and kf). |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one clean qMT inversion and applies it uniformly — it handles a couple of standard subjects but does not thread the per-voxel B1+ correction, fork single-point vs full-Z, or discover-and-reject the unannounced corrupted MT volumes. The passing panels show its two-pool solve is otherwise correct, so the 0.0 is earned on the genuine hard axes.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional, unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the per-voxel B1, the corrupted MT volumes, the single-point/full-Z fork) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
