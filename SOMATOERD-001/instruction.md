# Contralateral sensorimotor beta ERD to median-nerve stimulation (SOMATOERD-001)

## Scientific context

Brief electrical stimulation of the median nerve elicits, over the **contralateral
sensorimotor cortex**, a transient drop in ongoing **beta-band (~15-30 Hz)** power -- an
**event-related desynchronization (ERD)** -- shortly after the stimulus, before the
well-known later beta rebound. The ERD is quantified as the change in beta power relative
to a pre-stimulus baseline. This task uses the MNE **somato** dataset (single subject,
whole-head Elekta/Neuromag MEG, repeated median-nerve stimulation).

## Task

Using the MNE **somato** dataset, **compute the beta-band (15-30 Hz) event-related
desynchronization over the contralateral sensorimotor cortex** and report its magnitude
as the **percent change in beta power relative to the pre-stimulus baseline**, following
the fixed processing below.

### Data

Fetch the dataset with `mne.datasets.somato.data_path()` (downloads automatically, no
credentials). Use subject `sub-01`, file
`sub-01/meg/sub-01_task-somato_meg.fif`. The stimulation events are on the `STI 014`
trigger channel (a single event code marks each median-nerve stimulus). Analyse the
**gradiometer** channels.

### Fixed processing (pin exactly)

- Read the raw file and find the stimulation events on `STI 014`.
- Epoch the gradiometers from **-1.5 to 1.5 s** around each stimulus, with **no baseline
  correction at the epoching stage** and no additional filtering.
- Restrict the readout to the **contralateral sensorimotor gradiometers**
  **`MEG 1342`, `MEG 1343`, `MEG 1332`, `MEG 1333`**.
- Compute a **Morlet-wavelet** time-frequency representation over **15-30 Hz** on a
  **1 Hz** grid with **n_cycles = frequency / 2**.
- Express power as **percent change relative to the `-1.0` to `-0.25` s baseline**
  (percent baseline normalisation).
- Average the resulting percent values over the four channels, over the **15-30 Hz** band,
  and over the **0.10 to 0.35 s** post-stimulus window.
- Report that single number (a percentage; an ERD is a power decrease).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `erd.json` — at minimum `{"beta_erd_percent": <float>, "band_hz": [15, 30],
  "channels": ["MEG 1342", "MEG 1343", "MEG 1332", "MEG 1333"], "window_ms": [100, 350],
  "n_trials": <int>}`.
- `run_metadata.json` — dataset id, number of trials, the channels, time-frequency method,
  baseline, band, and measurement window you used.
- `findings.md` — a few sentences reporting the contralateral sensorimotor beta ERD
  magnitude. State only what your analysis supports.

## Failure handling

If the somato dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `run_metadata.json`, `erd.json`, and
`findings.md`.
