## HARMON-001

**Proposal Title:** Multi-site harmonization over-correction — un-cued destruction of a site-confounded covariate (the *over-correction / method-misuse* failure axis — NEW)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Multi-site harmonization / big-data cohorts

**Source finding:** Fortin et al. (2017/2018), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2017.11.024 — ComBat harmonization removes multi-site scanner effects; the method (Johnson et al. 2007) **requires the biological covariates of interest to be included** so their signal is preserved. Data: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200).

**Status: FULL runnable task, built with `tb-science-task-authoring`.** Opens a **NEW failure axis — over-correction / method-misuse** (the *opposite* of the dropped "site effects" confound: that INFLATES a spurious effect, this DESTROYS a real one). Found by the 111-topic Step-0 sweep (topic *harmonization*).

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists
Harmonization is a mandatory step in multi-site studies, and the natural pipeline order (harmonize → then analyse) is exactly where the trap lives: if you remove site effects without protecting the covariate you will later study, and that covariate is confounded with site, you remove the biology too. The un-cued judgement is to protect the covariate of interest in the harmonization.

### The reproduction (Step-0 validated) — a real developmental age signal + a strong site–age confound
ABIDE cc200, ~870 subjects, ~20 sites. Mean age varies strongly across sites: one-way ANOVA **eta²(age | site) = 0.49** (half the age variance is between-site). Connectivity predicts age (cross-validated Ridge): **r = 0.66** raw.

### The trap (Step-0 validated) — naive harmonization over-corrects
| harmonization | age-prediction r |
|---|---|
| raw (none) | **0.66** |
| **naive** (remove site, no covariate protected) | **0.02** — age signal destroyed |
| covariate-preserving (age protected) | **0.74** |

Removing the per-site location effect **without protecting age** silently strips the age-related variance (because age is confounded with site), collapsing age prediction to near zero — over-correction. Protecting the covariate keeps (even improves) it. The near-zero result is an artifact of over-correction, not an absence of signal.

### Verifier (2 plain checks)
`tests/test_outputs.py`: (1) a harmonization / age-prediction result was computed; (2) `findings.md` recognises that naive harmonization **over-corrects** — the covariate of interest (age) must be preserved, and the collapsed prediction is an artifact — a flat "connectivity doesn't predict age after harmonization" over-claims. Strong-token guard: the recognition must name over-correction / covariate-protection / site-confound, linked to the destroyed signal. Offline: oracle PASS; flat "no age signal after harmonization" adversarial FAIL; vague "noisy" adversarial FAIL.

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. **Telegraphing:** ComBat-with-covariates is standard practice; a strong agent may protect the covariate un-cued → possible easy control. Mitigated by the instruction posing the natural harmonize-then-analyse order without cueing covariate protection.
2. **ComBat-style location adjustment** — the oracle uses a site-location adjustment (with/without protecting age) rather than the full neuroCombat (to avoid an extra dependency); the over-correction phenomenon is identical (the covariate-confounded-with-batch problem is a property of the design, not the specific estimator).
3. **Data robustness** — the oracle reads the cached cc200 time series directly after a best-effort fetch, so a single flaky ABIDE mirror file does not break it.

### Cost
`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 ROI time series — S3 host). Deps: nilearn 0.12.1 + scikit-learn/scipy/numpy/pandas/nibabel. Oracle runtime a few min (FC + 3× cross-validated Ridge).
