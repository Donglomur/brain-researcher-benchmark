## SANDI-002

**Proposal Title:** Soma-and-neurite (SANDI) spherical-mean microstructure inversion of a heterogeneous diffusion cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure

**Source paper:** Palombo et al. 2020, *NeuroImage* (SANDI: soma and neurite imaging, https://doi.org/10.1016/j.neuroimage.2020.116835); Murday & Cotts 1968 / Neuman 1974 (Gaussian-phase restricted-sphere signal); Kaden et al. 2016, *NeuroImage* (spherical-mean technique, https://doi.org/10.1016/j.neuroimage.2016.06.002). Dataset: a **synthetic** multi-shell spherical-mean diffusion-MRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth compartment maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce per-voxel neurite/extra/soma fractions and soma radius); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the three-compartment SANDI inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on convention-invariant physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the scheme forks, discoverable only from each sidecar: five subjects carry a high-b shell (b ≥ 3000 s/mm²) that resolves the restricted soma compartment (fit the full neurite+soma+extra model, report `f_soma` and `R_s`), while three subjects' maximum b is below 3000 so the soma is **unidentifiable** — they must be fit with a reduced neurite+extra model and `f_soma`/`R_s` **omitted** (like an absolute concentration with no water reference). A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — from the spherical (direction) mean per shell one must assemble the stick (neurite) kernel, the ball (extra-cellular) kernel, and — the delicate part — the Neuman/Murday-Cotts Gaussian-phase restricted-sphere (soma) kernel, whose gradient strength `g` is recovered from each shell's `(b, small_delta, big_delta)` via `b = γ²g²δ²(Δ − δ/3)`. Because the per-subject gradient pulse timings **differ**, a fixed b-keyed sphere dictionary is wrong and biases `R_s`.
3. **Hidden robustness** — two off-critical-path hazards are un-cued: a majority of subjects (all five soma-resolvable ones) carry one or two grossly motion-corrupted gradient volumes that must be **detected and rejected before the spherical-mean average** or every fitted fraction is biased; and a rim of near-isotropic free-water/CSF voxels inside the brain mask must be excluded from the tissue fit. Neither is announced in `instruction.md`.
4. **Convention-invariant grading** — the fractions and `R_s` are uniquely-determined least-squares optima of the multi-shell spherical-mean decay; a genuinely-independent implementation reproduces every computable panel to within max 6e-4 of the reference (proven below), so a from-scratch solver can pass while wrong pipelines fail.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled DWI volumes with a **held-out reference** pipeline (`sandi_pipeline` + `sandi_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the reference's tissue grade-mask (near-isotropic free-water voxels excluded; `R_s` graded only where the fitted soma fraction is non-trivial). There are **32 (subject × map) panels**, each its own test. Reward is **fractional** — the score is the fraction of panels correct. A computable map passes when ≥90% of graded voxels agree within a per-map tolerance (fractions rtol 10%/atol 0.05; `R_s` rtol 8%/atol 0.3 µm); an unsupported map (`f_soma`/`R_s` for a subject whose max b < 3000 s/mm²) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (hard-coded sphere roots, a different corrupted-volume vote, a pure continuous multistart fit; **no** shared code) reproduces every computable panel to within max 6e-4 of the reference. The plausible-but-wrong pipelines each fail only their axis: **fit the soma for everyone / omit it for everyone** fails the divergence panels; a **fixed sphere dictionary** biases `R_s` only on the subjects whose timing differs; a **non-robust spherical mean** biases the fractions only on the motion-corrupted subjects. A naive uniform-recipe / no-robustness / no-omit pipeline scores only 2/32, so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **14/32 panels**, failing the hard axes — the soma determinability fork (fitting or omitting `f_soma`/`R_s` per the high-b shell), the per-subject sphere kernel derived from the `(b, small_delta, big_delta)` timings, the unannounced corrupted-volume rejection on the five soma-resolvable subjects, and the free-water/CSF voxel exclusion. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single SANDI fit and applies it broadly — it recovers the well-conditioned neurite/extra fractions on some subjects but does not correctly thread the soma-determinability fork, the timing-dependent sphere kernel, the unannounced corrupted-volume rejection, or the free-water exclusion. Its underlying spherical-mean fit is partly correct (roughly half the panels pass), so the 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (assemble a coupled multi-compartment inversion with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the kernel/determinability conventions but never enumerates the pitfalls (the timing-dependent sphere kernel, the corrupted volumes, the free-water rim) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`; `fixture_spec.json` is build-provenance only). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
