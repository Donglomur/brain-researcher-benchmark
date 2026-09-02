# The Berger effect: occipital alpha power, eyes-closed vs eyes-open (ALPHABAND-001)

## Scientific context

The oldest result in human electroencephalography is Berger's observation that
posterior **alpha-band (8–13 Hz)** activity is strongly enhanced when the eyes are
closed and suppressed when they are open (Berger, 1929). The effect is maximal over
the **occipital** cortex, and the eyes-closed/eyes-open **occipital alpha power ratio**
is the standard quantitative summary of it.

## Task

Using the PhysioNet **EEG Motor Movement/Imagery** dataset
(`mne.datasets.eegbci.load_data`), reproduce the Berger effect and report its magnitude.
For each of **subjects 1–5**, load **run 1 (eyes open)** and **run 2 (eyes closed)**
— the two ~1-minute baseline resting recordings. From the **occipital** EEG channels,
compute alpha-band power by Welch's method, and form, per subject, the ratio of
**eyes-closed to eyes-open** occipital alpha power. Report the **mean of this ratio
across the five subjects** as the headline occipital alpha power ratio.

Pin the analysis so the number reproduces: band **8–13 Hz**, Welch power spectral
density, common-average reference, and the mean-of-per-subject-ratios aggregation above.
Standard implementation choices the method leaves to the analyst (Welch segment length,
exact occipital electrode set) should follow common practice.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `alpha_ratio.json` — the headline result as
  `{"occipital_alpha_ratio_ec_over_eo": <float>, "band_hz": [8, 13],
  "n_subjects": 5, "channels": [<occipital channel names used>]}`.
- `per_subject.csv` — one row per subject:
  `subject, ec_occipital_alpha, eo_occipital_alpha, ratio`.
- `run_metadata.json` — dataset id, subjects, runs, band, PSD method, reference, and
  the occipital channels used.
- `findings.md` — a short written summary (a few sentences) stating the occipital
  alpha power ratio (eyes-closed vs eyes-open) you measured and what it means. State
  only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write a parseable `run_metadata.json`, `alpha_ratio.json`,
and `findings.md`.
