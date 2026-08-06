# EEGLEAK-001 — proposal (sibling)

## Topic → paper
Differentiated SIBLING of DECODE, found by the sibling hunt over duplicate papers. Anchor: Abraham et
al. 2014 (scikit-learn for neuroimaging) + CV-leakage literature (Varoquaux 2017; Lemm 2011). Fills the
explicitly-empty **EEG cell of the leakage/CV-circularity axis** (DECODE is fMRI/Haxby).

## The un-cued trap (leakage × EEG modality)
To get more samples, each motor-imagery trial is cut into overlapping windows. A **random k-fold** over
those windows leaks: windows from the same trial are highly correlated and land in both train and test,
so the classifier partly recognises the trial, not the class. Blocking by trial/run removes it.

Validated (eegbci runs 4/8/12, CSP+LDA, 9 subjects): random 5-fold **0.77** vs trial/run-blocked
**0.60** vs true one-window-per-trial **0.60** — inflation **+0.17**, in **100%** of subjects.

## Distinctness (not a near-dup of DECODE)
DECODE's trap is fMRI temporal-block leakage (random vs leave-one-run-out on autocorrelated TRs of a
blocked-run dataset with an ingrained run-blocking convention). EEG window-decoding has **no** such
convention — random k-fold over windowed epochs is common practice — and the leak is induced by the
analyst's **windowing** step, absent from Haxby. An agent that solved DECODE by mimicking Haxby's
leave-one-run-out does not mechanically pass here. New modality (EEG), distinct mechanism.

## Grading
`test_decoding_computed` — an accuracy result is present. `test_recognises_window_leakage` — findings.md
names the windowing / same-trial / non-independence / grouped-CV issue AND links it to inflation.
Oracle passes; a naive "≈77% decoding accuracy" report fails.
