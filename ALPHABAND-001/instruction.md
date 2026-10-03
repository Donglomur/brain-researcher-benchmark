# The Berger effect: occipital alpha power, eyes-closed vs eyes-open (ALPHABAND-001)

## Scientific context

Berger's historical observation motivates comparing posterior **alpha-band
(8–13 Hz)** activity with eyes closed and open (Berger, 1929). Here the
eyes-closed/eyes-open **occipital alpha power ratio** summarizes that contrast.

## Task

Using the PhysioNet **EEG Motor Movement/Imagery** dataset, assess the Berger effect
in this modern sample and report its magnitude.
For each of **subjects 1–5**, load **run 1 (eyes open)** and **run 2 (eyes closed)**
— the two ~1-minute baseline resting recordings. From the **occipital** EEG channels,
compute alpha-band power by Welch's method, and form, per subject, the ratio of
**eyes-closed to eyes-open** occipital alpha power. Report the **mean of this ratio
across the five subjects** as the headline occipital alpha power ratio.

Pin the analysis so the number reproduces: band **8–13 Hz**, Welch power spectral
density, common-average reference, and the mean-of-per-subject-ratios aggregation above.
For an auditable numerical comparison, standardize EDF channel names and use O1, Oz,
O2. Use the full recordings, common-average reference over all 64 EEG channels,
and 2-second Welch segments (320 samples at 160 Hz), FFT length 320, periodic Hamming
window, zero overlap, per-segment DC removal, and arithmetic mean across segments.
Do not add temporal filtering, ICA, or custom artifact rejection. Average the PSD
density over the frequency bins from 8 through 13 Hz inclusive, then over O1/Oz/O2.
Report this value in V²/Hz (not its integral). This is a modern five-subject
qualitative replication, not a numerical reproduction of Berger's original cohort.

### Available data

The image contains the ten original EDF+ recordings from
[PhysioNet EEGMMIDB v1.0.0](https://physionet.org/content/eegmmidb/1.0.0/) at
`${EEGBCI_DATA_DIR}` (default `/app/data/eegmmidb`), named
`S001/S001R01.edf` through `S005/S005R02.edf` (runs 01 and 02 only).
`data_manifest.json` records their versioned URLs, license and official SHA-256
checksums. Run 01 is eyes open; run 02 is eyes closed. Work entirely offline:
read these files directly (e.g. `mne.io.read_raw_edf`), not a runtime dataset fetch.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `alpha_ratio.json` — the headline result as
  `{"occipital_alpha_ratio_ec_over_eo": <float>, "band_hz": [8, 13],
  "n_subjects": 5, "channels": [<occipital channel names used>]}`. Also report, for
  contrast, `wholehead_alpha_ratio_for_reference`: use the same PSD recipe and mean
  of per-subject EC/EO ratios, changing only the spatial average to all 64 EEG channels.
- `per_subject.csv` — one row per subject (real subject ids):
  `subject, ec_occipital_alpha, eo_occipital_alpha, ratio`. The per-subject `ratio` is the
  eyes-closed/eyes-open OCCIPITAL alpha power ratio; its mean across subjects is the reported
  headline `occipital_alpha_ratio_ec_over_eo`.
- `run_metadata.json` — dataset id/version, subjects, runs, band, PSD settings,
  reference, power units, aggregation, and the occipital channels used. Include
  `dataset_version: "1.0.0"`, `power_units: "V^2/Hz"`,
  `aggregation: "mean_of_subject_ratios"`, and
  `welch: {"segment_sec": 2, "n_fft": 320, "n_overlap": 0,
  "window": "hamming", "remove_dc": true, "average": "mean"}`.
- `findings.md` — a short written summary (a few sentences) stating the occipital
  alpha power ratio (eyes-closed vs eyes-open) you measured and what it means. State
  only what your analysis actually supports.

### Metadata field schema

Use these exact top-level names in `run_metadata.json`; additional honest fields
are welcome. This example declares the required settings, not computed results:

```json
{
  "dataset_id": "PhysioNet EEGMMIDB",
  "dataset_version": "1.0.0",
  "subjects": [1, 2, 3, 4, 5],
  "runs": {"eyes_open": 1, "eyes_closed": 2},
  "band_hz": [8, 13],
  "channels": ["O1", "Oz", "O2"],
  "reference": "common_average",
  "power_units": "V^2/Hz",
  "aggregation": "mean_of_subject_ratios",
  "welch": {
    "segment_sec": 2, "n_fft": 320, "n_overlap": 0,
    "window": "hamming", "remove_dc": true, "average": "mean"
  }
}
```

Dataset-name aliases identifying EEGBCI/EEGMMIDB, equivalent subject-ID spellings,
channel-name capitalization, `reference: "CAR"`, and equivalent `V²/Hz` or
`V2/Hz` unit typography are accepted. `welch.window` may also be
`"periodic_hamming"` or `"periodic hamming"`; all refer to the prescribed periodic
window. No additional `psd_method` key is required: the `welch` object carries the
method contract. Optional implementation descriptions cannot replace any required
setting. All per-subject, group and whole-head numerical checks still apply.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write a parseable `run_metadata.json`, `alpha_ratio.json`,
and `findings.md`.
