# Sleep-staging performance from the EEG (AASMSTAGE-001)

## Scientific context

Automatic sleep staging classifies each 30-s epoch of a polysomnogram into the five AASM
stages -- **Wake, N1, N2, N3, REM** -- from the EEG. The Sleep-EDF Expanded database
(PhysioNet) is the standard public benchmark. A staging study is judged by how well the
classifier recovers the sleep stages across a night.

## Task

Using the PhysioNet **Sleep-EDF** age cohort
(`mne.datasets.sleep_physionet.age.fetch_data`, **subjects `[0, 1, 2, 3, 4, 5]`,
recording `1`**), build a 5-class AASM sleep stager from the EEG and report the
**cross-validated accuracy with which it recovers the five stages**.

Pin the pipeline so the result reproduces:

- Use the two EEG derivations **`EEG Fpz-Cz`** and **`EEG Pz-Oz`**, in **30-s epochs**
  aligned to the hypnogram annotations (crop the recording to the sleep period, from
  30 min before the first non-Wake epoch to 30 min after the last).
- Map the annotations to the **5 AASM classes**, merging *Sleep stage 3* and *Sleep
  stage 4* into **N3** (W -> Wake, 1 -> N1, 2 -> N2, 3/4 -> N3, R -> REM).
- Features: per epoch, the **relative band power** (Welch PSD, normalised to sum to 1
  across 0.5-30 Hz) in the delta (0.5-4.5 Hz), theta (4.5-8.5 Hz), alpha (8.5-11.5 Hz),
  sigma (11.5-15.5 Hz) and beta (15.5-30 Hz) bands for each of the two channels.
- Classifier: a **random forest** with **200 trees** (`random_state=42`).
- Evaluate with **leave-one-subject-out** cross-validation over the pinned subjects (train
  on five subjects, test on the held-out one), pooling the held-out predictions.

Report the cross-validated accuracy with which the five stages are recovered.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `staging_results.json` — the headline result as
  `{"cv_scheme": <str>, "accuracy": <float>, "n_stages": 5, "stages": [<str>...],
  "n_epochs_total": <int>}`.
- `run_metadata.json` — dataset id, subjects, recording, channels, features, classifier,
  and the cross-validation scheme you used.
- `findings.md` — a short written summary (a few sentences) reporting the cross-validated
  accuracy you obtained. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write a parseable `run_metadata.json`,
`staging_results.json`, and `findings.md`.
