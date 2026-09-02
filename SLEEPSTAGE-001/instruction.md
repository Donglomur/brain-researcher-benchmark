# Automatic sleep staging from the EEG (SLEEPSTAGE-001)

## Scientific context

Automatic sleep staging classifies each 30-s epoch of a polysomnogram into the five
AASM stages — **Wake, N1, N2, N3, REM** — from the EEG. The Sleep-EDF Expanded database
(PhysioNet) is the standard public benchmark, and the headline result of a staging study
is the **cross-validated accuracy and Cohen kappa** of the classifier over the 30-s
epochs.

## Task

Using the PhysioNet **Sleep-EDF** age cohort
(`mne.datasets.sleep_physionet.age.fetch_data`, **subjects `[0, 1, 2, 3, 4, 5]`,
recording 1**), build a 5-class AASM sleep stager from the EEG and report its
**cross-validated staging accuracy and Cohen kappa**.

Pin the pipeline so the result reproduces:

- Use the two EEG derivations **`EEG Fpz-Cz`** and **`EEG Pz-Oz`**, in **30-s epochs**
  aligned to the hypnogram annotations.
- Map the annotations to the **5 AASM classes**, merging *Sleep stage 3* and *Sleep
  stage 4* into **N3** (W → Wake, 1 → N1, 2 → N2, 3/4 → N3, R → REM).
- Features: per epoch, the **relative band power** in the delta (0.5–4 Hz), theta
  (4–8 Hz), alpha (8–12 Hz), sigma (12–16 Hz) and beta (16–30 Hz) bands for each of the
  two channels (Welch PSD), i.e. 10 features per epoch.
- Classifier: a **random forest** with **200 trees** (`random_state=0`).

Report the cross-validated **accuracy** and **Cohen kappa** over the pinned subjects.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `staging_results.json` — the headline result as
  `{"cv_scheme": <str>, "accuracy": <float>, "cohen_kappa": <float>,
  "n_subjects": 6, "n_epochs": <int>, "n_classes": 5}`.
- `per_fold.csv` — one row per cross-validation fold:
  `fold, n_test_epochs, accuracy, kappa` (`fold` is any identifier for the fold).
- `run_metadata.json` — dataset id, subjects, channels, epoch length, class mapping,
  features, classifier, and the cross-validation scheme you used.
- `findings.md` — a short written summary (a few sentences) stating the cross-validated
  staging accuracy and Cohen kappa you obtained. State only what your analysis actually
  supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write a parseable `run_metadata.json`, `staging_results.json`,
and `findings.md`.
