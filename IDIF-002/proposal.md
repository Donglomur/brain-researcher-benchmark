## IDIF-002

**Proposal Title:** Image-derived input function and kinetic outcome for a heterogeneous dynamic-PET cohort — reference-region ratio + blood-calibrated macro-parameter — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** PET kinetic modeling

**Source paper:** Logan et al. 1990, *JCBFM* (graphical analysis of reversible binding, https://doi.org/10.1038/jcbfm.1990.127); Patlak et al. 1983, *JCBFM* (graphical evaluation of blood-to-brain transfer constants, https://doi.org/10.1038/jcbfm.1983.1); Zanotti-Fregonara et al. 2011, *JCBFM* (image-derived input function, https://doi.org/10.1038/jcbfm.2011.107). Dataset: a **synthetic** dynamic-PET IDIF cohort, generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (extract the IDIF and write the per-region ratio map always, and the absolute kinetic macro-parameter where blood samples exist); the difficulty is *execution*, not an un-cued judgement. The agent implements the IDIF-and-kinetic pipeline **from scratch** (no tool bundled), over a **heterogeneous 8-subject cohort where subjects need fundamentally different computations**, with **hidden robustness** requirements, graded per-region against a **held-out reference** on **convention-invariant** quantities.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — two forks are latent in the data. The **tracer class** forks the graphical model: a reversible tracer needs the **Logan** distribution-volume slope, an irreversible tracer the **Patlak** net-influx slope — the wrong one is grossly biased and fails **both** maps. The **calibration state** forks whether the absolute map exists at all: `kinetic.npy` (VT or Ki) is written **only** where arterial blood samples exist and must be **omitted** otherwise (the recovery scale is undetermined) — writing it for a no-blood subject violates the omit rule. `ratio.npy` (DVR for reversible, Krel for irreversible) is always written.
2. **Coupled-physics assembly** — the carotid ROI blood curve must be assembled from candidate voxels, spillover-corrected with the given tissue fraction (`U = A − SP·Ctis`), recovery-calibrated by a closed-form blood-sample match, and fed through the trapezoidal cumulative integrals and the OLS graphical slope at the pinned `t_star` — an error in any one compounds.
3. **Hidden robustness** — two un-cued axes span the cohort: (a) the carotid candidate voxels of the calibrated subjects include **partial-volume/tissue-contaminated voxels** whose attenuated bolus must be excluded before averaging (biases the absolute map); (b) on a **majority** — the five irreversible-tracer exams — one or two carotid **tail frames are grossly motion-corrupted** and must be rejected before the input function is integrated. A tail-frame corruption is smoothed away by a Logan cumulative-integral slope but grossly biases a Patlak slope, so the motion axis punishes a pipeline that skips frame QC on **both** its kinetic and its ratio map — a strong agent that does voxel QC but omits frame QC fails half the panels.
4. **Convention-invariant grading** — the graphical slopes are unique given the pinned `t_star` and integration convention; a from-scratch implementation (different carotid voxel selection by bolus AUC, different corrupted-frame detection by neighbour ratio, `numpy.polyfit` OLS, even framewise rather than trapezoidal integration) reproduces every supported panel to ~5e-8 (proven below), so a correct solver can pass while wrong pipelines fail — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes both maps from the bundled TACs with a **held-out reference** pipeline (`idif_pipeline` + `idif_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades **per region** over the target regions. Reward is **fractional**: each of the **16 (subject × map) panels** is its own test, so the score is the fraction of panels correct. A supported panel passes when ≥90% of regions agree within tolerance (ratio rtol 10%/atol 0.05; kinetic rtol 10% with atol 0.2 for VT / 0.002 for Ki, keyed off the tracer class); the kinetic panel of an uncalibrated subject passes only when the submission **omits** the file.

**Grading-invariance proof (the key check).** A genuinely-correct independent implementation reproduces every supported panel to well within tolerance (max relative error ~5e-8 across all regions). The plausible-but-wrong pipelines each fail only their own axis, so partial credit is monotone in correctness: **skip voxel QC** → contaminated kinetic maps fail; **skip frame QC** → the five irreversible subjects fail on both maps (8/16 panels); **skip both** → a majority fail (10/16); **skip blood calibration** → only the absolute kinetic maps fail; **wrong graphical model** → the corresponding tracer class fails both maps; **compute the absolute map everywhere** → the uncalibrated omit panels fail.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | k=1 | 0.0 | Solved **8/16 panels**; the 8 it missed fall on the hard axes — the un-cued carotid tail-frame motion QC on the five irreversible (Patlak) subjects (failing both their maps), plus the carotid voxel QC and the blood-calibration/omit fork. Full-suite gate reward 0. |
| **2nd frontier family (Claude/Gemini)** | pending | pending | to be run by the maintainer at gate calibration |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model builds one IDIF-and-kinetic pipeline and does not discover-and-reject the unannounced carotid tail-frame corruption before integrating the Patlak input function, so the irreversible subjects are biased on both maps. The specific failing set is characterised from the task's hard axes (per-panel identities were not logged for this k=1 run); the 8-panel miss is the count the gate recorded and lands on the genuine hard axes, not a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (build the IDIF, the right graphical model, the calibration and the QC per subject, no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable but never enumerates the pitfalls (the tracer fork, the blood-calibration omit, the voxel/frame QC) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
