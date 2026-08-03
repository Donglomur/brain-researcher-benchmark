## EEGMC-001

**Proposal Title:** Left-vs-right motor-imagery EEG features (eegbci) — an un-cued multiple-comparisons inflation (the *multiple-comparisons* axis on the **EEG** modality)

**Scientific Domain:** Life Sciences · **Field:** Neuroscience · **Subfield:** EEG / brain–computer interfaces

**Source finding:** Schalk et al. (2004, PhysioNet EEG-MMI / BCI2000); multiple-comparisons references: Eklund et al. (2016). Data: `mne.datasets.eegbci` (subject 1, runs 4/8/12 = left/right fist imagery).

**Status: FULL runnable task.** Fills the **multiple-comparisons × EEG** cell — which, with AUTCONN (fMRI connectivity) and COGVBM (structural VBM), means the **multiple-comparisons axis is now demonstrated across all three modalities**. This is the anti-monoculture payoff: a fundamental inference error shown to generalise across measurement types.

**Difficulty vs frontier agents: NOT YET MEASURED** (gate deferred).

### The trap (Step-0 validated; `scratchpad/eeg_mc_step0.py`)
eegbci subject 1, runs 4/8/12, average reference, ~7500 channel×frequency features, t-test left (T1) vs right (T2) imagery:

| threshold | "significant" features |
|---|---|
| uncorrected p<0.05 | **700** (~374 by chance) |
| uncorrected p<0.001 | 32 (~7 by chance) |
| FDR q<0.05 | 0 |
| FWE (Bonferroni) | **0** |

Uncorrected flags hundreds of features; **0 survive correction**.

### Verifier (2 plain checks) + local calibration
`tests/test_outputs.py`: (1) a channel×frequency search was run (thousands of tests); (2) the reported number of discriminating features reflects correction (≤20 — ~0 survive), not the uncorrected ~32/700. Numeric (same robust extractor as AUTCONN/COGVBM).

Local calibration (`scratchpad/validate_eegmc.py`): oracle + honest-zero PASS/PASS; naive uncorrected (32 and 700) FAIL the correction check; broken FAILs computed.

### Honest caveats / open risks
1. **Difficulty UNTESTED** — needs the gate. Telegraphing: correction may be in frontier priors (cf. AUTCONN/COGVBM).
2. **Multiple-comparisons axis reused** (3rd) — but this is deliberate *modality* coverage: the same axis across fMRI/structural/EEG. Incremental novelty; real anti-monoculture value.
3. **Small n** (~23 vs 22 epochs, single subject) — natural for within-subject imagery; the mult-comp point (0 survive) holds regardless.

### Cost
`hard`. cpus 2, mem 8 GB, internet on (eegbci EDF via MNE/PhysioNet — small, reliable). Deps: mne 1.12.1 + pooch + numpy/scipy.
