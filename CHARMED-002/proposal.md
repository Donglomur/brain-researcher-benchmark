## CHARMED-002

**Proposal Title:** Composite hindered-and-restricted (CHARMED) diffusion inversion of a heterogeneous multi-shell dMRI cohort — an execution-hard reconstruction task (b-range recipe divergence + coupled restricted-diffusion physics + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure

**Source paper:** Assaf & Basser 2005, *NeuroImage* (composite hindered-and-restricted model of diffusion / CHARMED, https://doi.org/10.1016/j.neuroimage.2005.03.042); Van Gelderen et al. 1994, *J. Magn. Reson. B* (restricted-diffusion cylinder expression). Dataset: a **synthetic** multi-shell diffusion-MRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth parameters held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce MD, f_restricted, MD_hindered maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's reconstruction tasks (e.g. `pcasl-cbf-quantifier`): the agent implements the two-compartment diffusion inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar. The primary divergence is a **b-range fork**: multi-shell high-b subjects (b up to ~7–10k s/mm²) can separate the restricted intra-axonal compartment from the hindered extra-axonal one, so the restricted signal fraction and hindered MD are determinable and the full two-compartment fit applies; low-b-only subjects (b ≤ 1000) **cannot** separate the compartments — the restricted fraction and hindered MD are undefined and must be **omitted**, leaving only a DTI mean diffusivity. One low-b subject even carries two shells, so a shell-count heuristic mis-classifies it — the high-b *content* is what matters.
2. **Coupled-physics assembly** — the finite-pulse b = γ²G²δ²(Δ−δ/3) relation must be inverted **per subject** to get the gradient strength (δ/Δ vary across the cohort); the pinned Van Gelderen cylinder expression must be summed over the roots of J1′(x)=0 and evaluated at the **per-direction** perpendicular gradient component; and the hindered tensor, the restricted-parallel free-diffusion term, and the f/Dpar/Dperp/orientation nonlinear fit must all be assembled correctly. An error in any one compounds across the (subject × map) panels.
3. **Hidden robustness** — a **majority** of subjects (six of eight) carry several grossly corrupted whole DWI volumes (bulk-motion signal dropout) that are **not announced** and must be detected and rejected (a per-shell robust outlier test against a per-voxel angular baseline) before the DTI and CHARMED fits, or MD and the restricted fraction are biased on exactly those subjects.
4. **Convention-invariant grading** — f_restricted (dimensionless), MD_hindered and MD (µm²/ms) are uniquely determined given the pinned signal model; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled signals with a **held-out reference** pipeline (`charmed_pipeline` + `charmed_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **voxelwise**, one parametrized test per (subject × map) panel (24 panels). MD is graded over the brain mask; f_restricted and MD_hindered over the white+grey matter within it. A computable map passes when ≥90% of graded voxels agree within a per-map tolerance (f_restricted rtol 12%/atol 0.05; MD_hindered rtol 12%/atol 0.06 µm²/ms; MD rtol 5%/atol 0.03 µm²/ms); an unsupported map (restricted fraction / hindered MD for a low-b-only subject) passes only when the submission **omits** it. Reward is binary (all panels pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent implementation (a full 5-parameter nonlinear CHARMED fit with a different optimiser and a different corrupted-volume detector; **no** import of the reference) reproduces every computable panel within tolerance (24/24). The plausible-but-wrong pipelines each fail only their own axis: **skipping corrupted-volume rejection** fails MD and MD_hindered on the corrupted subjects; **ignoring the omit rule** fails the restricted-fraction / hindered-MD panels on the low-b-only subjects; a naive uniform pipeline scores 8/24 — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **11/24 panels**, failing the b-range omit fork, the coupled finite-pulse / Van Gelderen restricted-diffusion physics, and the unannounced corrupted-volume-rejection axes the task is built around. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean CHARMED/DTI pipeline and applies it uniformly — solving the standard panels but missing the b-range omit fork (restricted fraction / hindered MD only where high-b separates the compartments), the exact coupled restricted-diffusion physics, and the discover-and-reject of the unannounced corrupted volumes. The thirteen failed panels are the ones gated on those hard axes; the k=1 gate reports the count (11/24), and a per-panel itemization will come from the maintainer's calibration run.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (get a hundred coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the b-range fork, the two-shell low-b decoy, the corrupted volumes) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
