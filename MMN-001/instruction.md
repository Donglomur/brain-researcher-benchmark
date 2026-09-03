# The mismatch negativity at FCz (MMN-001)

## Scientific context

The **mismatch negativity (MMN)** is a frontocentral negative ERP component elicited by
rare "deviant" stimuli embedded in a stream of repeated "standard" stimuli, maximal at
frontocentral sites such as **FCz**. In the ERP CORE passive auditory oddball paradigm
(Kappenman, Farrens, Zhang, Stewart & Luck, 2021, *NeuroImage*,
https://doi.org/10.1016/j.neuroimage.2020.117465), 80 dB standard tones are occasionally
replaced by 70 dB deviant tones while the participant ignores the sounds, and the
canonical readout is the **deviant-minus-standard difference wave** and its amplitude in
the MMN window.

## Task

Using the ERP CORE **MMN** continuous EEG recordings for **subjects 1-12**, **compute the
deviant-minus-standard MMN difference-wave amplitude at electrode FCz in the 125-225 ms
window** and report it (microvolts), following the fixed processing below.

### Data (ERP CORE MMN, downsampled continuous EEGLAB files, subjects 1-12)

Each subject has a `<n>_MMN_ds.set` header and a matching `.fdt` data file that must sit
in the same directory. Download both files for each subject from OSF at
`https://osf.io/download/<id>/`:

```
subj   .set id                         .fdt id
1      5f16b7d60870f2014a09c21d        5f16b7d20596f6013e79b7dd
2      5f16c1690870f201560975ee        5f16c1660596f6013e79cda9
3      5f16c9be6ef440015ebc9cad        5f16c9ba6ef440015abc9e9c
4      5f16d2340870f2014b09c930        5f16d2306ef440015fbcb7c5
5      5f16d3bb6ef440015ebcae7a        5f16d3b80870f2015609a28f
6      5f16d4760596f6014a79a61b        5f16d4716ef440015fbcbd57
7      5f16d5376ef440015bbcb161        5f16d5330596f6014a79a7bb
8      5f16d5e16ef440015fbcc08c        5f16d5de6ef440015bbcb220
9      5f16d6a90596f6013e79e575        5f16d6a56ef440015fbcc2c8
10     5f16b8ab6ef4400155bca647        5f16b8a60870f2014709b1ba
11     5f16b9836ef4400155bca8ca        5f16b9800870f2014b09ae65
12     5f16ba576ef4400155bcaaff        5f16ba546ef4400155bcaaf4
```

Save each pair as `<n>_MMN_ds.set` / `<n>_MMN_ds.fdt` (the `.set` references the `.fdt` by
name). Read with `mne.io.read_raw_eeglab`.

### Event codes (ERP CORE MMN passive auditory oddball scheme)

Stimulus event codes: **80** = standard (80 dB tone), **70** = deviant (70 dB tone). Code
**180** marks the first stream of 15 standards at the very start (not part of the standard
bin). Read events with `mne.events_from_annotations`.

### Fixed processing (pin exactly)

- Mark `HEOG_left`, `HEOG_right`, `VEOG_lower` as EOG; the other 30 channels are scalp EEG.
- Band-pass filter the EEG **0.1-30 Hz**.
- Re-reference the EEG to the **average of the mastoid-adjacent electrodes P9 and P10**.
- Take the **standard** condition as event code **80** and the **deviant** condition as
  event code **70**.
- Epoch **-200 to 800 ms** around stimulus onset, apply a **-200 to 0 ms baseline**, and
  **average all epochs** of each condition (no additional peak-to-peak artifact
  rejection).
- Form the **deviant-minus-standard** difference wave (average of deviant minus average of
  standard), per subject.
- Measure the MMN as the **amplitude of the FCz deviant-minus-standard difference wave over
  the 125-225 ms window**, per subject.
- Report the **mean across the 12 subjects** of that per-subject amplitude.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `mmn.json` — at minimum `{"mmn_amplitude_uv": <float>, "channel": "FCz",
  "window_ms": [125, 225], "n_subjects": <int>}`.
- `run_metadata.json` — dataset id, n subjects, the reference and filter you used, the
  baseline and measurement window, and the standard/deviant code definition.
- `findings.md` — a few sentences reporting the deviant-minus-standard MMN amplitude at
  FCz. State only what your analysis supports.

## Failure handling

If the ERP CORE MMN files cannot be resolved, exit non-zero with `failed_precondition`
and a non-empty reason, and still write parseable `run_metadata.json`, `mmn.json`, and
`findings.md`.
