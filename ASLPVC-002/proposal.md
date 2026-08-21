## ASLPVC-002

**Proposal Title:** Partial-volume correction of a heterogeneous ASL cerebral-blood-flow cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Perfusion MRI / arterial spin labelling

**Source paper:** Asllani, Borogovac & Brown 2008, *MRM*, "Regression algorithm correcting for partial volume effects in arterial spin labeling MRI" (https://doi.org/10.1002/mrm.21670). Dataset: a **synthetic** ASL perfusion cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth pure-tissue CBF held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (recover per-voxel pure-tissue CBF by the linear-regression PVC and write the maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the windowed partial-volume regression **from scratch** (no reference bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each sidecar: a `probabilistic` subject ships soft GM **and** WM tissue-fraction maps and needs the full 2-compartment regression (design `[P_GM, P_WM]`, CSF excluded as non-perfusing) yielding **both** pure GM and pure WM CBF, while a `gm_only` subject ships **only** a GM fraction map and needs a single-compartment regression (design `[P_GM, 1-P_GM]`) yielding pure GM CBF alone — pure WM CBF is not determinable from a GM-only segmentation and must be **omitted** (like an absolute concentration with no water reference). A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the correction is a coupled *spatial* fit: for every voxel the measured CBF of the surrounding in-plane kernel (a per-subject pinned half-width) is regressed on the kernel voxels' tissue fractions to recover the locally-constant pure-tissue CBF. The array must be reshaped to the 3-D grid, sliced and windowed correctly, CSF/edge partial-volume voxels must not be turned into spurious pure-tissue CBF, and the units (mL/100g/min) kept right; an error in any one compounds across the (subject × map) panels.
3. **Hidden robustness** — a **majority** of subjects carry a sparse set of grossly corrupted (intravascular / motion-spike) voxels that a plain least-squares fit smears into every kernel that touches them, biasing the pure-tissue CBF of a large neighbourhood; these must be detected as gross residual outliers and rejected (a modified least-trimmed-squares fit) before the estimate is trustworthy. This is never announced in `instruction.md`.
4. **Convention-invariant grading** — the pure GM and WM CBF are locally-constant physical quantities uniquely determined by the pinned mixture model and sidecar kernel, so two independent correct implementations recover them identically (proven below); a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every pure-tissue map from the bundled measured CBF + tissue fractions with a **held-out reference** pipeline (`pvc_pipeline` + `pvc_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the per-map determinability mask (interior voxels where the windowed design has leverage for that compartment), one parametrized test per (subject × map) panel. A computable map passes when ≥90% of determinable voxels agree within a per-map tolerance (CBF_GM rtol 8%/atol 3; CBF_WM rtol 10%/atol 3 mL/100g/min); an unsupported map (CBF_WM for a `gm_only` subject) passes only when the submission **omits** it. Reward is binary (all 16 panels pass → 1.0).

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation (roll-based kernel gather, batched normal-equations solve, Tukey-biweight IRLS robustness — a different method, **no** import of the reference) reproduces every computable panel with <1% voxel disagreement (worst panel 0.73%); adjacent kernel sizes agree within tolerance on ≥97.5% of voxels, so the graded quantity is convention-invariant given the sidecar-pinned kernel. Wrong pipelines each fail only their own axis: **no PVC** (report measured CBF as pure GM) fails 3/16; a **global** instead of windowed fit fails 8/16 (wherever CBF varies spatially); a **non-robust** fit fails 8/16 (only the corrupted subjects); **forcing a WM map** where the segmentation is GM-only fails the omit rule (13/16); a naive uniform pipeline (non-robust *and* no omit fork) fails 11/16 — a majority.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **8/16 panels**, failing the hard axes: the windowed vs global spatial fit, the robust rejection of the grossly corrupted (intravascular/motion) voxels on the majority of subjects, and/or the single- vs two-compartment omit fork on the `gm_only` subjects. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean PVC pipeline and applies it uniformly — it handles the standard panels but does not correctly thread the per-subject windowed spatial regression with robust outlier rejection, nor discover-and-omit the WM compartment where only a GM segmentation exists. The 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get many coupled per-voxel spatial-regression decisions right with no bundled fitter), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the mixture-model conventions but never enumerates the pitfalls (the per-subject kernel, the corrupted voxels, the single-compartment omit fork) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`; verified by grep). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
