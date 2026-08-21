## NODDIBAYES-002

**Proposal Title:** Multi-fibre ball-and-stick reconstruction of a heterogeneous diffusion-MRI cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / tractography

**Source paper:** Behrens et al. 2003, *MRM*, "Characterization and propagation of uncertainty in diffusion-weighted MR imaging" (ball-and-stick model; https://doi.org/10.1002/mrm.10609); Behrens et al. 2007, *NeuroImage*, "Probabilistic diffusion tractography with multiple fibre orientations: what can we gain?" (crossing-fibre model selection / ARD; https://doi.org/10.1016/j.neuroimage.2006.09.018). Dataset: a **synthetic** multi-shell/single-shell diffusion-MRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth fibre configurations held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (reconstruct the per-voxel crossing-fibre model — count, orientations, volume fractions — and write it out); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the ball-and-stick estimator and nested model selection **from scratch** (no fitter bundled), over a **heterogeneous 7-subject cohort where the required computation varies both per voxel and per subject**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the required computation varies **both per voxel and per subject**. Per voxel the number of fibres is unknown and must be **inferred**: isotropic voxels support 0 sticks, single-fibre voxels 1, crossing voxels 2, and the estimator must prune the unsupported sticks (a pipeline that fits two sticks everywhere over-reports fibres on the isotropic/single-fibre majority and reports a spurious second fraction). Per subject the diffusivity is handled from the acquisition: a **multi-shell** exam constrains `d` directly (fit it), whereas a **single-shell** exam uses the pinned protocol `d`; the shells, direction counts and b-values all vary and must be read from the sidecar.
2. **Coupled-physics assembly** — the physics is coupled and non-linear: the ball-and-stick signal, the joint fit of diffusivity, fibre orientations and volume fractions, and the nested model selection for the fibre count must **all** be assembled correctly; an error in any one compounds.
3. **Hidden robustness** — a **majority** of the subjects carry a few grossly corrupted gradient volumes (dropouts/spikes) that bias every voxel's fit unless detected and rejected before fitting; this robustness requirement is **not announced** in `instruction.md`.
4. **Convention-invariant grading** — the fibre count is decided from the fitted objective (SSE reduction), which every correct optimiser drives to the same floor, and the fractions/orientations are the unique well-conditioned least-squares optimum in the design's safe envelope (multi-shell or fixed-d single-shell, SNR≥30, crossing angles ≥65°, wide fraction margins), so two independent correct implementations compute them identically (proven below) — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled diffusion signal with a **held-out reference** pipeline (`bas_pipeline` + `bas_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel — 7 subjects × {n_fibres, f1, f2, v1, v2} = 35 panels. A panel passes when ≥~90% of the relevant voxels agree: exact fibre count; primary/secondary volume fraction within (rtol 0.10–0.12, atol 0.05) at every masked voxel (the reference is 0 where a fibre is pruned, so a spurious extra fibre fails here); primary/secondary orientation within 12–15° (sign-invariant acute angle) over the voxels the reference supports. Reward is binary (all 35 panels pass → 1.0).

**Grading-invariance proof (the key check).** A from-scratch independent implementation (different optimiser, multi-start initialisation, batch sigma-clip volume rejection — no import of the reference) reproduces every panel. The plausible-but-wrong pipelines each fail only their own axis: **always two sticks with no ARD** fails the fibre-count/secondary-fraction panels on every subject; **no corrupt-volume rejection** fails only the contaminated subjects; a **wrong fixed diffusivity** fails only the single-shell subjects; **mis-ordered fibres** fail the fraction/orientation panels — so a naive uniform pipeline (two sticks everywhere, fit d everywhere, no rejection) fails a majority (25/35 measured).

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **15/35 panels**, failing the hard axes: the per-voxel fibre-count inference with stick pruning (spurious second fibres on the isotropic/single-fibre majority), the unannounced corrupt-volume rejection on the majority of subjects, and/or the multi-shell vs fixed-d single-shell diffusivity fork. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single ball-and-stick fit and applies it uniformly — it recovers some orientations but does not correctly thread the nested model selection / stick pruning nor discover-and-reject the unannounced corrupted gradient volumes. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the non-linear model, model selection, units, and per-subject adaptation right with no bundled fitter), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the model-selection rule but never enumerates the pitfalls (the corrupted volumes, the per-voxel pruning, the diffusivity fork) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`; verified by grep). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
