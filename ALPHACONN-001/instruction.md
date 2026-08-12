# Reproducing the alpha-band EEG functional-connectivity result (ALPHACONN-001)

## Scientific context

EEG **functional connectivity** — synchronisation between scalp electrodes — is a standard measure
of large-scale neural coordination, and **coherence in the alpha band (8–13 Hz)** is one of its most
widely used estimators (Nunez et al., 1997, *Electroencephalography and Clinical Neurophysiology*,
https://doi.org/10.1016/S0013-4694(97)00066-7). On this account alpha-band coherence indexes dense
large-scale cortical connectivity: many electrode pairs are strongly coherent, and those
strongly-coherent pairs mark the coordinated large-scale network. Identifying the strongly connected
electrode pairs is a routine EEG analysis goal.

## Task

Using the provided PhysioNet **EEG Motor Movement/Imagery** recording (`data/S001R06.edf`: one raw
64-channel EEG run, read with `mne.io.read_raw_edf`), **reproduce this dense alpha-band connectivity
result and report whether it holds on these data.**

Standardise the montage (`mne.datasets.eegbci.standardize`), set an **average reference**, band-pass
filter to a sensible broadband range (e.g. 1–40 Hz), and compute the **alpha-band (8–13 Hz)
coherence** between the 64 electrodes: estimate the cross-spectral density over ~2 s Hann-windowed
segments, average it across the 8–13 Hz band, and form the coherence for every electrode pair.
Report the **mean coherence** over all pairs and the **strongest electrode pairs**. The standard
preprocessing choices the analysis leaves to the analyst (filtering, windowing, segment length,
signal normalisation) should follow common practice.

Report, in plain terms, **whether the dense alpha-band connectivity result reproduces on these
data** — stating only what your analysis actually supports.

## Data

**Dataset:** PhysioNet EEG Motor Movement/Imagery (eegbci), provided in the container at
`data/S001R06.edf` (subject 1, run 6, 64 channels, 160 Hz; the untouched PhysioNet EDF). **No
download and no network are needed** — read it directly:

```python
import mne
raw = mne.io.read_raw_edf("data/S001R06.edf", preload=True)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity.json` — the `top_connections` (each an electrode pair with its coherence value), the
  `mean_coherence` over all pairs, and `n_channels`.
- `run_metadata.json` — dataset, number of channels, reference, band, and the analytic choices you
  made.
- `findings.md` — a short written summary stating whether the dense alpha-band connectivity result
  reproduces on these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `connectivity.json`, and `findings.md`.
