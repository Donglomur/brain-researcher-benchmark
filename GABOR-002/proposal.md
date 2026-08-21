## GABOR-002

**Proposal Title:** Voxel-wise visual-encoding (Gabor receptive-field) model of a stimulus-response cohort — an execution-hard reconstruction task (recipe divergence + coupled-physics assembly + hidden robustness)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Computational visual neuroscience / voxel encoding models

**Source paper:** Kay et al. 2008, *Nature* (identifying natural images from human brain activity / Gabor-wavelet voxel encoding, https://doi.org/10.1038/nature06713); Naselaris et al. 2011, *NeuroImage* (encoding and decoding in fMRI). Dataset: a **synthetic** visual-encoding cohort (precomputed Gabor-pyramid features + per-voxel training responses, held-out test stimuli), generated deterministically at `synth_build/generate_fixtures.py`; planted ground-truth held out under `synth_build/fixture_spec.json`.

**Status: FULL runnable Harbor task.** This is a **reconstruction** task, *not* a recognition / "spot-the-confound" task — the instruction names the deliverable (fit each voxel's receptive field and predict held-out test responses) and the difficulty is *execution*, not an un-cued judgement. It follows the shape of the maintainer's `pcasl-cbf-quantifier`: the agent implements the encoding-model pipeline **from scratch** (no fitter bundled), over a **heterogeneous cohort where subjects need fundamentally different computations**, with a **hidden robustness** requirement, graded against a **held-out reference** on a **convention-invariant** (correlation-scored) prediction.

### Why this is hard (the four difficulty drivers)

1. **Recipe divergence** — subjects ship the training responses in *two different representations*, discoverable only from each sidecar: some provide per-stimulus response amplitudes (`resp_train`, ready to regress) while others provide a raw detrended BOLD time-course (`ts_train`) plus stimulus-onset TRs and **no** amplitudes — those must first be recovered by least-squares **HRF deconvolution** against the canonical HRF before any receptive field can be fit. A pipeline that assumes one representation cannot process the other.
2. **Coupled-physics assembly** — the fit is a per-voxel L2-regularised (ridge) regression with the regularisation chosen from the data; on the time-course subjects the deconvolution feeds the regression, and the **direction** of the receptive field (not any absolute scale) is what must generalise to held-out stimuli. An error in the deconvolution, the ridge path, or the reliability score compounds.
3. **Hidden robustness** — a **majority of subjects** carry a few grossly corrupted training samples (motion spikes) that bias an ordinary least-squares fit and must be rejected before fitting — including on the time-course subjects, where the spike must be caught in the *deconvolved* amplitudes, so the deconvolution and the robust rejection are coupled. Additionally, within every subject a substantial fraction of voxels carry no stimulus tuning (pure noise); their receptive field is un-fittable and must be **excluded as NaN columns** rather than predicted, judged per-voxel from cross-validated predictive reliability. None of this is announced.
4. **Convention-invariant grading** — predictions are scored by *correlation* across the test stimuli, so any global gain, offset, or regularisation strength cancels — only the receptive-field direction is graded; the fittable set is separated by a wide bimodal gap (signal voxels ~0.66–0.93 CV correlation, noise voxels ~0), so an independently-implemented reliability criterion recovers the same set. Two independent correct implementations agree (proven below) — no reporting-convention ambiguity.

### Verifier

`tests/test_outputs.py` recomputes the predicted test responses and the fittable-voxel set from the bundled features + responses with a **held-out reference** pipeline (`gabor_pipeline` + `gabor_ref`, shipped only under `tests/` + `solution/`, never under `/app/data`) and grades each subject on **two panels** — **16 panels** in all (8 subjects × {pred, omit}): a `pred` panel (≥90% of the reference-fittable voxels must have a finite predicted column correlating ≥0.90, across the test stimuli, with the reference) and an `omit` panel (the keep/exclude decision must match the reference's fittable mask on ≥90% of voxels). Reward is fractional over the 16 panels.

**Grading-invariance proof (the key check).** A fully independent implementation (SVD/GCV ridge with a continuous lambda path, a single random-split fittable score at a different threshold, explicit-intercept HRF deconvolution, median-based corrupt-row rejection; **no** import of the reference) reproduces every panel (16/16, worst per-voxel prediction correlation 0.97, worst fittable-set agreement 0.97). Wrong pipelines each fail only their own axis: **assume one response representation for all** → 1/16; **never exclude un-fittable voxels** → 8/16; **skip the HRF deconvolution** → 10/16; **keep grossly corrupted samples** → 7/16 — so partial credit is monotone in correctness.

### Difficulty — measured on the frontier gate

Oracle **reward 1.0**, in-container (deterministic; oracle == verifier).

| agent | runs | reward | what it did |
|---|---|---|---|
| **gpt-5.6-sol (codex, xhigh)** | **k=1** | **0.0** | Solved **9/16 panels**. The 7 failing panels concentrate on the task's designed hard axes: the betas-vs-timeseries HRF-deconvolution fork, the un-fittable-voxel **omit** (NaN-column) decision, and the unannounced corrupted-sample rejection on the affected subjects. A reproducible multi-axis execution failure. |
| **2nd frontier family (Claude/Gemini)** | _k≥3_ | _pending_ | _to be run by the maintainer at gate calibration_ |

**Failure mode (measured for gpt-5.6-sol; hypothesis for the 2nd family):** the model implements a single clean encoding pipeline and applies it near-uniformly — it fits the betas subjects and predicts their test responses but does not thread the HRF deconvolution through the time-course subjects, honour the per-voxel exclusion rule, or reject the unannounced corrupted samples, so the 0.0 is earned on the genuine hard axes rather than a format bug.

### Notes / honesty

- **Reconstruction paradigm.** This task's difficulty is executional (get many coupled quantitative decisions right with no recipe), unlike the recognition-tier "un-cued judgement" tasks in this repo. `instruction.md` names the deliverable and the model conventions but never enumerates the pitfalls (the representation fork, the exclusion rule, the corrupted samples) — the agent must discover them from the data.
- **Data.** Synthetic, small, deterministic, and **leakage-clean** (the held-out reference and planted parameters are never under `/app/data`). Regenerable via `synth_build/generate_fixtures.py`.
- **allow_internet=false.** The task is self-contained (dependencies baked in the image; no network at run or verify time).
