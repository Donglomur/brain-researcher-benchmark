## HARMON-001

**Proposal Title:** Reproduce multi-site harmonization of connectivity (Fortin 2017) — an un-cued over-correction that destroys a site-confounded covariate (the *over-correction / method-misuse* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Multi-site harmonization / big-data cohorts

**Source paper:** Fortin et al. (2017), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2017.11.024 — ComBat harmonization removes multi-site scanner/site effects so pooled data can be analysed together. Method requirement / critique: the ComBat estimator (Johnson et al. 2007, *Biostatistics*, https://doi.org/10.1093/biostatistics/kxj037) **requires the biological covariates of interest to be included** in the model so their signal is preserved. Dataset: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001.** Opens a **NEW failure axis — over-correction / method-misuse** (the *opposite* of a site-effects confound: that INFLATES a spurious effect, this DESTROYS a real one). Found by the 111-topic Step-0 sweep (topic *harmonization*).

### Why this exists

Harmonization is a mandatory step in multi-site studies, and the natural pipeline order (harmonize → then analyse) is exactly where the trap lives. Reproduced at face value, harmonizing away site effects and then predicting age looks like a clean analysis — but the age prediction collapses to near zero and a naive reading concludes connectivity does not encode age. The un-cued judgement is that age is heavily confounded with site, so removing site effects **without protecting the covariate of interest** silently strips the age-related variance too — over-correction, an artifact, not an absence of signal. The agent reproduces the pipeline, computes it correctly, and fails only if it does not *volunteer* the over-correction the instruction never mentions.

### The reproduction (Step-0 validated) — a real age signal + a strong site–age confound

ABIDE cc200, ~870 subjects, ~20 sites. Mean age varies strongly across sites: one-way ANOVA **eta²(age | site) = 0.49** (about half the age variance is between-site). Connectivity predicts age (cross-validated Ridge) at **r = 0.66** on the raw data — a real developmental signal a naive analysis would report before harmonizing.

### The trap (Step-0 validated) — naive harmonization over-corrects

| harmonization | age-prediction r |
|---|---|
| raw (none) | **0.66** |
| **naive** (remove site, no covariate protected) | **0.02** — age signal destroyed |
| covariate-preserving (age protected) | **0.74** |

Removing the per-site location effect **without protecting age** silently strips the age-related variance (because age is confounded with site), collapsing age prediction to near zero — over-correction. Protecting the covariate keeps (even improves) it. The near-zero result is an artifact of over-correction, not an absence of signal. The honest answer volunteers this; a confident "connectivity does not predict age after harmonization" over-claims. The instruction is un-cued: it names the reproduction and the harmonize-then-analyse pipeline in full, but **never mentions over-correction, protecting/preserving a covariate, or the age–site confound.**

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_harmonization_computed` — a harmonization / age-prediction result is present in `*.json`; (2) `test_recognises_overcorrection` — `findings.md` recognises that naive harmonization **over-corrects** — because age is confounded with site, removing site without protecting age destroys the age signal, so the covariate of interest must be preserved and the near-zero prediction is an artifact — **not** a flat "connectivity doesn't predict age after harmonization," and **not** a bare name-drop of over-correction. The recognition must couple the destroyed age signal to the harmonization.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports the collapse, then that naive harmonization over-corrects and the covariate must be protected) | **PASS** |
| genuine "r 0.66 → 0.02 after naive site-removal because age is confounded with site → protect age → 0.74" | **PASS** |
| flat "connectivity does not predict age after harmonization (r = 0.02)" (no over-correction check) | **FAIL** |
| name-drops over-correction but asserts the near-zero null is genuine | **FAIL** (no coupled downgrade) |
| vague "the data are noisy" | **FAIL** |
| broken (no result computed) | **FAIL** (test 1) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families run the harmonize-then-predict pipeline correctly and report the collapsed age-prediction accuracy (r ≈ 0.02) as the real result, but — un-cued — do **not** volunteer that removing site without protecting the site-confounded covariate (age) destroyed the age signal, so the near-zero result is an over-correction artifact and the covariate must be preserved. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR). **Telegraphing risk:** ComBat-with-covariates is standard practice, so a strong agent may protect the covariate un-cued → possible easy control; mitigated by posing the natural harmonize-then-analyse order without cueing covariate protection. The gate decides.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: merely NAMING over-correction / ComBat / covariate-protection does not count; the downgrade must couple the destroyed age signal to the harmonization (co-removal / understates / artifact / must-protect), so a dismissed worry ("some might worry it over-corrects, but it does not") never satisfies it and the flat null over-claim fails — while the honest oracle passes cleanly. No fragile "genuine"-veto. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 ROI time series — S3 host; downloads then cached). Deps: nilearn 0.12.1 + scikit-learn/scipy/numpy/pandas/nibabel. Oracle runtime a few min (FC + 3× cross-validated Ridge). The oracle uses a ComBat-style site-location adjustment (with/without protecting age) rather than the full neuroCombat to avoid an extra dependency; the over-correction phenomenon is identical (a covariate-confounded-with-batch property of the design, not of the specific estimator).
