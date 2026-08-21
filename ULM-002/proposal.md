## ULM-002

**Proposal Title:** Super-resolution reconstruction of an ultrasound-localization-microscopy cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Ultrasound localization microscopy

**Source paper:** Errico et al. 2015, *Nature*, "Ultrafast ultrasound localization microscopy for deep super-resolution vascular imaging" (https://doi.org/10.1038/nature16066); Christensen-Jeffries et al. 2020, *Ultrasound Med. Biol.* (super-resolution ultrasound imaging review). Dataset: a **synthetic** contrast-enhanced ULM cohort of beamformed microbubble frame stacks, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth density/velocity held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (reconstruct the super-resolved vessel-density map and, where the acquisition allows, the blood-speed map, and write them out); the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the localisation, accumulation and tracking **from scratch** (no toolbox bundled), over a **heterogeneous 8-acquisition cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded binwise against a **held-out reference** on a **convention-invariant** physical quantity.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — the central divergence is an **omit fork** on a **majority** of the cohort, discoverable only from the frames + sidecar: in the trackable acquisitions the microbubbles persist across many frames and drift slowly, so they link into tracks and a per-bin blood-**speed** map (mm/s) is determinable; in the other five the bubbles have **no reliable temporal correspondence** between frames (fast/independent appearances), tracking is ambiguous, and the velocity map is **not determinable and must be omitted** (like R2* from a single echo) — the vessel-**density** map is still recoverable for both. A uniform pipeline that always tracks and always emits a velocity map fails every must-omit panel.
2. **Coupled-physics assembly** — the physics is coupled and executional: each frame must be searched for microbubbles, sub-pixel-localised, accumulated onto a pinned super-resolution grid for density, and linked into tracks whose inter-frame displacement is converted to mm/s with **each subject's own** pixel size and frame rate (hard-coding one frame rate mis-scales the trackable subjects whose rate differs).
3. **Hidden robustness** — a robustness requirement spans a **majority** of the cohort and is **never announced**: most acquisitions are polluted by two artifact populations — dim noise-floor false detections (must be rejected by amplitude) and defocused **out-of-plane** bubbles imaged with a much wider PSF (must be rejected by spot width / shape) — which, left in, inflate the background density and blur it along the vessels.
4. **Convention-invariant grading** — the graded quantities are convention-invariant by construction of the data (bright vs dim amplitude gap; narrow vs wide shape gap; persistent vs single-appearance tracks), so two independent correct implementations compute them identically (proven below); a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes both maps from the bundled frames with a **held-out reference** pipeline (`ulm_pipeline` + `ulm_ref`, shipped only under `tests/`+`solution/`, never under `/app/data`) and grades **binwise** on the pinned grid, one parametrized test per (subject × map) panel. Density passes when ≥90% of grid bins agree within (rtol 0.15, atol 2 counts); velocity, for a trackable subject, passes when ≥90% of the reference-defined bins agree within (rtol 0.15, atol 1.2 mm/s); an unsupported velocity map passes only when the submission **omits** it (writes no `velocity.npy`). Reward is fractional across the 16 panels.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation (global vs local background, weighted-centroid vs log-parabolic sub-pixel localisation, radius-2 ring vs radius-1 sharpness shape gate, mutual vs greedy nearest-neighbour tracking, different track-length and yield thresholds — no import of the reference) reproduces every panel to 97–100% agreement. The plausible-but-wrong pipelines each fail only their own axis: **keep the false spots** or **keep the out-of-plane bubbles** fails density on the artifact subjects; **always emit velocity** fails the omit panels; a **hard-coded frame rate** fails velocity on the off-rate trackable subjects — so a fully-naive uniform pipeline fails 11 of 16 panels.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **15/16 panels**, failing on the hard axis: one panel where it did not correctly reject an artifact population (dim false detections / out-of-plane wide-PSF bubbles) or mis-scaled velocity / mis-applied the tracking omit fork. A near-miss but a genuine execution failure — the binary structure means one wrong axis still costs the panel. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a clean ULM pipeline that handles most of the cohort but does not fully thread the unannounced artifact rejection and/or the trackability omit fork across every acquisition. The residual 0.0 is earned on a genuine hard axis, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the localisation geometry, units, per-subject frame-rate scaling, and artifact rejection right with no bundled toolbox), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the frame/omit conventions but never enumerates the pitfalls (the two artifact populations, the per-subject frame rate, the velocity omit fork) — the agent must discover them from the data. Note this task's frontier gate was the closest to solved of the batch (15/16), so its final difficulty calibration is the most sensitive to the 2nd-family run.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`; verified by grep). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
