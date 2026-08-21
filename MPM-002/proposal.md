## MPM-002

**Proposal Title:** Quantitative multi-parameter mapping (R1, R2*, MTsat, PD) of a heterogeneous SPGR cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Quantitative MRI / relaxometry

**Source paper:** Tabelow et al. 2019, *NeuroImage* (hMRI toolbox, https://doi.org/10.1016/j.neuroimage.2019.01.029); Weiskopf et al. 2013, *Front. Neurosci.* (multi-parameter mapping); Helms et al. 2008, *MRM* (MTsat). Dataset: a **synthetic** multi-contrast spoiled-gradient-echo (SPGR) cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth parameters held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce R1/R2\*/MTsat/PD maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the quantitative inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar: 2-point vs 3+-flip variable-flip-angle sets; the MT-weighted contrast present for some subjects and **absent** for others (MTsat then not computable → must be omitted); multi-echo vs single-echo (R2\* determinable or not). A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the rational-SPGR signal model, the joint log-linear ESTATICS R2\* fit, the a/S-vs-a² VFA regression for R1/PD, the Helms MTsat correction, and the per-voxel B1+ transmit correction must **all** be assembled correctly; an error in any one compounds across the (subject × map) panels.
3. **Hidden robustness** — a minority of subjects carry grossly motion-corrupted echo volumes that must be **detected and rejected** before the joint R2\* fit; this is never announced in `instruction.md`.
4. **Convention-invariant grading** — R1 (1/s), R2\* (1/s), MTsat (p.u.), and WM-normalized PD are uniquely determined given the pinned signal model; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled signals with a **held-out reference** pipeline (`mpm_pipeline` + `mpm_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel. A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (R1 rtol 6%/atol 0.03; R2\* rtol 10%/atol 2; MTsat rtol 10%/atol 0.3; PD_norm rtol 6%/atol 0.03); an unsupported map (R2\* for single-echo, MTsat with no MTw) passes only when the submission **omits** it. Reward is binary (all panels pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (different linear algebra, VARPRO-style warm-started nonlinear R2\*, iterative sigma-clip echo rejection, exact 2×2 VFA solve; **no** import of the reference) reproduces every graded map to ~2e-8 (floating-point roundoff) and passes all panels. Wrong pipelines each fail only their own axis: **ignore B1** biases R1/MTsat on the inhomogeneous subjects; **compute MTsat for all** or **force R2\* on single-echo** fails the omit rule; a **non-robust R2\*** fit is biased only on the corrupted subjects; a **fixed 2-flip** solve is wrong only on the 3-flip subjects.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=3** | **0.0 (all 3)** | Solved **17/28 panels** every run (identical failing set): correct on the mild-B1 / standard subjects, but **R1 = 0% agreement on the 3 strong-B1 subjects** (did not correctly apply the B1+ correction) and **R2\* = 0% on the corrupted-echo subjects** (no robust echo rejection), plus PD-normalization errors. A clean, reproducible multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean MPM pipeline and applies it uniformly — it handles the standard subjects but does not correctly thread the per-subject B1+ correction through the strong-B1 subjects, nor discover-and-reject the unannounced corrupted echo volumes. Its underlying fits are otherwise correct (the omit-rule and mild-B1 panels pass), so the 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get a hundred coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (per-subject B1, the corrupted echoes, the omit forks) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`; verified by grep). Regenerable via `synth_build/generate_fixtures.py`; can be moved to Docker-build-time generation if the maintainer prefers no committed fixtures.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
