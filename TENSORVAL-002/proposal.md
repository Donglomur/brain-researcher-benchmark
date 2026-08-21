## TENSORVAL-002

**Proposal Title:** Mean-kurtosis decomposition and microFA from a heterogeneous tensor-valued diffusion-encoding cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure (tensor-valued encoding)

**Source paper:** Westin et al. 2016, *NeuroImage* (q-space trajectory imaging / QTI, https://doi.org/10.1016/j.neuroimage.2016.02.039); Lasič et al. 2014, *Front. Phys.* (microscopic anisotropy / microFA, https://doi.org/10.3389/fphy.2014.00011). Dataset: a **synthetic** tensor-valued diffusion-encoding cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth kurtosis/microFA maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce per-voxel MD, MK, MKi, MKa, microFA maps where determinable); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the shared-slope powder kurtosis decomposition **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on convention-invariant physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — which maps a subject supports depends on its encoding set and must be decided per subject from each sidecar's per-volume list of b-tensor **shapes** (LTE `b_Δ=+1`, PTE `b_Δ=−1/2`, STE `b_Δ=0`): a ≥2-distinct-shape subject supports the full MKi/MKa split (and microFA); an LTE-only subject can report only the total MK (the split is confounded → omit MKi/MKa/microFA); an STE-only subject determines V_iso hence MKi but has no anisotropic information and no LTE powder total (omit MKa/microFA/MK). Critically the split is **not** gated on STE presence — an LTE+PTE subject also determines both variances, so keying the fork on "STE present" is wrong. A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — one joint log-quadratic powder fit with a **shared** `b=0` intercept + **shared** MD slope + one curvature `C2_s` per shape, the per-shape variance split `C2_s = V_iso + (4/5)·b_Δ(s)²·V_aniso` with the `4/5` powder factor, and the kurtosis / microFA normalisations (`MKi=3V_iso/MD²`, `MKa=(12/5)V_aniso/MD²`, `MK=3C2_LTE/MD²`, `microFA=√((3/2)V_aniso/(V_aniso+V_iso+MD²))`) must **all** be assembled correctly; an error in any one compounds.
3. **Hidden robustness** — a majority of subjects (5 of 8) carry one or two grossly corrupted diffusion volumes (dropout/spike) that must be **rejected** before the joint powder fit, or the shared MD and every curvature (and thus every downstream kurtosis map) are biased; this is never announced in `instruction.md`.
4. **Convention-invariant grading** — the graded quantities are uniquely-defined functions of the shared-slope powder fit; a genuinely-independent implementation reproduces every determinable panel to a worst-case median relative error of 0.4% (proven below), so a from-scratch solver can pass while wrong pipelines fail.

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled volumes with a **held-out reference** pipeline (`tensorval_pipeline` + `tensorval_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map). There are **40 panels** (8 subjects × {MD, MK, MKi, MKa, microFA}). A determinable map passes when ≥90% of brain voxels agree within a per-map tolerance (MD rtol 5%/atol 0.02; MK rtol 6%/atol 0.03; MKi rtol 8%/atol 0.02; MKa rtol 8%/atol 0.03; microFA rtol 8%/atol 0.04); an undeterminable map (the MKi/MKa split for a single-shape subject, MK for an STE-only subject) passes only when the submission **omits** it. Reward is binary (1 only when every panel is correct).

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (model-free shell-local outlier rejection, an explicit powder-average, a single-stage direct V_iso/V_aniso linear fit via a different backend; **no** shared code) reproduces every determinable panel to well within tolerance (worst-case median relative error 0.4%, all 40 panels correct), establishing convention-invariance. The plausible-but-wrong pipelines each fail only their axis: an omit-rule violation scores 28/40; a shape-ignoring (mislabel) split 23/40; a dropped `4/5` factor 29/40; a wrong MKa coefficient 36/40; a wrong microFA normalisation 36/40; a non-robust fit 25/40; and the naive uniform/non-robust/no-omit baseline scores 13/40 (fails 27 of 40 panels spanning 6 of 8 subjects), so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **25/40 panels**: correct on the well-conditioned MD and the determinable kurtosis maps for the standard subjects, but failed the hard axes — the per-subject encoding-set determinability fork / omit rule (LTE-only → MK only, STE-only → MKi only, split only with ≥2 distinct shapes) and the unannounced corrupted-volume rejection on the 5 motion-affected subjects. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single kurtosis-decomposition fit and applies it broadly — it recovers MD and the determinable kurtosis maps on the standard subjects but does not correctly thread the encoding-set determinability fork (mis-keying the split, or violating the omit rule), nor discover-and-reject the unannounced corrupted volumes. Its underlying joint fit is largely correct (a majority of panels pass), so the 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (assemble a coupled shared-slope inversion and decide determinability with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the encoding/kurtosis conventions but never enumerates the pitfalls (the determinability fork, the corrupted volumes) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`; `fixture_spec.json` is build-provenance only). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
