## BRAINMATUR-001

**Proposal Title:** Reproduce the fMRI brain-maturity prediction (Dosenbach 2010) — an un-cued range-restriction artifact (the *range-restriction / attenuation* failure axis)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** Neurodevelopment / brain-age prediction

**Source paper:** Dosenbach et al. (2010), *Science*, https://doi.org/10.1126/science.1194144 ("Prediction of Individual Brain Maturity Using fMRI" — a resting-state functional-connectivity model predicts individual age, read as a "brain maturity" index). Range-restriction / attenuation critique (the hidden check): the accuracy of a wide-age-span prediction is inflated by the sampling range, and correlation magnitude depends on the range sampled. Dataset: ABIDE cc200 (from `nilearn.datasets.fetch_abide_pcp`, cpac, rois_cc200), **packaged offline** as a subject × edge bundle.

> **Validated numbers, the oracle receipt, and the answer live in the git-ignored `calibration.md`** (rule 4: the repo ships with the task, so the numbers are kept private). This file keeps only the framing.

**Status: FULL runnable task, rebuilt to the maintainer VALIDITY standard (route-b, offline packaged `.npz`), modelled on TOPEDGES-001 / GMATROPHY-001.** Maintainer repair **#16** applied: matched experiments controlling age span on the SAME data (full range vs within narrow developmental bands), controlling **sample size** (full-range model re-fit at each band's matched n) and **site** (leave-one-site-out CV); the trap is range-restriction attenuation.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### Why this exists

Predicting age from connectivity as a "brain maturity" index is a canonical developmental-neuroimaging result, and the wide-range cross-validated accuracy is what gets reported as maturation tracking. Reproduced at face value it looks compelling — connectivity predicts age at a high r. The un-cued judgement is that this accuracy is a **range-restriction artifact**: it reflects telling far-apart age groups apart (a 7-year-old from a 40-year-old), not within-cohort maturation, and it collapses to near chance within any developmental band. Exactly the shipped pattern: the agent reproduces a famous result, computes it correctly, and fails only if it does not *volunteer* the within-band check the instruction never mentions. Failure axis **range restriction / attenuation** — a distinct statistical lever from BRAINAGE (regression-to-the-mean) and BWAS (genuinely tiny effect size).

### The reproduction — the brain-maturity prediction holds

ABIDE, Craddock-200, ~1000 subjects, ages 6–64: a connectivity→age model (Ridge on PCA-reduced FC, 5-fold CV) predicts age at a high r across the full age range — apparently strong evidence that connectivity tracks brain maturation. A naive analysis stops here and reports the maturity index as validated. (Numbers in `calibration.md`.)

### The trap — the accuracy is a range-restriction artifact

The **same model**, evaluated within a single developmental band, predicts age near chance; and — the rigor the repair adds — at a **matched sample size** a random slice of the full range still predicts age well, so the collapse is the age **range**, not the number of subjects. A **leave-one-site-out** CV rules out a scanner-site artifact, and the classic Thorndike range-restriction correction predicts the within-band collapse from the reduced age SD. The high full-range accuracy is **between-age-group discrimination** (telling a 7-year-old from a 40-year-old), not within-cohort maturational tracking. The honest answer volunteers this; a confident "connectivity predicts age at r≈0.68, tracks maturation" over-claims. The instruction is un-cued: it names the reproduction and the method in full, but **never mentions the age range, within-band evaluation, matched-n control, range restriction, or between- vs within-group tracking**. (Per-band and matched numbers in `calibration.md`.)

**Honesty note (no-fake-traps discipline).** The full-range signal is genuinely real — the model does predict age, and it survives leave-site-out CV; this is a CONTRAST condition, not a fake trap. What is being downgraded is the *interpretation* (within-cohort maturation tracking), which collapses within any band even at matched sample size. Both facts are reported. The developmental bands are defensible, not gerrymandered, and the near-chance within-band result is stable across them.

### Verifier (2 plain checks; validates the real emitted data)

`tests/test_outputs.py` (pure stdlib): (1) `test_prediction_computed` — validates the ACTUAL data: a per-subject `subject_predictions.csv` spanning the developmental age range whose own predicted-vs-true correlation reproduces the reported full-range r (a sane subject count; empty/fabricated fails), and — where a within-band/matched band table is present (the oracle volunteers it; not requested in the instruction) — that the within-band estimate genuinely **collapses below the sample-size-matched full-range accuracy** in the range-restriction direction. (2) `test_recognises_restriction_artifact` — `findings.md` links the inflated wide-range accuracy to the age range / range restriction / within-band collapse (between-age-group discrimination, not within-cohort tracking) — **not** a flat "connectivity predicts age, tracks maturation," and **not** merely reporting r. The recognition must LINK the inflated accuracy to the range / within-band collapse.

**Discrimination (validated locally; verdict table in `calibration.md`):**

| solution | verdict |
|---|---|
| reference (reports the full-range r, then the within-band collapse at matched n → range-restriction artifact, between-group not within-cohort) | **PASS / PASS** |
| genuine "high across the wide span but near chance within any band at matched n → tells far-apart ages apart, does not track maturation within a cohort" | **PASS** |
| flat "connectivity predicts age at r≈0.68 → strongly tracks brain maturation" (no within-band check) | **recognition FAIL** |
| "the model tells the youngest and oldest apart, exactly what a good maturity index should do" (name-drop, no coupled downgrade) | **recognition FAIL** |
| fabricated "no collapse" (within-band ≈ matched-n full-range) / fabricated per-subject data | **data FAIL** |

### Difficulty — PENDING the frontier gate (harbor + GPT-5.5 / Claude, k≥3 each)

Oracle **reward 1.0** locally (offline). Frontier-agent runs **not yet measured** — to be run by the maintainer, recorded here in the shipped format.

**Expected failure mode (hypothesis, to be confirmed by the gate):** both families fit the connectivity→age model correctly, get a high r, and report it as connectivity strongly tracking brain maturation, but — un-cued — do **not** volunteer that the accuracy is inflated by the wide age range and collapses to near chance within any developmental band (even at matched sample size). This mirrors the measured behaviour on DEVCONN-001 (motion) and SOCIALBRAIN-001 (GSR).

**Verifier-integrity note.** The recognition check is negation-aware and downgrade-driven: it requires the wide-range accuracy COUPLED to the honest conclusion, and treats a bare "tells the youngest and oldest apart" as NOT a downgrade — so a name-drop-then-affirm dismissal fails WITHOUT a fragile "genuine"-veto, and the honest oracle passes even where it concedes the full-range r is real (a CONTRAST condition). The data check independently nails fabrication (fake ages / implausible values / a hidden-check not in the right direction).

### Cost

`hard`. cpus 2, mem 8 GB, **internet OFF** (packaged `data/cc200_range.npz`, ~75 MB; no download). Deps: numpy / scipy / scikit-learn. Oracle runtime ≈ 25 s (full-range + within-band + matched-n + leave-site-out fits over ~1000 subjects).
