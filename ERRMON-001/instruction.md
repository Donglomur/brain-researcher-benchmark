# Error-related frontocentral negativity in the ERP CORE Flankers task (ERRMON-001)

## Scientific context

In a flanker task, a participant presses a left or right button to report the direction of
a central target arrow while flanking arrows point the same way (compatible) or the opposite
way (incompatible). On a minority of trials the participant presses the wrong button. Errors
are accompanied by a sharp **frontocentral negativity** in the EEG, largest at the midline
frontocentral electrode **FCz** — the **error-related negativity (ERN)**. Its size is
summarised by the **error-minus-correct difference** in the frontocentral EEG. This task uses
the openly available **ERP CORE** Flankers recording (subject 001).

## Task

Using the **ERP CORE Flankers** recording for **subject 001**, **compute the amplitude of
the error-related frontocentral negativity** and report it as the **mean error-minus-correct
amplitude at electrode FCz, in microvolts, over a 0-100 ms window**, following the fixed
processing below.

### Data

Fetch the dataset with `mne.datasets.erp_core.data_path()` (downloads automatically, no
credentials). Use the file `ERP-CORE_Subject-001_Task-Flankers_eeg.fif`. Read its
annotations with `mne.events_from_annotations`; the recording marks both the **button
presses** (`response/left`, `response/right`) and the **flanker arrays**
(`stimulus/compatible/target_left`, `stimulus/compatible/target_right`,
`stimulus/incompatible/target_left`, `stimulus/incompatible/target_right`). The recording
has 30 scalp EEG electrodes plus 3 peripheral EOG channels (`HEOG_left`, `HEOG_right`,
`VEOG_lower`).

### Fixed processing (pin exactly)

- Pair each flanker array with the **next button press**. A trial is an **error** if the
  pressed hand does not match the target arrow's direction (`target_left` should be answered
  with `response/left`, `target_right` with `response/right`); otherwise it is **correct**.
- Set the 3 EOG channels aside and analyse the **30 scalp EEG electrodes**. Apply an
  **average reference** across those 30 electrodes.
- Apply a **0.1-30 Hz band-pass** filter.
- Epoch the data around the events of interest, apply a **pre-event baseline** (the 200 ms
  before each event), and average the error trials and the correct trials separately.
- Measure the response as the **mean amplitude at FCz in the 0-100 ms post-event window**,
  taken as the **error-average minus the correct-average**.
- Report that error-minus-correct amplitude in **microvolts**.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `ern.json` — at minimum `{"ern_amplitude_uv": <float>, "electrode": "FCz",
  "measure": "mean error-minus-correct amplitude, 0-100 ms", "window_ms": [0, 100],
  "n_error_trials": <int>, "n_correct_trials": <int>}`.
- `run_metadata.json` — dataset id, file, trial definition, number of error/correct trials,
  electrode, reference, band-pass, baseline, and the measurement window you used.
- `findings.md` — a few sentences reporting the error-related frontocentral negativity
  amplitude. State only what your analysis supports.

## Failure handling

If the ERP CORE Flankers recording cannot be resolved, exit non-zero with
`failed_precondition` and a non-empty reason, and still write parseable `run_metadata.json`,
`ern.json`, and `findings.md`.
