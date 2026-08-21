## PETSPECTRAL-002

**Proposal Title:** Spectral analysis of a heterogeneous dynamic-PET cohort (plasma- and reference-input variants) — an execution-hard reconstruction task (input-model recipe divergence + coupled NNLS assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** PET kinetic modeling

**Source paper:** Cunningham & Jones 1993, *J. Cereb. Blood Flow Metab.* (spectral analysis of dynamic PET, https://doi.org/10.1038/jcbfm.1993.9); Gunn et al. 2002, *J. Cereb. Blood Flow Metab.* (reference-tissue / rank-shaping spectral variants). Dataset: a **synthetic** dynamic-PET cohort of a reversible tracer, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth macro-parameters held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (fit the non-negative kinetic spectrum and report the per-region macro-parameters); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's reconstruction tasks (e.g. `pcasl-cbf-quantifier`): the agent implements spectral analysis **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded per-region against a **held-out reference** on **convention- and method-invariant** quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects need *different code paths*, discoverable from each sidecar's `input_type`. Subjects with an arterial **plasma** input do plasma spectral analysis (a non-negative sum of plasma-convolved exponentials by weighted NNLS) and report VT = Σⱼ αⱼ/βⱼ and K1 = Σⱼ αⱼ; subjects with only a **reference-region** TAC require the reference-input variant — an extra direct R1·Cref term, giving DVR = R1 + Σⱼ αⱼ/βⱼ and R1 — and **must omit** absolute VT/K1 (unidentifiable without an arterial input, like a water-reference-absent absolute concentration).
2. **Coupled-physics assembly** — the piecewise-linear input-function convolution must be frame-averaged on the pinned fine grid, the pinned log-spaced β basis and duration weighting applied, non-negativity enforced, and the reference variant's direct term threaded through **both** DVR and R1; an error in any one corrupts the whole spectrum.
3. **Hidden robustness** — a **majority** of subjects (six of eight) carry **one of two independent, un-announced** acquisition artifacts. (a) Reference-input subjects carry grossly motion-corrupted **frames** (a whole-image scale jump that also corrupts the reference input, which doubles as the model regressor) — detect coherent cross-region log-TAC jumps, repair the reference input, and drop the frames, or R1 (and sometimes DVR) is biased. (b) Plasma-input subjects carry a grossly corrupted **arterial sample** (a contaminated/mis-timed blood draw spikes one node of the shared input curve) — detect it as a gross log-outlier of the smooth washout and drop it, or VT and K1 are biased for every region. The two artifacts live in different modalities (tissue frames vs the arterial-input file), so an agent must independently anticipate **both**. Because VT and DVR are total-distribution-volume integrals that are robust by construction, this axis bites the fragile fast/point-value panels (9/32 here) rather than a strict majority.
4. **Convention/method-invariant grading** — an independent Logan-graphical VT (on the cleaned input) and an SRTM-basis DVR both reproduce the spectral recompute within tolerance (proven below), so a from-scratch solver can pass while wrong pipelines fail.

### Verifier

`tests/test_outputs.py` recomputes every quantity from the bundled TACs with a **held-out reference** pipeline (`spectral_pipeline` + `spectral_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **per-region** over 32 parametrized (subject × quantity) panels (8 × {VT, K1, DVR, R1}), each its own test. A computable quantity passes when ≥80% of the subject's regions agree within a per-quantity tolerance (VT rtol 10%/atol 0.06; K1 rtol 12%/atol 0.01; DVR rtol 10%/atol 0.06; R1 rtol 12%/atol 0.05); an unsupported quantity (VT/K1 for a reference subject, DVR/R1 for a plasma subject) passes only when the submission **omits** it. Reward is binary (pytest rc → 1.0 iff every panel passes).

**Grading-invariance proof (the key check).** A fully independent implementation (different β-basis convolution — piecewise-constant on a finer grid — a different BVLS solver, a different frame integration, a different Hampel/MAD arterial-outlier and motion detection/repair; **no** import of the reference) reproduces every computable panel within tolerance; Logan-graphical VT and SRTM-basis DVR likewise agree. The plausible-but-wrong pipelines each fail only their axis: the naive uniform pipeline (plasma analysis for all) fails 24/32; a fork-correct but non-robust pipeline fails 9/32 (the fragile plasma VT/K1 on blood-corrupted subjects + reference R1/DVR on motion subjects); computing all four quantities fails the 16 omit panels — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **24/32 panels**, failing the plasma-vs-reference input-model fork, the coupled NNLS spectral fit + reference direct term, and the two independent unannounced artifact axes (corrupted frames for reference subjects; corrupted arterial samples for plasma subjects) the task is built around. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a clean spectral pipeline and largely handles the omit forks and the robust integral macro-parameters — but misses the fragile fast/point-value panels gated on the two unannounced hidden-robustness artifacts (repair-and-drop corrupted reference frames; detect-and-drop the corrupted arterial sample). The eight failed panels are the ones gated on those hard axes; the k=1 gate reports the count (24/32), and a per-panel itemization will come from the maintainer's calibration run.

### Notes / honesty

- **Reconstruction paradigm.** The difficulty is executional (assemble a coupled NNLS spectral fit and get the per-subject decisions right with no fitter), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the models but never enumerates the pitfalls (the input-model fork, the two independent artifacts) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
