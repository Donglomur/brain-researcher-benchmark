# Decoding imagined movement from the EEG (MOTORIMAGERY-001)

## Scientific context

In a motor-imagery brain-computer interface, the participant *imagines* moving a limb and
a classifier reads out which movement was imagined from the sensorimotor rhythms (the
mu, ~8-12 Hz, and beta, ~13-30 Hz, bands) of the EEG. The standard pipeline spatially
filters the band-passed EEG with **Common Spatial Patterns (CSP)** and classifies the
log-variance features with **linear discriminant analysis (LDA)**. The headline result
of such a study is the **cross-validated decoding accuracy**.

## Task

Using the PhysioNet **EEG Motor Movement/Imagery** dataset
(`mne.datasets.eegbci.load_data`, **subjects `1-10`**, **runs `[6, 10, 14]`** — the
*imagined* "both fists" vs "both feet" runs), build a per-subject **CSP + LDA** decoder of
**imagined hands vs feet** and report its **cross-validated decoding accuracy**, averaged
over the subjects.

Pin the pipeline so the result reproduces:

- For each subject, load runs `[6, 10, 14]` and concatenate them. Standardise the channel
  names (`mne.datasets.eegbci.standardize`) and set the `standard_1005` montage.
- Band-pass filter the EEG to **7-30 Hz** (FIR).
- The annotations mark **T1 = both fists (hands)** and **T2 = both feet (feet)**; ignore
  the rest periods (T0). Extract epochs from **1.0 to 2.0 s** after each cue, using **all
  EEG channels**, with no baseline correction.
- Decoder: **CSP with 4 components** (log-variance features) followed by **LDA**.
- Evaluate with **5-fold stratified cross-validation** within each subject.

Report the **decoding accuracy** as the mean, across the 10 subjects, of each subject's
cross-validated accuracy (chance = 0.5 for this two-class problem).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `decoding_results.json` — the headline result as
  `{"cv_scheme": <str>, "accuracy": <float>, "cohen_kappa": <float>,
  "n_subjects": 10, "n_epochs_total": <int>, "n_classes": 2, "chance_level": 0.5}`.
- `per_subject.csv` — one row per subject: `subject, n_epochs, accuracy, kappa`.
- `run_metadata.json` — dataset id, subjects, runs, band, epoch window, channels,
  decoder, and the cross-validation scheme you used.
- `findings.md` — a short written summary (a few sentences) stating the cross-validated
  decoding accuracy (and Cohen kappa) you obtained. State only what your analysis
  actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write a parseable `run_metadata.json`,
`decoding_results.json`, and `findings.md`.
