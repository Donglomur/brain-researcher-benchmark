# Auditory M100 latency in the Brainstorm bst_auditory MEG recording (MEGAEF-001)

## Scientific context

A brief tone elicits, about 100 ms later, the **auditory M100** (the N100m/M100, the
magnetic counterpart of the EEG N100), a robust marker of auditory cortical processing. A
convenient sensor-level, reference-free summary of the evoked field at each time point is
the **Global Field Power (GFP)** — the spatial standard deviation across the MEG
magnetometers. The **latency** of the GFP peak in the M100 window indexes the timing of
this response. This task uses the Brainstorm **bst_auditory** dataset (a single-subject
CTF-MEG auditory oddball recording of standard and deviant tones).

## Task

Using the **bst_auditory** MEG recording, **compute the latency of the auditory M100 for
the standard tones** and report it as the **time of the peak magnetometer Global Field
Power (in milliseconds) in the 60-160 ms window, relative to the onset of the auditory
stimulus**, following the fixed processing below.

### Data

Fetch the dataset with
`mne.datasets.brainstorm.bst_auditory.data_path(accept=True)` (downloads automatically, no
credentials; the `accept=True` flag agrees to the dataset's license terms). Use **run 1**,
the file `MEG/bst_auditory/S01_AEF_20131218_01.ds`. The **standard tones** are marked on
the `UPPT001` stimulus channel with **trigger code 1** (the deviant tones are code 2; do
not analyse them here).

### Fixed processing (pin exactly)

- Read run 1 and identify the standard-tone events (`UPPT001` code `1`).
- Analyse the **MEG magnetometers** only.
- Epoch from **-0.1 to 0.4 s** around stimulus onset, apply a **pre-stimulus baseline**
  (the -100..0 ms interval), and average the standard-tone epochs to form the evoked
  response.
- Apply a **40 Hz low-pass** filter to the magnetometers.
- Compute the **Global Field Power** (the standard deviation across the magnetometers at
  each time point) and take the **latency of its peak in the 60-160 ms window**.
- Report that latency in **milliseconds**, relative to stimulus onset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `m100.json` — at minimum `{"m100_latency_ms": <float>, "condition": "standard tone",
  "window_ms": [60, 160], "measure": "peak Global Field Power (magnetometers)",
  "n_trials": <int>}`.
- `run_metadata.json` — dataset id, file, condition, number of trials, channels, measure,
  epoch window, baseline, low-pass, and the measurement window you used.
- `findings.md` — a few sentences reporting the auditory M100 latency. State only what your
  analysis supports.

## Failure handling

If the bst_auditory dataset cannot be resolved, exit non-zero with `failed_precondition`
and a non-empty reason, and still write parseable `run_metadata.json`, `m100.json`, and
`findings.md`.
