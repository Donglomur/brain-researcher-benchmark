# Decoding stimulus modality from single-trial MEG (TIMEDECODE-001)

## Scientific context

When a stimulus is presented, the sensor-level MEG response carries information about what
was presented. A common way to quantify this is to train a classifier on the single-trial
sensor pattern and report its **cross-validated decoding accuracy** -- the fraction of
held-out examples whose class the decoder gets right. Here the two classes are the
**modality** of the stimulus: **auditory** vs **visual**.

## Task

Using the MNE **sample** dataset (`mne.datasets.sample`, the
`sample_audvis_filt-0-40_raw.fif` recording and its event file
`sample_audvis_filt-0-40_raw-eve.fif`), build a single-trial **auditory vs visual**
decoder from the MEG and report its **cross-validated decoding accuracy**.

Pin the pipeline so the result reproduces:

- Read the raw file and the events. The four stimulus events are
  `1 = auditory/left`, `2 = auditory/right`, `3 = visual/left`, `4 = visual/right`;
  the class label is the **modality**: auditory = {1, 2}, visual = {3, 4}.
- Use the **gradiometer** channels only (`meg="grad"`, exclude bads).
- Epoch from **-0.2 to 0.5 s** around each stimulus, `baseline=(None, 0)`, `proj=True`,
  reject epochs with `grad = 4000e-13`, and **decimate by 2**.
- Treat **each post-stimulus time sample in the 0.05-0.45 s window as one example**: the
  feature vector for an example is the gradiometer values at that time sample, and its
  label is the modality of the trial it comes from. Pool these examples over all trials
  and all time samples in the window.
- Standardise the features (`StandardScaler`) and classify with
  `LogisticRegression(max_iter=1000)`.
- Evaluate with **5-fold cross-validation** and report the mean accuracy over the folds.

Report the **decoding accuracy** (chance = 0.5 for this two-class problem).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `decoding_results.json` — the headline result as
  `{"cv_scheme": <str>, "accuracy": <float>, "n_trials": <int>,
  "n_samples_total": <int>, "n_classes": 2, "chance_level": 0.5}`.
- `per_fold.csv` — one row per cross-validation fold:
  `fold, n_test_samples, accuracy`.
- `run_metadata.json` — dataset id, contrast, sensors, epoch window, analysis window,
  decoder, and the cross-validation scheme you used.
- `findings.md` — a short written summary (a few sentences) stating the cross-validated
  decoding accuracy you obtained. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write a parseable `run_metadata.json`,
`decoding_results.json`, and `findings.md`.
