## CEUS-002

**Proposal Title:** Contrast-enhanced ultrasound (CEUS) microbubble perfusion quantification — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Contrast-enhanced ultrasound / perfusion quantification

**Source paper:** Wei et al. 1998, *Circulation* (destruction–replenishment microbubble perfusion, https://doi.org/10.1161/01.CIR.97.5.473); Strouthos et al. 2010, *IEEE TUFFC* (indicator-dilution / log-normal TIC models, https://doi.org/10.1109/TUFFC.2010.1554); Dietrich et al. 2012, *Ultraschall Med.* (EFSUMB DCE-US quantification). Dataset: a **synthetic** CEUS perfusion cohort (8 exams), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth quantities held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — `instruction.md` names the deliverable (per-region perfusion quantities from each microbubble time-intensity curve); the difficulty is *execution*, not an un-cued judgement. The agent implements the perfusion quantification **from scratch** (no fitter is bundled), over a **heterogeneous cohort where exams need fundamentally different computations**, with a **hidden robustness** requirement, graded per-quantity against a **held-out reference** on **convention-invariant** physical quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — exams need *different code paths*, discoverable only from each sidecar: a **bolus** study needs a log-normal TIC fit (PE, WiR, TTP, AUC) while a **destruction–replenishment** study needs a post-flash mono-exponential fit (β, plateau A, perfusion index) — and each must **omit** the other model's quantities (a bolus quantity on a replenishment exam, or vice-versa, is not determinable). Some exams store **linear** acoustic intensity and others **log-compressed dB** samples that must be linearised (`I = 10**(v/10)`) before any baseline, fit, or integral; frame rate differs per exam (`t = frame/fps`); a replenishment fit runs only from the sidecar's flash frame. A single fixed recipe cannot fit the cohort.
2. **Coupled-physics assembly** — the dB→linear scaling, the model-free artefact rejection, the nonlinear log-normal / mono-exponential fits, and the derived quantities (max enhancement, max derivative, time-to-peak, integral) must **all** be assembled correctly; an error in any one compounds across the (exam × region × quantity) panels.
3. **Hidden robustness** — a **majority** of regions carry grossly corrupted frames (transient motion bursts and acoustic-shadow dropouts) that must be detected and rejected (a centred Hampel filter) before the fit, or a non-robust fit is dragged off the true curve. This is never announced in `instruction.md`.
4. **Convention-invariant grading** — with the rising edge sampled and the gross outliers removed, the nonlinear optimum is sharp, so PE, WiR, TTP, AUC, β, A, PI are uniquely determined; two independent correct implementations compute them identically (proven below), so a from-scratch solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes every quantity from the bundled TICs with a **held-out reference** pipeline (`ceus_pipeline` + `ceus_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **per (exam × region × quantity)**. A supported quantity passes when the submitted value agrees within a per-quantity tolerance (PE rtol 10%, WiR 12%, TTP 6%, AUC 10%, β 10%, A 10%, PI 12%); an unsupported quantity (a bolus quantity on a replenishment exam, or vice-versa) passes only when the submission **omits** it. Harbor reward is binary (pytest rc==0 → 1 else 0).

**Grading-invariance proof (the key check).** A fully independent from-scratch implementation — a derivative-free Nelder–Mead simplex instead of the reference's trust-region least-squares, a different Hampel window and FWHM-based initialisation, Simpson-rule AUC, and **no** import of the reference — reproduces every supported panel to within ~1e-4, orders of magnitude inside the tolerances. The plausible-but-wrong pipelines each fail only their own axis: **assume one model for all** fails the exams of the other type; **skip log→linear** fails the dB exams; **no artefact rejection** fails the artefact-carrying regions; **compute every quantity everywhere** fails the omit rule.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **166/168 panels** — got model-selection, dB linearisation, and the omit rule right, but the 2 residual failures land on the task's hardest driver (the un-announced corrupted-frame robustness), and the binary Harbor reward zeroes on any failed panel. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements clean per-model fits and threads the omit forks correctly (166/168), but does not fully discover-and-reject the unannounced corrupted frames on every region, so a small residual set of robustness panels fails — enough to earn 0.0 under binary reward. The near-miss confirms the failure is on the genuine hard axis, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get the model selection, dB handling, robust fits, and omit forks right with no bundled fitter), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the pinned model definitions but never enumerates the pitfalls (the dB exams, the corrupted frames, the omit forks) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
