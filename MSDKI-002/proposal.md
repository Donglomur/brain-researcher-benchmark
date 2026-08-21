## MSDKI-002

**Proposal Title:** Mean-signal diffusion-kurtosis (MSDKI) inversion of a heterogeneous multi-shell cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Diffusion MRI / microstructure

**Source paper:** Jensen & Helpern 2010, *NMR Biomed.* (diffusion kurtosis imaging, https://doi.org/10.1002/nbm.1518); Henriques et al. 2021, *Magn. Reson. Med.* (robust mean-signal / powder-averaged DKI, https://doi.org/10.1002/mrm.28730). Dataset: a **synthetic** multi-shell diffusion-MRI cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth MSD/MSK held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce per-voxel MSD and, where determinable, MSK maps); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the MSDKI inversion **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded voxelwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable only from each subject's b-values: with ≥2 distinct non-zero shells both MSD and MSK are determined by the quadratic log-signal fit, whereas a single-non-zero-shell subject determines **only** MSD from the two-point mono-exponential slope and MSK is **not computable and must be omitted** (like an absolute concentration with no water reference). The b-value schemes differ per subject, so shells must be read from the data — a hard-coded scheme cannot fit the cohort.
2. **Coupled-physics assembly** — shell grouping, the **arithmetic** powder average per shell, the `b=0` normalisation, the log-linear design `[1, −b, b²/6]` with `b` in ms/µm² (`= bval/1000`), and the `MSK = (quadratic coeff)/MSD²` unpacking must **all** be assembled correctly; an error in any one compounds.
3. **Hidden robustness** — a majority of subjects (6 of 8) carry one or two grossly corrupted diffusion volumes (dropout or spike) that bias the per-shell powder mean and must be **rejected** before averaging; this is never announced in `instruction.md`, so a competent pipeline that gets every stated step right but never inspects the volumes fails the majority of the cohort.
4. **Convention-invariant grading** — the powder (direction) average makes MSD and MSK rotation-invariant by construction, and with `b=0` plus two shells the three-point fit is exactly determined, so MSD and MSK are implementation-independent physical quantities; two independent correct implementations agree to ~5e-8 (proven below).

### Verifier

`tests/test_outputs.py` recomputes every map from the bundled per-volume signals with a **held-out reference** pipeline (`msdki_pipeline` + `msdki_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **voxelwise** over the brain mask, one parametrized test per (subject × map). There are **16 panels** (8 subjects × {MSD, MSK}). A computable map passes when ≥90% of brain voxels agree within a per-map tolerance (MSD rtol 6%/atol 0.02; MSK rtol 12%/atol 0.06); an unsupported map (MSK for a single-non-zero-shell subject) passes only when the submission **omits** it. Reward is binary (1 only if every panel passes).

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (b grouped by a different rounding, a **different** batch sigma-clip volume rejection, a normalise-first fit with no intercept via `scipy` least squares; **no** shared code) reproduces MSD and MSK to a max relative error of ~5e-8 over all graded voxels — so the tolerances reflect method-invariance rather than absorbing method spread. The plausible-but-wrong pipelines each miss on their own axis: **forcing MSK** on single-shell subjects fails only the omit panels; **skipping volume rejection** fails only the corrupted subjects; the per-direction fit and the geometric-vs-arithmetic mean probe the shared powder-average physics. A naive uniform pipeline (fit MSD+MSK for everyone, no rejection) fails 12 of 16 panels across 7 of 8 subjects.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **7/16 panels**: correct on the well-conditioned multi-shell, clean-volume MSD/MSK fits, but failed the hard axes — the unannounced corrupted-volume rejection on the 6 motion-affected subjects and the MSK omit rule on the single-non-zero-shell subjects. A clean multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean MSDKI fit and applies it uniformly — it handles the standard multi-shell subjects but does not discover-and-reject the unannounced corrupted volumes before the powder average, nor omit MSK where a single shell cannot determine it. Its underlying quadratic fit is otherwise correct (the standard panels pass), so the 0.0 is earned on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (assemble a coupled per-voxel inversion with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the powder-average/estimator conventions but never enumerates the pitfalls (the corrupted volumes, the single-shell omit fork) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`; `fixture_spec.json` is build-provenance only). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
