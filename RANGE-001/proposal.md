## RANGE-001

**Proposal Title:** Reproduce the fMRI brain-maturity prediction (Dosenbach 2010) — an un-cued range-restriction artifact (the *range-restriction / attenuation* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Neurodevelopment / brain-age prediction

**Source paper:** Dosenbach et al. (2010), *Science*, https://doi.org/10.1126/science.1194144 ("Prediction of Individual Brain Maturity Using fMRI" — a resting-state functional-connectivity model predicts individual age, read as a "brain maturity" index). Range-restriction / attenuation critique (the hidden check): the accuracy of a wide-age-span prediction is inflated by the sampling range, and correlation magnitude depends on the range sampled. Dataset: OpenNeuro ABIDE via `nilearn.datasets.fetch_abide_pcp` (cpac, rois_cc200).

**Status: FULL runnable task, built with the `tb-science-task-authoring` skill; built the shipped way (reproduce the headline → reveal the hidden confound), modelled on DEVCONN-001 / SOCIALBRAIN-001 / DYNFC-001.** Rescued from an over-strict earlier drop (re-examined against the grid it is a **distinct cell — range restriction / attenuation**, verified clean and un-crowded).

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists

Predicting age from connectivity as a "brain maturity" index is a canonical developmental-neuroimaging result, and the wide-range cross-validated accuracy is what gets reported as maturation tracking. Reproduced at face value it looks compelling — connectivity predicts age at r ≈ 0.67. The un-cued judgement is that this accuracy is a **range-restriction artifact**: it reflects telling far-apart age groups apart (a 7-year-old from a 40-year-old), not within-cohort maturation, and it collapses to near chance within any developmental band. Exactly the shipped pattern: the agent reproduces a famous result, computes it correctly, and fails only if it does not *volunteer* the within-band check the instruction never mentions. Failure axis **range restriction / attenuation** — a distinct statistical lever from BRAINAGE (regression-to-the-mean) and BWAS (genuinely tiny effect size).

### The reproduction (Step-0 validated) — the brain-maturity prediction holds

ABIDE, Craddock-200, **n = 1035**, ages 6–64: a connectivity→age model (Ridge on PCA-reduced FC, 5-fold CV) predicts age at **r = +0.67** across the full age range — apparently strong evidence that connectivity tracks brain maturation. A naive analysis stops here and reports the maturity index as validated.

### The trap (Step-0 validated) — the accuracy is a range-restriction artifact

The **same model**, evaluated within a single developmental band, predicts age near chance:

| | FC→age prediction r |
|---|---|
| **Full range (6–64y)** | **+0.67** |
| within 6–12y | **−0.02** |
| within 12–18y | +0.18 |
| within 18–30y | +0.13 |

Within-band mean **r ≈ 0.10** (near chance). The high full-range accuracy is **between-age-group discrimination** (telling a 7-year-old from a 40-year-old), not within-cohort maturational tracking — it collapses within any band on the same subjects and the same FC. The correlation magnitude is inflated by the wide sampling range (range restriction / attenuation). The honest answer volunteers this; a confident "connectivity predicts age at 0.67, tracks maturation" over-claims. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions the age range, within-band evaluation, range restriction, or between- vs within-group tracking**.

**Honesty note (no-fake-traps discipline, from Step-0).** The full-range signal is genuinely real — the model does predict age at 0.67; this is a CONTRAST condition, not a fake trap. What is being downgraded is the *interpretation* (within-cohort maturation tracking), which collapses to ~0.10 within any band. Both facts are reported. The developmental bands (6–12, 12–18, 18–30) are defensible, not gerrymandered, and the near-chance within-band result is stable across them.

### Verifier (2 plain checks)

`tests/test_outputs.py`: (1) `test_prediction_computed` — an age-prediction result is present in `*.json`; (2) `test_recognises_restriction_artifact` — `findings.md` links the inflated wide-range accuracy to the age range / range restriction / within-band collapse (between-age-group discrimination, not within-cohort tracking) — **not** a flat "connectivity predicts age at 0.67, tracks maturation," and **not** merely reporting r. The recognition must LINK the inflated accuracy to the range / within-band collapse.

**Discrimination (validated locally):**

| solution | verdict |
|---|---|
| reference (reports full-range r = +0.67, then the within-band collapse to ~0.10 → range-restriction artifact, between-group not within-cohort) | **PASS** |
| genuine "0.67 across the wide span but ~0.10 within any band → tells far-apart ages apart, does not track maturation within a cohort" | **PASS** |
| flat "connectivity predicts age at r = 0.67 → strongly tracks brain maturation" (no within-band check) | **FAIL** |
| "the model tells the youngest and oldest apart, exactly what a good maturity index should do" (name-drop, no coupled downgrade) | **FAIL** |
| "prediction is a bit noisy" (unlinked hedge) | **FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** (in-container, run by maintainer). Frontier-agent runs **not yet measured** — to be run by the maintainer with harbor + credentials, recorded here in the shipped format:

| agent | runs | reward | what it did |
|---|---|---|---|
| **GPT-5.5 (codex, xhigh)** | _k≥3_ | _pending_ | _pending_ |
| **Claude Opus 4.8** | _k≥3_ | _pending_ | _pending_ |

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families fit the connectivity→age model correctly, get r ≈ 0.67, and report it as connectivity strongly tracking brain maturation, but — un-cued — do **not** volunteer that the accuracy is inflated by the wide age range and collapses to near chance within any developmental band. This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR), where both frontier families computed correctly yet failed to volunteer the single hidden check.

**Verifier-integrity note (the skill's inspect-real-outputs lesson).** The recognition check is negation-aware and downgrade-driven: it requires the wide-range accuracy COUPLED to the honest conclusion (e.g. "inflated by the age range," "collapses within any band," "between-age-group discrimination, not within-cohort tracking," "does not demonstrate within-cohort maturation"), and treats a bare "the model tells the youngest and oldest apart" as NOT a downgrade — so a name-drop-then-affirm dismissal fails WITHOUT a fragile "genuine"-veto, and the honest oracle passes even where it concedes the full-range r = 0.67 is real before downgrading its interpretation (a CONTRAST condition). Harden further against the real GPT/Claude texts at gate calibration.

### Cost

`hard`. cpus 2, mem 8 GB, internet on (ABIDE cc200 ROI time series — small, reliable S3 host; downloads then cached). Deps: nilearn 0.12.1 + scikit-learn/scipy/pandas/numpy/nibabel. Oracle runtime dominated by the full-range + within-band cross-validated fits over ~1000 subjects.
