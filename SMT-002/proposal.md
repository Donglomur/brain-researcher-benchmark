## SMT-002

**Proposal Title:** Multi-compartment Spherical-Mean-Technique microstructure mapping of a heterogeneous multi-shell dMRI cohort — an execution-hard reconstruction task (shell-count recipe divergence + coupled spherical-mean assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure

**Source paper:** Kaden et al. 2016, *NeuroImage* (multi-compartment microscopic diffusion imaging / Spherical Mean Technique, https://doi.org/10.1016/j.neuroimage.2016.06.002). Dataset: a **synthetic** multi-shell diffusion-MRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the per-voxel microFA, Fintra, Dintra maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's reconstruction tasks (e.g. `pcasl-cbf-quantifier`): the agent implements the multi-compartment SMT inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** orientation-invariant quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. Two subjects have a **single** non-zero shell, where the intra-neurite fraction f and the intrinsic diffusivity λ cannot be separated (the micro-model is under-determined) and **all** maps must be **omitted**; the rest have two or three shells that identify the model. The per-subject shell b-values and direction counts differ, so the spherical-mean model is subject-specific.
2. **Coupled-physics assembly** — the robust powder (spherical) average with b=0 normalisation, the two-compartment spherical-mean kernel (an erf function of b·λ), the tortuosity constraint that ties the extra-neurite radial diffusivity to (1−f)·λ, the joint non-linear (f, λ) fit, and the microscopic-FA computed from the micro-tensor eigenvalues must **all** be assembled correctly; an error in any one compounds.
3. **Hidden robustness** — a **majority** of subjects (five of eight) carry one to three grossly corrupted gradient-direction volumes (signal dropout or spike) that must be **rejected** before the per-shell powder average (a global dropout/spike shifts a volume's mean-over-mask level far from the shell median while clean volumes scatter only a few percent), or the fitted micro-parameters are biased. This is never announced in `instruction.md`.
4. **Convention-invariant grading** — microFA, Fintra, and Dintra are orientation-invariant by construction (the powder average removes fibre orientation) and uniquely determined given the pinned kernel; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled DWI series with a **held-out reference** pipeline (`smt_pipeline` + `smt_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise** over the tissue mask, one parametrized test per (subject × map) panel (24 panels). A computable map passes when ≥90% of tissue voxels agree within a per-map tolerance (microFA rtol 5%/atol 0.03; Fintra rtol 5%/atol 0.03; Dintra rtol 6%/atol 0.08); an unsupported map (a single-shell subject) passes only when the submission **omits** it. Reward is binary (all panels pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent implementation (scipy per-voxel non-linear least squares, a different fixed-relative-deviation volume-rejection rule, a different b=0 reduction, sharing **no** code with the reference) reproduces every computable panel to a median voxel difference ~1e-4 (microFA/Fintra) and ~5e-3 (Dintra) — far inside tolerance — so the maps are convention-invariant physical quantities. The plausible-but-wrong pipelines each fail on their own axis: computing the single-shell subjects fails only their 6 omit panels; skipping the corrupted-volume rejection fails only the 15 motion-corrupted panels; the naive uniform pipeline (both mistakes) fails 21/24 — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **9/24 panels**, failing the single-shell omit fork, the coupled spherical-mean kernel + tortuosity + microFA assembly, and the unannounced corrupted-volume-rejection axis the task is built around. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean SMT pipeline and applies it uniformly — solving some standard panels but missing the single-shell omit fork, the exact coupled two-compartment spherical-mean physics, and the robust discover-and-reject of the unannounced corrupted volumes. The fifteen failed panels are the ones gated on those hard axes; the k=1 gate reports the count (9/24), and a per-panel itemization will come from the maintainer's calibration run.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (assemble a coupled micro-diffusion model and get the per-subject decisions right with no fitter), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the single-shell omit fork, the corrupted volumes) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
