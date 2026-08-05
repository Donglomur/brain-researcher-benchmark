# EEG functional connectivity in the alpha band (EEGVC-001)

## Scientific context

EEG **functional connectivity** — synchronisation between scalp electrodes — is a standard
measure of large-scale neural coordination. **Coherence** in the **alpha band (8–13 Hz)** is
one of the most widely used EEG connectivity measures (Nunez et al., 1997,
*Electroencephalogr Clin Neurophysiol*, https://doi.org/10.1016/S0013-4694(97)00066-7), and
identifying the strongly connected electrode pairs is a common analysis goal in EEG.

## Task

Using the PhysioNet **EEG Motor Movement/Imagery** dataset via MNE
(`mne.datasets.eegbci.load_data(subject=1, runs=[6, 10, 14])`, read the first run with
`mne.io.read_raw_edf`), set an **average reference**, band-pass to a sensible range, and
compute the **alpha-band (8–13 Hz) coherence** between the 64 electrodes. **Identify the
strongly connected electrode pairs** and report the connectivity.

The standard analytic choices the analysis leaves to the analyst (window length, exact band,
connectivity estimator) should follow common practice.

Report, in plain terms, **the dominant alpha-band functional connectivity on these data** —
stating only what your analysis actually supports.

## Data

**Dataset:** PhysioNet EEG Motor Movement/Imagery (eegbci). It is downloaded programmatically at runtime by the loader used in the Task section — nothing is pre-placed in the container, so **internet access is required** on the first run (the download is cached locally afterwards). Fetch it with:

```python
mne.datasets.eegbci.load_data(subject=1, runs=[6, 10, 14])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity.json` — the `top_connections` (each an electrode pair with its coherence
  value), the `mean_coherence` over all pairs, and `n_channels`.
- `run_metadata.json` — dataset, number of channels, reference, band, and the analytic choices.
- `findings.md` — a short written summary of the dominant alpha-band connectivity and how
  confident you are in it. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `connectivity.json`, and `findings.md`.
