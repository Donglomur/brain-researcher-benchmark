## DSCSVD-002

**Proposal Title:** Quantitative DSC perfusion (rCBV / rCBF / rMTT) of a heterogeneous cohort by SVD deconvolution — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Perfusion MRI / dynamic susceptibility contrast (DSC)

**Source paper:** Østergaard et al. 1996, *MRM* (SVD deconvolution of DSC-MRI, https://doi.org/10.1002/mrm.1910360510); Wu et al. 2003, *MRM* (block-circulant / oSVD deconvolution, https://doi.org/10.1002/mrm.10522); Boxerman, Schmainda & Weisskoff 2006, *AJNR* (Boxerman-Weisskoff leakage correction). Dataset: a **synthetic** gradient-echo DSC first-pass cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce NAWM-normalized rCBV / rCBF / rMTT maps); the difficulty is *execution*. The agent implements the full quantitative DSC pipeline **from scratch** (no deconvolver is bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on **convention-invariant** (NAWM-normalized) quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar, via two coupled forks. (a) **AIF availability:** exams that captured a major artery provide an AIF, so CBF/MTT are determinable by deconvolution; exams with no AIF cannot be deconvolved, so rCBF and rMTT must be **omitted** (only the AIF-free rCBV is reported) — exactly like R2* on a single-echo scan. (b) **Blood-brain-barrier leakage:** flagged exams need the pinned Boxerman-Weisskoff baseline/integral correction of `dR2*(t)` **before** integration and deconvolution, whereas applying that same correction to a non-leakage exam biases its CBV — so the correction must be applied to *exactly the right subjects*.
2. **Coupled-physics assembly** — signal→`dR2*` conversion, the NAWM reference construction, the Boxerman-Weisskoff leakage fit, the block-circulant truncated-SVD deconvolution (PSVD=0.20), and the NAWM normalization must **all** be assembled correctly; an error in any one compounds.
3. **Hidden robustness** — the provided white-matter label is contaminated by gross large-vessel voxels that must be **excluded** from the NAWM reference (including them roughly doubles the normalization denominator and corrupts *every* map); per-voxel bolus-arrival delays vary (the block-circulant construction is what makes deconvolution delay-insensitive); the time-courses carry recirculation and noise. None of this is announced in `instruction.md`.
4. **Convention-invariant grading** — because the graded quantities are NAWM-normalized, the global scale (κ/ρ/hematocrit), the echo time, and the AIF amplitude all cancel, so the three quantities are uniquely determined by the pinned recipe; two independent correct implementations compute them identically (proven below).

### Verifier

`tests/` recomputes every map from the bundled signals with a **held-out reference** pipeline (`dsc_pipeline` + `dsc_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask — 24 (subject × map) panels, each its own test. A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (rtol 8%; atol 0.08–0.10 on the NAWM=1 scale); an unsupported map (rCBF/rMTT for a no-AIF exam) passes only when the submission **omits** it. The Harbor reward is 1 only if all panels pass.

**Grading-invariance proof (the key check).** Because the graded quantities are NAWM-normalized, a genuinely-correct independent implementation (different baseline statistic, integral discretization, leakage-fit backend, SVD backend, per-voxel loop; **no** import of the reference) reproduces every computable panel to well within tolerance (measured max ~3%). The plausible-but-wrong pipelines each fail only their own axis: **no leakage correction** fails the leakage exams' volume maps; **leakage correction everywhere** fails the non-leakage exams; **CBF/MTT without an AIF** fails the omit panels; **large vessels left in the NAWM reference** fails essentially every panel — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **11/24 panels** — correct on the straightforward volume maps, but failed the hard axes: the AIF-availability omit fork (rCBF/rMTT omitted with no AIF), applying the Boxerman-Weisskoff leakage correction to exactly the flagged subjects, excluding the gross large-vessel voxels from the NAWM reference, and the block-circulant truncated-SVD deconvolution. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model builds one DSC pipeline and applies it uniformly — it produces plausible normalized volume maps but does not thread the per-exam leakage fork, discover-and-exclude the large-vessel contamination of the NAWM reference, or correctly assemble the block-circulant SVD deconvolution. The passing panels show the concentration conversion and integration are otherwise correct, so the 0.0 is earned on the genuine hard axes.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional, unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the leakage fork, the AIF omit rule, the large-vessel contamination) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** in the data-provenance sense (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
