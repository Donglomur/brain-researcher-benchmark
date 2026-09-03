# Auditory N100 amplitude in the MNE sample dataset (AUDN1-001)

## Scientific context

A brief tone elicits, ~100 ms later, the **auditory N100** (the N1; in EEG a
fronto-central negativity, the counterpart of the MEG N100m/M100), a robust marker of
auditory cortical processing. A convenient scalp-level, reference-independent summary of
its size is the **peak Global Field Power (GFP)** — the spatial standard deviation across
electrodes — in the N100 time window. This task uses the MNE **sample** dataset (combined
MEG/EEG recording of an auditory + visual paradigm).

## Task

Using the MNE **sample** dataset, **compute the auditory N100 amplitude for the
left-auditory condition** and report it as the **peak EEG Global Field Power amplitude
(in microvolts) in the 80-120 ms window**, following the fixed processing below.

### Data

Fetch the dataset with `mne.datasets.sample.data_path()` (downloads automatically, no
credentials). Use the filtered raw file
`MEG/sample/sample_audvis_filt-0-40_raw.fif`. Stimulus triggers are on the `STI 014`
channel; the **left-auditory** stimulus is trigger code **1**.

### Fixed processing (pin exactly)

- Read the raw file and find the events on `STI 014`; select the left-auditory trigger
  (code `1`).
- Analyse the **EEG** channels only. Exclude the channel the recording marks as bad
  (`info['bads']`); apply the SSP projectors that ship with the recording.
- Set an **average reference** over the EEG channels.
- Epoch from **-0.2 to 0.5 s** around stimulus onset and average the epochs to form the
  left-auditory evoked response.
- Compute the **Global Field Power** (the standard deviation across the EEG electrodes at
  each time point) and take its **peak value in the 80-120 ms window**.
- Report that value in **microvolts**.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `n1.json` — at minimum `{"n100_gfp_amplitude_uv": <float>, "condition": "left auditory",
  "window_ms": [80, 120], "reference": "average", "n_epochs": <int>}`.
- `run_metadata.json` — dataset id, file, condition, number of epochs, channels,
  reference, epoch window, and the measurement window you used.
- `findings.md` — a few sentences reporting the auditory N100 GFP amplitude. State only
  what your analysis supports.

## Failure handling

If the sample dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `run_metadata.json`, `n1.json`, and
`findings.md`.
