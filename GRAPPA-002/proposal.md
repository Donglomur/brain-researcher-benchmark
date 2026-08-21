## GRAPPA-002

**Proposal Title:** GRAPPA parallel-imaging reconstruction of a heterogeneous multi-coil cohort — an execution-hard reconstruction task (recipe divergence + coupled k-space bookkeeping + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** MRI image reconstruction / parallel imaging

**Source paper:** Griswold et al. 2002, *Magn. Reson. Med.* (generalized autocalibrating partially parallel acquisitions / GRAPPA, https://doi.org/10.1002/mrm.10171). Dataset: a **synthetic** accelerated multi-coil MRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth reconstruction held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the coil-combined magnitude image per subject); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements GRAPPA **from scratch** (no recon library bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded per-pixel against a **held-out reference** on a **convention-invariant** (median-normalised) magnitude.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the acceleration `R` varies (2, 3, 4), so a subject needs `R−1` **separate** shift-invariant kernel fits, one per missing phase-encode offset; a pipeline that assumes a single offset (the R=2 case) leaves six of eight subjects grossly aliased. The calibration kernel geometry is per-subject. A single fixed recipe cannot reconstruct the cohort.
2. **Coupled k-space bookkeeping** — placing the acquired undersampled lines on the full DC-centered grid, assembling the source/target neighbourhoods across all coils, fitting the kernel weights from the ACS by least squares, synthesising every missing line, `ifft2(ifftshift(·))` per coil, and root-sum-of-squares combination must **all** be assembled correctly; an error in any one produces coherent residual aliasing.
3. **Hidden robustness (the decisive axis)** — six of eight subjects carry a pair of grossly motion-corrupted ACS lines that must be rejected before the least-squares kernel fit. The corrupt lines are planted in the low-energy transition zone of the ACS block, whose centre-of-k-space rows are legitimately ~9–16× brighter, so a **global** energy/z-score threshold cannot separate them (a loose cut deletes the bright legitimate centre rows → degenerate fit; a tight cut misses the edge spikes → aliased weights) and a single-shot "drop the worst row" leaves the second spike — only a **local-baseline, iterative** robust estimator works. Three subjects additionally have a dead (noise-only) receive channel that must be excluded from both the kernel fit and the RSS combination. None of this is announced in `instruction.md`.
4. **Convention-invariant grading** — each image is normalised by its median over the object, removing the arbitrary receive-gain / DFT-normalisation scale, so the graded quantity is the spatial content (residual aliasing) alone; two independent correct implementations agree to within tolerance (proven below).

### Verifier

`tests/test_outputs.py` recomputes the reference GRAPPA reconstruction for every subject from the bundled undersampled + ACS k-space with a **held-out reference** core (`grappa_pipeline` + `grappa_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades per subject, voxelwise over the object mask (**8 panels**, each its own test). Reward is **fractional** — the score is the fraction of subjects reconstructed correctly. A subject passes when ≥90% of object-mask pixels of the median-normalised magnitude agree with the reference within 0.10.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (augmented-ridge `lstsq` via gelsd vs normal equations; a **different** dead-coil detector — ACS row-energy peak/median concentration vs coil-median correlation; a **different** corrupt-line detector — a Hampel local-window energy ratio vs a MAD z-score on a log-energy median-baseline residual; a wider RO kernel) reproduces every subject to within tolerance (worst median |delta| ~0.02, ≥99.6% of pixels within tolerance on every panel), and both detectors independently agree on exactly which rows/coils to drop for every subject — so the graded quantity does not depend on the particular robust estimator. A **non-robust** uniform pipeline (correct heterogeneous GRAPPA but no ACS-line rejection, all coils kept) reconstructs only 1 of 8; a **global-threshold or single-shot** ACS rejection — the intuitive shortcut — still fails a majority (0–2 of 8). Partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **1/8 panels** (only the single defect-free subject, `sub-01`), failing the hard axes — the `R−1` separate kernel fits for the R>2 subjects (single-offset recon leaves them aliased), the local-baseline iterative ACS-line rejection for the 6 corrupted subjects (a global/single-shot cut under- or over-rejects), and the dead-channel exclusion for the 3 coil-dropout subjects. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean R=2 GRAPPA recon with all coils and no ACS-line rejection and applies it uniformly — it reconstructs only the one defect-free subject, and does not discover the per-subject acceleration fork, the unannounced corrupted ACS lines (which sit below the legitimate bright centre rows and need a local iterative estimator), or the dead channels. The single solved panel confirms the k-space core is otherwise correct, so the 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (assemble a coupled k-space reconstruction with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the k-space/coil conventions but never enumerates the pitfalls (the per-R offsets, the corrupted ACS lines, the dead channels) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted reconstruction are never under `/app/data`; `fixture_spec.json` is build-provenance only). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
