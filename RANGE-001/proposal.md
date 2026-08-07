# RANGE-001 — proposal (rescued from an over-strict drop)

## Topic → paper
Topic: **neurodevelopment / prediction / brain age** (landscape). Originally surfaced in the DROPPED
re-attack as a "range-restriction" candidate but DROPPED as over-clustering with BRAINAGE/BWAS; on
re-examination against the grid it is a **distinct cell** (range-restriction lever), verified clean.
Anchor: Dosenbach et al. 2010, *Science* ("Prediction of individual brain maturity using fMRI") + the
range-restriction critique of wide-age-span prediction accuracy.

## The un-cued trap (range-restriction axis)
The task asks to predict age from connectivity as a "brain maturity" index — without mentioning age
range. The trap: the accuracy is inflated by the wide sampling range.

| | FC→age prediction r |
|---|---|
| Full range (6–64y) | **+0.67** |
| within 6–12y | **−0.02** |
| within 12–18y | +0.18 |
| within 18–30y | +0.13 |

The high full-range accuracy is between-age-group discrimination (telling a 7-year-old from a
40-year-old), not within-cohort maturation — it collapses to ~0.10 within any band (same subjects, same
FC). The honest, un-cued move is to VOLUNTEER that the accuracy is a range-restriction artifact.

Validated: ABIDE cc200, 1035 subjects, full-range r=0.67, within-band mean 0.10.

## Distinctness (why it is a different cell, not a duplicate)
A genuinely distinct statistical axis: **range restriction / attenuation** — the correlation magnitude
depends on the sampling range. NOT regression-to-the-mean (BRAINAGE — brain-age gap bias, structural
OASIS), NOT effect-size (BWAS — the effect is genuinely tiny, ABIDE FIQ). Three distinct axes in the
prediction lane, on 2 datasets/modalities — spread, not monoculture. I'd dropped it too strictly; per
the written standard it belongs (under-crowded cell, real dramatic signal).

## Grading
`test_prediction_computed` — an age-prediction result is present. `test_recognises_range_restriction` —
findings.md links the inflated wide-range accuracy to the age range / range restriction / within-band
collapse (between-group not within-cohort). Oracle passes; a naive "connectivity predicts age at r=0.67,
tracks maturation" report fails.
