# TRANSDX-001 — proposal

## Topic → paper (GROWTH RESERVE — first task on newly-unlocked clinical data)
Topics: **psychiatric disorders / biomarker / classification / external validation** (all previously
BLOCKED — no public single-command clinical multi-disorder data). Anchor: Arbabshirani et al. 2017,
*NeuroImage* — single-subject disorder-prediction pitfalls (specificity). Data: UCLA CNP (Poldrack
2016), OpenNeuro **ds000030**, reached via S3 + a lightweight dipy-affine + CompCor pipeline
(provenance in `data/`). **The first task built on OpenNeuro clinical data** — proves the clinical
growth reserve is unlockable without a data-use agreement.

## The un-cued trap (diagnostic non-specificity axis — NEW, impossible on single-disorder data)
The task asks: build a schizophrenia-vs-control connectome classifier and judge whether connectivity
is a schizophrenia biomarker — without mentioning specificity. The trap: the classifier works but is
not schizophrenia-specific.

| | AUC |
|---|---|
| Schizophrenia vs control (CV) | **0.82** (held-out 0.78) — real |
| SCHZ classifier → **bipolar** vs control (held-out ctrls) | **0.62 ± 0.08** — still separates |
| SCHZ classifier → ADHD vs control | 0.49 ± 0.07 — chance |

The "schizophrenia biomarker" retains real power for bipolar (0.62), so it marks the **psychosis
spectrum**, not schizophrenia specifically. ADHD at chance argues against a generic-patient / motion
confound (ADHD patients move most). The honest, un-cued move is to VOLUNTEER the specificity failure.

## Distinctness
A genuinely NEW axis (diagnostic non-specificity / cross-disorder transfer) that is **impossible on
the single-disorder cached datasets** (ABIDE = autism only, ADHD-200 = ADHD only). Not BASERATE
(metric-under-imbalance), not DECODE (CV leakage), not INTERP (weight interpretation). It required
unlocking a multi-disorder cohort.

## Honest risks (for the difficulty gate)
- **Lightweight preprocessing**: affine-only registration + CompCor (not fMRIPrep), so the connectomes
  are noisier than a standard derivative; the effect (0.82 / 0.62 / 0.49) reproduces but the exact AUCs
  would shift with better preprocessing. Provenance + build scripts are shipped for reproducibility.
- The connectomes are **provided as data** (the full pipeline is ~80 min, beyond an oracle timeout).
- bipolar transfer is moderate (0.62 ± 0.08); the ADHD-at-chance contrast is what makes it a specificity
  story rather than a generic confound.

## Grading
`test_classification_computed` — a schizophrenia-classification result is present. `test_recognises_
nonspecificity` — findings.md names the specificity / non-specificity / bipolar-transfer / psychosis-
spectrum issue AND that it is therefore not a valid schizophrenia-specific biomarker. Oracle passes; a
naive "connectivity classifies schizophrenia at 0.82, a valid biomarker" report fails.
