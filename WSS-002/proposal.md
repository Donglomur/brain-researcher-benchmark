## WSS-002

**Proposal Title:** Wall shear stress and oscillatory shear index from a heterogeneous 4D-flow / phase-contrast cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Neurovascular 4D-flow MRI / hemodynamics

**Source paper:** Stalder et al. 2008, *Magn. Reson. Med.* (quantitative 2D/3D phase-contrast MRI: blood flow and vessel-wall parameters, https://doi.org/10.1002/mrm.21778); Ku et al. 1985, *Arteriosclerosis* (oscillatory shear index). Dataset: a **synthetic** 4D-flow / phase-contrast vessel cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth wall-shear quantities held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce per-wall-node TAWSS, peak WSS, and OSI where determinable); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the wall-shear-stress pipeline **from scratch** (no tool bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded per-wall-node against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar: 3-directional 4D-flow subjects (a majority, 5/8) carry three velocity components over several cardiac frames and require the full 3D WSS vector — the wall-normal gradient of **both** wall-tangential velocity components — and OSI from the WSS vector over the cycle; 2D through-plane phase-contrast subjects store only the axial velocity at a single frame, so **only** the axial WSS is determinable and OSI is **not determinable and must be omitted** (like an absolute concentration with no water reference). Using the axial-only gradient on a 3-directional subject underestimates every 3D panel. A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the wall-tangential projection, the near-wall gradient along the provided inward normal, the pinned viscosity + cm/s·mm → Pa unit conversion, the per-frame WSS vector, its time-average and peak, and the OSI vector formula must **all** be assembled correctly; an error in any one compounds.
3. **Hidden robustness** — un-cued and spanning a majority of the cohort: a first-order background/eddy-current velocity offset (present on 6/8 subjects) must be estimated from the static tissue and removed; and the partial-volume boundary voxel plus a minority of phase-wrap aliasing outliers at the near wall must be rejected by a **high-breakdown** near-wall gradient estimator (Theil-Sen / repeated-median). Neither is announced in `instruction.md`.
4. **Convention-invariant grading** — the pinned viscosity, unit conversion, provided wall normals, and the linear near-wall profile make the wall shear stress a uniquely-determined physical quantity; a genuinely-independent implementation reproduces every computable panel to a median relative error ~1% (proven below), so a from-scratch solver can pass while wrong pipelines fail.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled velocity field with a **held-out reference** pipeline (`wss_pipeline` + `wss_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades per wall node, one parametrized test per (subject × map). There are **24 (subject × map) panels**. Reward is **fractional** — the score is the fraction of panels correct. A computable map passes when ≥90% of wall nodes agree within a per-map tolerance (tawss rtol 10%/atol 0.010 Pa; wss_peak rtol 10%/atol 0.012 Pa; osi rtol 15%/atol 0.03); an unsupported map (OSI for a single-frame through-plane subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (`scipy` background fit; a **different** high-breakdown near-wall estimator — repeated-median / Siegel) reproduces every computable panel to well within tolerance (median relative error ~1%, min pass fraction 1.00 over all 24 panels). The plausible-but-wrong pipelines each fail only their axis: **axial-only gradient** biases only the 3-directional subjects; **OSI-for-through-plane** fails only the omit panels; **no background correction** fails only the background subjects; a **non-robust near-wall fit** fails wherever the near-wall voxels are corrupted (a majority). A single fixed naive recipe fails all 24 panels, so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **12/24 panels**, failing the hard axes — the acquisition fork (full 3D WSS vector + OSI for the 3-directional subjects vs axial-only + OSI-omit for the through-plane subjects), the unannounced background/eddy-current offset correction on the 6 affected subjects, and the high-breakdown near-wall gradient estimator that rejects the partial-volume boundary voxel and phase-wrap outliers. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean near-wall gradient pipeline and applies it broadly — it produces valid maps for the simpler / uncorrupted panels but does not correctly thread the 3-directional-vs-through-plane fork (and the OSI omit rule), the unannounced background offset removal, or the high-breakdown near-wall estimator. Half the panels pass, so the 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (assemble a coupled hemodynamics pipeline with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the WSS/OSI conventions but never enumerates the pitfalls (the background offset, the near-wall outliers, the acquisition fork) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted quantities are never under `/app/data`; `fixture_spec.json` is build-provenance only). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
