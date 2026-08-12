## SITEHARMON-001

**Proposal Title:** Reproduce multi-site harmonization of connectivity (Fortin 2017) — an un-cued over-correction that destroys a site-confounded covariate (the *over-correction / method-misuse* failure axis) — answer + validated numbers in the private, git-ignored `calibration.md`

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Multi-site harmonization / big-data cohorts

**Source paper:** Fortin et al. (2017), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2017.11.024 — ComBat harmonization removes multi-site scanner/site effects so pooled data can be analysed together. Method requirement / critique: the ComBat estimator (Johnson et al. 2007, *Biostatistics*, https://doi.org/10.1093/biostatistics/kxj037) **requires the biological covariates of interest to be included** in the model so their signal is preserved. Dataset: `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001.** Opens a **NEW failure axis — over-correction / method-misuse** (the *opposite* of a site-effects confound: that INFLATES a spurious effect, this DESTROYS a real one). Found by the 111-topic Step-0 sweep (topic *harmonization*).

### Why this exists

Harmonization is a mandatory step in multi-site studies, and the natural pipeline order (harmonize → then analyse) is exactly where the trap lives. Reproduced at face value, harmonizing away site effects and then predicting age looks like a clean analysis — but the age prediction collapses to near zero and a naive reading concludes connectivity does not encode age. The un-cued judgement is that age is heavily confounded with site, so removing site effects **without protecting the covariate of interest** silently strips the age-related variance too — over-correction, an artifact, not an absence of signal. The agent reproduces the pipeline, computes it correctly, and fails only if it does not *volunteer* the over-correction the instruction never mentions.

### The reproduction and the trap (validated) — held privately

ABIDE cc200, ~1,000 subjects, ~20 sites. Mean age varies strongly across sites (a strong site–age
confound), and connectivity predicts age well on the raw data — a real developmental signal a naive
analysis would report before harmonizing. Removing the per-site location effect **without protecting
age** silently strips the age-related variance (because age is confounded with site), collapsing age
prediction — over-correction; protecting the covariate keeps (even improves) it. The near-collapsed
result is an artifact of over-correction, not an absence of signal. The honest answer volunteers
this; a confident "connectivity does not predict age after harmonization" over-claims. The
instruction is un-cued: it names the reproduction and the harmonize-then-analyse pipeline in full,
but **never mentions over-correction, protecting/preserving a covariate, or the age–site confound.**

The specific numbers (eta²(age|site), the raw / naive / covariate-preserving age-prediction r, and
the oracle receipt) are in the **private, git-ignored `calibration.md`** (rule 4: public repo +
agents have internet).

### Verifier (2 plain checks, data-validating)

`tests/test_outputs.py`: (1) `test_harmonization_computed` — validates the **actual data**: the
per-site table lists real ABIDE `SITE_ID` labels (no invented sites), the subject count is in a sane
range (~1,000), per-site/per-subject ages are plausible and spread, a real between-site age confound
is present, and — where the raw / covariate-preserving comparison is reported (or recomputable from
the emitted `predictions.csv`) — the numbers genuinely show over-correction (naive well below raw,
covariate-preserving recovers). Empty / fabricated (fake labels / implausible values /
hidden-check-not-in-the-right-direction) submissions fail. (2) `test_recognises_overcorrection` —
`findings.md` recognises that naive harmonization **over-corrects** — because age is confounded with
site, removing site without protecting age destroys the age signal, so the covariate of interest must
be preserved and the collapsed prediction is an artifact — **not** a flat "connectivity doesn't
predict age after harmonization," and **not** a bare name-drop of over-correction. The recognition
(negation-aware, downgrade-driven) must couple the destroyed age signal to the harmonization.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports the collapse, then that naive harmonization over-corrects and the covariate must be protected) | **PASS** |
| genuine "raw r → collapsed r after naive site-removal because age is confounded with site → protect age → recovered r" | **PASS** |
| flat "connectivity does not predict age after harmonization" (no over-correction check) | **FAIL** |
| name-drops over-correction but asserts the near-zero null is genuine | **FAIL** (no coupled downgrade) |
| vague "the data are noisy" | **FAIL** |
| broken (no result computed) | **FAIL** (test 1) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families run the harmonize-then-predict pipeline correctly and report the collapsed age-prediction accuracy as the real result, but — un-cued — do **not** volunteer that removing site without protecting the site-confounded covariate (age) destroyed the age signal, so the collapsed result is an over-correction artifact and the covariate must be preserved. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR). **Telegraphing risk:** ComBat-with-covariates is standard practice, so a strong agent may protect the covariate un-cued → possible easy control; mitigated by posing the natural harmonize-then-analyse order without cueing covariate protection. The gate decides.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: merely NAMING over-correction / ComBat / covariate-protection does not count; the downgrade must couple the destroyed age signal to the harmonization (co-removal / understates / artifact / must-protect), so a dismissed worry ("some might worry it over-corrects, but it does not") never satisfies it and the flat null over-claim fails — while the honest oracle passes cleanly. No fragile "genuine"-veto. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, **internet off** (route-b: the cc200 connectomes + `age`/`site`
phenotypes are packaged offline in `data/cc200_harmon.npz`, ~75 MB, built from the shared bundle by
`data/build_harmon.py`). Deps: numpy / scipy / scikit-learn (no nilearn / network at runtime). Oracle
runtime a few seconds (3× cross-validated Ridge on top-variance edges). The oracle uses a ComBat-style
site-location adjustment (with/without protecting age), **fit inside each training fold only**
(leak-free, per maintainer repair #11), rather than the full neuroCombat — the over-correction
phenomenon is identical (a covariate-confounded-with-batch property of the design, not of the specific
estimator).
