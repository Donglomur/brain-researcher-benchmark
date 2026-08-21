## TRACKDENSITY-002

**Proposal Title:** Track-density imaging (TDI) of a heterogeneous tractography cohort — an execution-hard reconstruction task (recipe divergence + coupled-geometry assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / tractography

**Source paper:** Calamante et al. 2010, *NeuroImage* (track-density imaging: super-resolution white-matter imaging via whole-brain track-density mapping, https://doi.org/10.1016/j.neuroimage.2010.07.024). Dataset: a **synthetic** whole-brain tractography cohort (8 subjects), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth count maps held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (per-cell track-density maps from each streamline set); the difficulty is *execution*, not an un-cued judgement. The agent implements TDI **from scratch** (no tractography / mapping library bundled), over a **heterogeneous cohort where subjects need different outputs**, with a **hidden robustness** requirement, graded cellwise against a **held-out reference** on **convention-invariant** integer counts.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different outputs*, decided from each tractogram: **dense** tractograms (≥ `n_min` streamlines) support the super-resolution track-density map on a grid `super_factor`-times finer than native, while **sparse** tractograms do **not** — the super-resolution grid would be a scatter of isolated single-streamline cells, so `tdi_super` is not determinable and must be **omitted** (native map only). A single fixed recipe cannot fit the cohort.
2. **Coupled-geometry assembly** — the count is a coupled geometric assembly that must **all** be right or every count is wrong: invert each subject's world→voxel affine, build the super grid as `native × super_factor` sharing the world corner, and — the crux — perform **exact piece-wise-linear segment/voxel traversal** so every super-resolution cell a streamline's polyline crosses is counted (each streamline once per cell), **not** merely the cells that contain a stored vertex (vertex/point binning badly undercounts the finer grid; it is the classic TDI pitfall).
3. **Hidden robustness** — un-announced, a **majority** of the cohort's raw tractograms carry many spurious/truncated fragment streamlines — tiny stubs far shorter than any anatomical streamline (a grossly bimodal length distribution with a wide empty gap) — which must be excluded before counting, or the maps are stippled with false density. This is never flagged in `instruction.md`.
4. **Convention-invariant grading** — the graded quantity is an integer count per cell fixed by the segment-intersection definition; two independent exact traversals produce **bit-identical** maps (proven below) — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every count map from the bundled streamlines with a **held-out reference** pipeline (`tdi_pipeline` + `tdi_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **cellwise**. Each of the 16 (subject × map) panels is its own parametrized test; per-panel scoring is fractional-intent, but the Harbor reward is binary — any failed panel zeroes it. A computable map passes when ≥97% of the graded cells (the union of reference-occupied and submission-occupied cells, so both missing and spurious density are penalised) match the reference count within ±0.5; an unsupported map (`tdi_super` for a sparse subject) passes only when the submission **omits** it.

**Grading-invariance proof (the key check).** Two genuinely-independent **exact** traversals — an Amanatides–Woo 3-D DDA in the reference and a parametric grid-plane-crossing method (with an automatic fragment-length cut) as an independent check — reproduce every computable panel **to the bit** (max |Δ| = 0 over every occupied cell). The plausible-but-wrong pipelines each fail only their own axis: **vertex/point binning** fails every fine-grid count; **keeping the fragments** fails the subjects that carry them; **computing super for sparse subjects** violates the omit rule; **block-upsampling** the native map instead of recomputing on the finer grid fails only the super panels — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **6/16 panels** — 10 failed. The model does not implement exact segment/voxel traversal (the anti-vertex-binning crux), does not exclude the spurious fragment streamlines, and/or mishandles the sparse-subject `tdi_super` omit rule; the binary Harbor reward zeroes on any failed panel. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model produces plausible native maps for some subjects but falls into the classic vertex-binning pitfall on the finer grid, does not reject the fragment streamlines that stipple the counts, and does not thread the dense-vs-sparse omit fork — so it clears only 6/16. A clean, reproducible multi-axis execution failure on the genuine hard axes.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (exact geometric traversal, fragment rejection, and the dense-vs-sparse omit fork with no bundled library), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the pinned definitions but never flags the fragment streamlines — the agent must discover them.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted maps are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
