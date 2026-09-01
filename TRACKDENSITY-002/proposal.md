## TRACKDENSITY-002

**Proposal Title:** Track-density imaging (TDI) of a heterogeneous tractography cohort — an execution-hard reconstruction task (recipe divergence + coupled-geometry assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / tractography

**Source paper:** Calamante et al. 2010, *NeuroImage* (track-density imaging: super-resolution white-matter imaging via whole-brain track-density mapping, https://doi.org/10.1016/j.neuroimage.2010.07.024). Dataset: a **deterministic** whole-brain tractography cohort (8 subjects), generated at `synth_build/generate_fixtures.py`; the planted ground-truth count maps (exact track density of the anatomical streamlines) are held out under `tests/planted_truth.npz` (built by `synth_build/build_truth.py`, never shipped under `environment/data`).

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (per-cell track-density maps from each streamline set); the difficulty is *execution*, not an un-cued judgement. The agent implements TDI **from scratch** (no tractography / mapping library bundled), over a **heterogeneous cohort where subjects need different outputs**, with a **declared robustness** requirement (the realization hidden), graded cellwise against the **planted geometry** on **convention-invariant** integer counts.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different outputs*, decided from each tractogram: **dense** tractograms (≥ `n_min` streamlines) support the super-resolution track-density map on a grid `super_factor`-times finer than native, while **sparse** tractograms do **not** — the super-resolution grid would be a scatter of isolated single-streamline cells, so `tdi_super` is not determinable and must be **omitted** (native map only). A single fixed recipe cannot fit the cohort.
2. **Coupled-geometry assembly** — the count is a coupled geometric assembly that must **all** be right or every count is wrong: invert each subject's world→voxel affine, build the super grid as `native × super_factor` sharing the world corner, and — the crux — perform **exact piece-wise-linear segment/voxel traversal** so every super-resolution cell a streamline's polyline crosses is counted (each streamline once per cell), **not** merely the cells that contain a stored vertex (vertex/point binning badly undercounts the finer grid; it is the classic TDI pitfall).
3. **Declared robustness, hidden realization** — a **majority** of the cohort's raw tractograms carry many spurious/truncated fragment streamlines — tiny stubs far shorter than any anatomical streamline (a grossly bimodal length distribution with a wide empty gap) — which must be excluded before counting, or the maps are stippled with false density. `instruction.md` now **declares** that such fragments exist and must be excluded; only the *realization* (which subjects / which streamlines) is hidden and must be discovered from the data.
4. **Convention-invariant grading** — the graded quantity is an integer count per cell fixed by the segment-intersection definition; two independent exact traversals produce **bit-identical** maps — no reporting-convention ambiguity.

### What changed in this revision (addressing the review of the hidden-contract version)

1. **Robustness contract made public.** `instruction.md` now states, under *Robustness / data-quality contract*, that the raw tractograms carry spurious short fragment streamlines that must be excluded before counting — only the *realization* (which subjects/streamlines) is hidden. A correct pipeline is no longer penalized for failing to guess an undeclared step.
2. **Graded against the true geometry, not one traversal.** The verifier no longer recomputes with a private pipeline on the real data and demands agreement. It compares each submitted count map, cellwise, to the **held-out planted target** = the exact track density of the anatomical streamlines (`tests/planted_truth.npz`, built by `synth_build/build_truth.py`). Because TDI is deterministic geometry and the fragment threshold sits in a wide bimodal gap, **any valid implementation** returns the identical integer counts. The hidden reference modules were removed from `tests/`.

### Verifier

`tests/test_outputs.py` grades **cellwise** against `tests/planted_truth.npz`. Each of the 16 (subject × map) panels is its own parametrized test; the score is the fraction of panels correct. A computable map passes when ≥97% of the graded cells (the union of planted-occupied and submission-occupied cells, so both missing and spurious density are penalised) match the planted count within ±0.5; an unsupported map (`tdi_super` for a sparse subject) passes only when the submission **omits** it.

**Validity / discrimination evidence (recomputed for this revision).** The oracle recovers the planted target on **all 16 panels (13 computable exactly, 3 correctly omitted)**. Because TDI is deterministic geometry and the fragment threshold sits in a wide bimodal length gap, any exact independent traversal reproduces the integer counts to the cell. A **naive submission that keeps the fragment streamlines** (robustness knob disabled) fails **10 panels** through the real verifier — every panel of the six fragment-bearing subjects — while the two fragment-free subjects (sub-04, sub-07) still pass and the sparse-subject omit forks are unaffected. So a correct robust solver passes and the robustness/omit shortcuts fail, on axes the instruction *declares*.

### Difficulty — frontier gate

Oracle **reward 1.0** verified in-container (deterministic). On the *previous* (hidden-contract) version, **gpt-5.6-sol (codex, xhigh) scored 0.0**, solving 6/16 panels — falling into the vertex-binning pitfall on the finer grid, not excluding the fragment streamlines, and/or mishandling the sparse-subject `tdi_super` omit rule.

**Frontier re-gate on this revised (public-contract) version: PENDING.** Because the revision *discloses* the fragment-exclusion requirement, the old gate number does not transfer and must be re-measured — not overclaimed here. The expectation is that the exact sub-voxel segment/voxel traversal (the anti-vertex-binning crux), the world→voxel affine + super-grid assembly, discover-and-exclude the hidden fragments, and the dense-vs-sparse omit fork remain hard; the local discrimination above shows the robustness shortcut still fails. A 2nd frontier family (Claude/Gemini) gate is likewise pending at maintainer calibration.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (exact geometric traversal, fragment rejection, and the dense-vs-sparse omit fork with no bundled library), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the pinned definitions but never flags the fragment streamlines — the agent must discover them.
- **Data.** Deterministic, small, and **leakage-clean** (the planted count maps live only in `tests/planted_truth.npz`, never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py` + `synth_build/build_truth.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
