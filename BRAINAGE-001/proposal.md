## BRAINAGE-001

**Proposal Title:** Reproduce the brain-age gap biomarker (Franke 2010) — an un-cued regression-to-the-mean / age-bias confound (the *wrong-cause / confounded-metric* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Brain-age / imaging biomarkers

**Source paper:** Franke et al. (2010), *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2010.01.005 ("BrainAGE" — predict age from structural MRI; the predicted−chronological "brain-age gap" is a biomarker of accelerated/decelerated ageing). Un-cued check / bias correction: de Lange & Cole (2020), *NeuroImage: Clinical*, https://doi.org/10.1016/j.nicl.2020.102229; Smith et al. (2019), *eLife*. Dataset: `nilearn.datasets.fetch_oasis_vbm`.

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline biomarker → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001.** Opens a **regression-to-the-mean / selection** confound (statistical-inference family) — an axis the drops-log had listed as OPEN and believed to need *longitudinal* data; it is reproduced here **purely cross-sectionally**.

### Why this exists

The brain-age gap is one of the most-used imaging biomarkers, routinely interpreted (correlated with disease, cognition, risk) **without** the age-bias correction. The un-cued judgement is that the gap is mechanically confounded with chronological age (regression to the mean) and must be corrected before any interpretation. Exactly the shipped pattern: the agent is asked to reproduce a famous biomarker, builds a legitimate model, computes the gap correctly, and fails only if it does not *volunteer* the age-bias check the instruction never mentions. Failure axis **wrong-cause / confounded-metric** — a differentiated instance vs DEVCONN (motion) and SOCIALBRAIN (GSR), on a different topic and dataset.

### The reproduction (Step-0 validated) — a working brain-age model

OASIS VBM, n≈403, cross-validated Ridge on gray-matter maps: **MAE = 11.9 yr, r(predicted, true) = 0.80** — a legitimate brain-age model, reproducing the Franke (2010) BrainAGE paradigm. A naive analysis computes the gap and reports what it relates to.

### The trap (Step-0 validated) — the gap is age-confounded, and it distorts inference

| quantity | naive gap | after de Lange–Cole bias correction |
|---|---|---|
| corr(brain-age gap, chronological age) | **r = −0.62** (p = 2.5e-44) | **r = 0.00** |
| dementia (CDR>0) vs healthy gap difference | +2.0 yr, p = **0.21 (n.s.)** | +7.9 yr, p = **0.0015 (sig.)** |

Because an imperfect regressor shrinks predictions toward the sample mean, the gap is spuriously, strongly correlated with age — a **regression-to-the-mean** artifact. The uncorrected gap both **manufactures a spurious age association** and **masks the real dementia effect** (non-significant naively, significant after correction). The honest, un-cued move is to VOLUNTEER that the gap is age-confounded and must be bias-corrected (de Lange & Cole 2020) before any interpretation; a flat report of the uncorrected gap over-claims and misleads.

**Honesty note (no-fake-traps discipline, from Step-0).** The whole effect is mathematically forced by r(pred,true) < 1 — it is not a fragile artifact of one pipeline; it is robust across smoothing/resolution. The de Lange–Cole correction is a legitimate, published fix, not a bespoke transform: it regresses predicted on true age in the training sense and rescales, and after it the spurious age correlation vanishes (r ≈ 0) while the *real* dementia effect emerges (p = 0.0015). So the honest answer is not "the gap is meaningless" but "the raw gap is confounded and, corrected, reveals a genuine dementia effect the naive gap masked."

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_brain_age_computed` — a brain-age model / gap was computed (a `gap`/`mae`/`pred`/`brain_age` numeric is present in `*.json`); (2) `test_recognises_age_bias` — `findings.md` recognises the gap is confounded with chronological age (regression to the mean / predictions shrunk toward the mean) and must be age-bias-corrected — **not** a flat "the gap correlates with age" or "no dementia difference," and **not** merely name-dropping the correction while affirming the raw gap is a clean marker. The recognition must LINK the confound to the brain-age gap.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (builds the model, then reports the gap is a regression-to-the-mean artifact of age; bias-corrected, the dementia effect emerges) | **PASS** |
| genuine "gap anti-correlates with age because predictions are shrunk to the mean → correct before interpreting" | **PASS** |
| flat "the brain-age gap correlates with age; no dementia difference" (uncorrected, no RTM) | **FAIL** |
| "applied de Lange–Cole correction, the raw gap still tracks real ageing" (name-drop, no coupled downgrade) | **FAIL** |
| "the gap is a bit noisy" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families build a valid brain-age model, compute the gap, and report "the gap correlates with age" and/or "no dementia difference" as findings — without volunteering that the gap is mechanically confounded with age (regression to the mean) and must be bias-corrected, after which the spurious age relation vanishes and the real dementia effect emerges. This mirrors the measured behaviour on DEVCONN (motion) and SOCIALBRAIN (GSR). **Telegraphing risk:** brain-age bias correction is known in the biomarker literature, so a strong agent may volunteer it → possible easy control; mitigated by posing a plain "compute the gap and report what it relates to" analysis.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the RTM / age-bias concept coupled to the gap (predictions shrunk to the mean, the gap spuriously tied to age, the correction making the spurious relation vanish or the dementia effect emerge), and rejects a name-drop-then-affirm dismissal ("corrected it, the raw gap is still a clean marker") without a fragile "genuine"-veto — so the oracle still passes when it legitimately notes the real dementia effect emerging in the bias-corrected CONTRAST condition. Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (OASIS VBM gray-matter maps — NITRC host; downloads then cached). Deps: nilearn 0.12.1 + scikit-learn/scipy/numpy/pandas/nibabel. Oracle runtime ~1-2 min (masker + cross-validated Ridge over ~400 subjects).
