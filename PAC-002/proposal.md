## PAC-002

**Proposal Title:** Phase-amplitude cross-frequency coupling in a heterogeneous recording cohort — an execution-hard reconstruction task (recipe divergence + coupled-pipeline assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Electrophysiology / cross-frequency-coupling signal processing

**Source paper:** Tort et al. 2010, *J. Neurophysiol.* (Kullback-Leibler modulation index for phase-amplitude coupling, https://doi.org/10.1152/jn.00106.2010); Canolty & Knight 2010, *Trends Cogn. Sci.* (the functional role of cross-frequency coupling). Dataset: a **synthetic** single-channel electrophysiology cohort (epoched recordings, per-recording sampling rate and bands), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (produce the Tort modulation index, the preferred coupling phase, and the comodulogram) and the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the PAC pipeline **from scratch** (no PAC library bundled), over a **heterogeneous cohort where recordings need fundamentally different computations and omit different outputs**, with a **hidden robustness** requirement, graded against a **held-out reference** on **convention-invariant** quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — recordings need different computations and **omit different outputs**, decided only from each sidecar and the data: the sampling rate and pinned phase/amplitude bands differ per subject; only recordings of sufficient nominal duration (≥ 90 s) support the comodulogram — for the **majority (short) recordings** it is not determinable and must be **omitted**; the preferred coupling phase is reportable only for channels that actually couple (MI ≥ the detection floor) and must be **omitted** for uncoupled channels. A single fixed recipe cannot fit the cohort.
2. **Coupled-pipeline assembly** — the physics is a coupled multi-stage chain — zero-phase FIR band-pass (Hamming-windowed sinc, 3 cycles of the pass-band low edge, odd taps, filtfilt), analytic-signal phase and amplitude, the 18-bin Tort KL modulation index, the circular-mean preferred phase, and the comodulogram grid — and an error in any stage compounds; a non-pinned band-pass or a surrogate-normalised index fails the value panels.
3. **Hidden robustness** — a **majority of recordings** carry a minority of grossly corrupted epochs (sharp, high-amplitude phase-locked transient trains) whose broadband, phase-locked energy manufactures *spurious* coupling; a pipeline that pools every epoch without rejecting these gross outliers reads the artifact as coupling — MI inflated by tens of percent on the coupled channels, the comodulogram wrong across a majority of cells, and on an uncoupled channel a fabricated false-positive that trips the preferred-phase omit rule. Nothing in the instruction announces this.
4. **Convention-invariant grading** — MI, preferred phase, and comodulogram are convention-invariant given the pinned pipeline in `protocol.json`; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every quantity from the bundled epoched signals with a **held-out reference** pipeline (`pac_pipeline` + `pac_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades per (subject × quantity) — **24 panels** in all (8 recordings × {mi, preferred_phase, comodulogram}). `mi` passes when the scalar agrees within (rtol 0.15, atol 0.003); the preferred-phase panel passes within a 0.15 rad circular distance for a coupled channel and passes only on **omission** for an uncoupled one; the comodulogram passes when ≥90% of grid cells agree within (rtol 0.15, atol 0.002) for a long recording and passes only on **omission** for a short one. Reward is binary (all 24 panels must pass).

**Grading-invariance proof (the key check).** A fully independent implementation (different analytic-signal code, different phase binning, a different robust epoch-rejection statistic; **no** import of the reference) reproduces every computable panel to well within tolerance (max relative MI difference well under 1%; preferred phase within ~0.01 rad; the comodulogram agrees on 100% of cells). Wrong pipelines each fail only their own axis: **keep artifact epochs** biases MI/comodulogram/preferred phase on the artifact recordings; **comodulogram for short recordings** fails the short recordings; **preferred phase for uncoupled channels** fails the uncoupled channels; a **non-pinned Butterworth band-pass** or a **surrogate-normalised index** fails the value panels — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **13/24 panels**. The 11 failing panels concentrate on the task's designed hard axes: the unannounced artifact-epoch rejection that spans a majority of recordings (MI / comodulogram / preferred phase), the short-recording comodulogram **omit** rule, and the uncoupled-channel preferred-phase **omit** rule. A reproducible multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a clean Tort-MI pipeline and applies it near-uniformly — it computes the single-band MI on the clean recordings but does not discover-and-reject the unannounced corrupted epochs, honour the short-recording comodulogram omit, or omit the preferred phase on uncoupled channels, so the 0.0 is earned on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get many coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the analysis conventions but never enumerates the pitfalls (the corrupted epochs, the two omit rules) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted ground truth are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
