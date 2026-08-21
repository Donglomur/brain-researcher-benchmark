## UFA-002

**Proposal Title:** Microscopic anisotropy (uFA) from a heterogeneous b-tensor-encoding cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure

**Source paper:** Lasic et al. 2014, *Frontiers in Physics* (microscopic diffusion anisotropy / uFA from variable b-tensor shape, https://doi.org/10.3389/fphy.2014.00011); Westin et al. 2016, *NeuroImage* (q-space trajectory / b-tensor encoding, https://doi.org/10.1016/j.neuroimage.2016.02.039). Dataset: a **synthetic** b-tensor-encoding diffusion cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (produce per-voxel MD/uFA/Ciso maps); the difficulty is *execution*, not an un-cued judgement. The agent implements a microscopic-anisotropy inversion from b-tensor-encoding data **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar's per-volume list of b-tensor **shapes** (linear LTE b_Δ=+1, planar PTE b_Δ=−1/2, spherical/isotropic STE b_Δ=0). Separating isotropic variance V_iso from anisotropic variance V_aniso — hence uFA — requires **≥2 distinct shapes**: an LTE-only or PTE-only subject confounds them and **uFA and Ciso must be omitted**; an STE-only subject determines V_iso (Ciso) but not V_aniso (uFA must be omitted); only a ≥2-shape subject supports all three maps.
2. **Coupled-physics assembly** — the powder (direction-averaged) signal of each shape follows the second-order cumulant model Sbar_s(b)=S0·exp(−b·MD + ½·b²·C2_s) with C2_s = V_iso + (4/5)·b_Δ(s)²·V_aniso; MD and S0 are **shared** across all shapes (a shared-slope joint fit) and only the curvature depends on shape. The shared-slope log-quadratic powder fit, the per-shape b_Δ variance split with the 4/5 powder factor, and the uFA normalisation must **all** be assembled correctly; an error in any one compounds.
3. **Hidden robustness** — a majority of subjects (6 of 8) carry one or two grossly corrupted diffusion volumes (motion dropout / spike) that must be **rejected** before the joint powder fit, or the shared MD and every curvature (and thus every downstream map) are biased; never announced in `instruction.md`.
4. **Convention-invariant grading** — MD, uFA, and Ciso are uniquely determined given the pinned cumulant model and b_Δ split; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled volumes with a **held-out reference** pipeline (`ufa_pipeline` + `ufa_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map) panel — **24 panels** in all. Reward is **fractional** (each panel its own test). A determinable map passes when ≥90% of brain voxels agree within a per-map tolerance (MD rtol 5%/atol 0.02; uFA rtol 8%/atol 0.04; Ciso rtol 15%/atol 0.02); an undeterminable map (uFA for a single-shape subject, Ciso for an LTE-only or PTE-only subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (model-free shell-local outlier rejection, explicit powder-average, single-stage direct V_iso/V_aniso linear fit via a different backend) reproduces every determinable panel to well within tolerance (worst-case median relative error <0.4%, every panel ≥90% agreement). The plausible-but-wrong pipelines each fail only their own panels: an **omit-rule violation** scores 0.79, a **shape-ignoring split** 0.75, a **wrong uFA normalisation** 0.79, a **non-robust fit** 0.46, and a naive uniform/non-robust/no-omit baseline scores 0.25 (fails 18 of 24 panels, spanning 7 of 8 subjects) — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **11/24 panels**, failing the shared-slope joint powder fit, the b-tensor-shape variance split (V_iso/V_aniso), the uFA/Ciso omit rules by encoding set, and the unannounced corrupted-volume rejection. |
| **2nd frontier family (Claude/Gemini)** | _pending_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements one clean uFA pipeline and applies it uniformly — it does not run the shared-slope joint powder fit with the correct b_Δ variance split, honour the uFA/Ciso omit rules per encoding set, nor discover-and-reject the unannounced corrupted volumes. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the coupled powder physics, variance split, and per-subject forks right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and pins the conventions but never enumerates the pitfalls (the shape-set forks, the corrupted volumes, the variance split) — the agent must discover them.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
