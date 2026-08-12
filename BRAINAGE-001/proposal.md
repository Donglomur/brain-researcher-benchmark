## BRAINAGE-001

**Proposal Title:** The brain-age gap biomarker (OASIS VBM) — an un-cued regression-to-the-mean / age-bias confound (wrong-cause / confounded-metric axis) (answer + numbers in private calibration.md)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Brain-age / imaging biomarkers

**Source paper:** Franke et al. (2010), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2010.01.005 ("BrainAGE" — predict age from structural MRI; the predicted−chronological "brain-age gap" is a biomarker of accelerated/decelerated ageing). Un-cued check / bias correction: de Lange & Cole (2020), *NeuroImage: Clinical*, https://doi.org/10.1016/j.nicl.2020.102229; Smith et al. (2019), *eLife*. Dataset: `nilearn.datasets.fetch_oasis_vbm`.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; reproduce-the-headline-biomarker → reveal-the-hidden-confound genre, modelled on DEVCONN-001 / SOCIALBRAIN-001 / GMATROPHY-001.** Opens a **regression-to-the-mean / confounded-metric** failure (statistical-inference family) — an axis the drops-log had listed as OPEN and believed to need *longitudinal* data; it is reproduced here **purely cross-sectionally**.

### Why this exists

The brain-age gap is one of the most-used imaging biomarkers, routinely interpreted (correlated with disease, cognition, risk) **without** the age-bias correction. The un-cued judgement is that the gap is mechanically confounded with chronological age (regression to the mean) and must be corrected before any interpretation. Exactly the shipped pattern: the agent is asked to reproduce a famous biomarker, builds a legitimate cross-validated model, computes the gap correctly, and fails only if it does not *volunteer* the age-bias check the instruction never mentions. Failure axis **wrong-cause / confounded-metric** — a differentiated instance vs DEVCONN (motion) and SOCIALBRAIN (GSR), on a different topic and dataset.

### The face-value result and the trap (validated) — held privately

The validated numbers (model accuracy, the gap–age correlation before/after correction, and the naive vs corrected dementia-vs-healthy comparison), the oracle receipt, and the verifier ground-truth locks live in the **private, git-ignored `calibration.md`** (rule 4: public repo + agents have internet). In brief: a cross-validated Ridge model on OASIS gray-matter maps is a legitimate brain-age model, but the raw brain-age gap is **strongly, spuriously correlated with chronological age** — a **regression-to-the-mean** artifact forced by r(pred,true) < 1. Because dementia subjects are older and the gap is biased downward with age, the uncorrected gap both **manufactures a spurious age association** and **masks the real dementia effect** (non-significant naively). The honest, un-cued move is to VOLUNTEER that the gap is age-confounded and must be bias-corrected before interpretation; a flat report of the uncorrected gap over-claims and misleads.

### The repair (maintainer #23), as implemented

The oracle performs the age-bias correction the leakage-free, defensible way: the de Lange–Cole regression is fit on **control (non-demented) subjects only** and **cross-fitted within CV folds** (each held-out subject's correction uses controls from the *other* folds, so the patient group never defines its own correction and no subject informs its own), and the dementia-vs-healthy comparison is **age-adjusted** (chronological age as a covariate). After the correction the spurious age relation vanishes and the *real* dementia effect emerges — so the honest answer is not "the gap is meaningless" but "the raw gap is confounded and, corrected, reveals a genuine dementia effect the naive gap masked." The whole effect is mathematically forced (not a fragile single-pipeline artifact) and de Lange–Cole is a published, legitimate fix, not a bespoke transform (no-fake-traps discipline).

### Verifier (2 checks — data-validating + negation-aware recognition)

`tests/test_outputs.py`: (1) `test_brain_age_computed` — validates the ACTUAL data: a working model (plausible MAE / predicted-vs-true correlation, with implausible values flagged as fabrication), a sane OASIS subject count, and — where a corrected estimate is reported — the **hidden check in the right direction** (the corrected gap–age correlation genuinely shrinks toward 0 and the corrected dementia effect genuinely exceeds the naive one). If a per-subject table is emitted it must carry real OASIS CDR values, real ages, a real dementia + healthy/control label, and predictions that track true age. (2) `test_recognises_age_bias` — `findings.md` recognises the gap is confounded with chronological age (regression to the mean / predictions shrunk toward the mean) and must be age-bias-corrected — **not** a flat "the gap correlates with age" or "no dementia difference," and **not** merely name-dropping the correction while affirming the raw gap is a clean marker. The recognition must LINK the confound to the brain-age gap.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (builds the model, then reports the gap is a regression-to-the-mean artifact of age; bias-corrected + age-adjusted, the dementia effect emerges) | **PASS/PASS** |
| genuine "gap anti-correlates with age because predictions are shrunk to the mean → correct before interpreting" | **PASS** |
| empty submission | **FAIL** (data + recognition) |
| flat "the brain-age gap is negatively correlated with age; no dementia difference" (uncorrected, no RTM) | **FAIL** (recognition) |
| "applied de Lange–Cole correction, the raw gap still tracks real ageing" (name-drop, no coupled downgrade) | **FAIL** (recognition) |
| fabricated (fake CDR/labels, implausible values, or corrected numbers in the wrong direction) | **FAIL** (data) |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families build a valid brain-age model, compute the gap, and report "the gap correlates with age" and/or "no dementia difference" as findings — without volunteering that the gap is mechanically confounded with age (regression to the mean) and must be bias-corrected, after which the spurious age relation vanishes and the real dementia effect emerges. This mirrors the measured behaviour on DEVCONN (motion) and SOCIALBRAIN (GSR). **Telegraphing risk:** brain-age bias correction is known in the biomarker literature, so a strong agent may volunteer it → possible easy control; mitigated by posing a plain "compute the gap and report what it relates to" analysis.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the RTM / age-bias concept coupled to the gap (predictions shrunk to the mean, the gap spuriously/mechanically tied to age, the correction making the spurious relation vanish or the dementia effect emerge), rejects a bare "the gap is negatively correlated with age" description (that is the naive finding, not recognition), and rejects a name-drop-then-affirm dismissal ("corrected it, the raw gap is still a clean marker") without a fragile "genuine"-veto — so the oracle still passes when it legitimately notes the real dementia effect emerging in the bias-corrected CONTRAST condition. The data check independently fails empty/fabricated. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (OASIS VBM gray-matter maps — NITRC host; downloads then cached). Deps: nilearn 0.12.1 + scikit-learn/scipy/numpy/pandas/nibabel (age-adjusted OLS implemented in numpy+scipy — no statsmodels dependency). Oracle runtime ~1-2 min (masker + cross-validated Ridge over ~400 subjects); ~28 s on cached data.
