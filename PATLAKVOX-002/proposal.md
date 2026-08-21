## PATLAKVOX-002

**Proposal Title:** Voxelwise Patlak parametric imaging of a dynamic brain-PET cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Molecular imaging / PET kinetic modeling

**Source paper:** Patlak, Blasberg & Fenstermacher 1983, *JCBFM* (graphical net-influx analysis, https://doi.org/10.1038/jcbfm.1983.1); Logan et al. 1996, *JCBFM* (reference-tissue graphical analysis); Ichise et al. 2002, *JCBFM* (multilinear analysis MA1). Dataset: a **synthetic** dynamic brain-PET cohort (per-voxel TACs, arterial or reference input, mixed isotopes), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the per-voxel parametric map(s) the acquisition supports); the difficulty is *execution*. The agent implements voxelwise Patlak / reference-Patlak / reversible-VT analysis **from scratch** (no fitter is bundled), over a **heterogeneous cohort where subjects and even individual voxels need structurally different computations**, with a dominant **hidden robustness** requirement, graded voxelwise against a **held-out reference**.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects and voxels need *different code paths*, discoverable only from the data. The **input fork:** five subjects provide a metabolite-corrected arterial input (plasma net-influx Ki, mL/min/mL); three provide only a reference region and no arterial input, so a plasma Patlak is uncomputable and the reference-Patlak Ki_ref (1/min), on a *different* x-axis, is the only route — the two families report **different quantities in different files with different units**. The per-voxel **reversibility fork:** inside every plasma subject each voxel is either irreversibly trapping (linear Patlak → report Ki) or reversible (Ki undefined → **omit as NaN**, report VT instead), and which one is unlabeled — ~half of every plasma map is a per-voxel model-selection decision.
2. **Coupled-physics assembly** — isotope-specific per-frame decay-correction to injection time (¹¹C t½=20.4 min vs ¹⁸F t½=109.8 min), the metabolite-corrected parent plasma (whole-blood × plasma/blood ratio × parent fraction, decay-corrected like the tissue), the reference-region mean, cumulative-trapezoid integration for the graphical linearizations, and the per-subject pinned t* window must **all** be correct; an error in any one compounds.
3. **Hidden robustness (dominant trap)** — a *majority* of subjects (six of eight) carry two-to-three grossly **motion-corrupted frames** clustered in the **late, highest-leverage** part of the graphical window, where decay-correction amplifies them most for the short-half-life ¹¹C subjects. The outliers are deliberately **asymmetric** in sign/magnitude, so a one-pass detector that repairs only the single most obvious frame leaves biasing outliers — the *full* set must be found by an iterate-until-clean detector before any integral or fit. Two clean anchor subjects force the axis to be discovered from the data, and a blind "always drop the highest-leverage frame" hack corrupts them. Never announced in `instruction.md`.
4. **Convention-invariant grading** — the graded quantities are convention- and estimator-invariant: a fully-independent from-scratch implementation (nonlinear 2-tissue-compartment Ki/VT with reversibility from fitted k4, multilinear reference-Patlak, a different motion detector) reproduces every panel, so a correct solver of any estimator family passes while wrong pipelines fail.

### Verifier

`tests/` recomputes every map **voxelwise** from the bundled TACs with a **held-out reference** pipeline (`patlak_pipeline` + `patlak_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`), graded per (subject, map). The verifier defines 24 (subject × map) panels (8 subjects × {ki, vt, kiref}); a computable map passes when ≥90% of brain voxels are correct, where a voxel is correct iff the reference is finite and the submission agrees within a per-map tolerance (Ki rtol 10%/atol 0.006; VT rtol 16%/atol 0.5; Ki_ref rtol 17%/atol 0.004), **or** the reference is NaN and the submission is NaN too (the submission must both estimate the quantity *and* withhold it where it does not apply). An unsupported map passes only when the file is omitted. Reward is **binary** (test.sh: pytest rc==0 → 1 else 0).

**Grading-invariance proof (the key check).** The genuinely-independent implementation reproduces every panel (24/24), with per-voxel relative differences median/max of Ki 1.3%/5.6%, VT 0.15%/13.0%, Ki_ref 1.5%/14.3%, and per-voxel reversible/omit routing agreeing on 99.65% of voxels (plasma Logan-VT and MA1-VT agree to <1%). The plausible-but-wrong pipelines each fail on their own axis (panels failed / 24): **ignore the input fork** 6, **skip reversibility routing** 10, **skip motion detect+repair** 10, **skip decay-correction** 13; a naive uniform pipeline fails 16/24. Crucially, a *competent one-pass* pipeline that gets the forks, decay and reversibility right but repairs only the single most obvious motion frame still fails 10/24, and a two-drop detector still fails 4/24 — only an iterate-until-clean repair passes all 24. Partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **23/25 gate panels** but not the full set — failed the hard axes: the plasma-vs-reference input fork (different quantities/files/units), the per-voxel reversible-vs-trapping model-selection routing (NaN where the other applies), isotope-specific decay correction, and above all the iterate-until-clean multi-outlier motion-frame repair in the late high-leverage window. |
| **2nd frontier family (Claude/Gemini)** | _k≥1_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model gets most panels close but is defeated by the dominant hidden axis — the asymmetric, late-clustered multi-outlier corruption biases the graphical slope past tolerance unless the *complete* outlier set is repaired, and a one-pass detector leaves it wrong. With reward binary, the two remaining panels sink the run despite broad partial progress, so the 0.0 is earned on the genuine hard axes, not a format bug.

*(Note: the verifier defines 24 subject×map panels; the frontier gate enumerated 25 test items for this task, of which 23 passed — reported here as measured.)*

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional, unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the physics conventions but never enumerates the pitfalls (the input fork, the per-voxel reversibility routing, the multi-outlier motion frames) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
