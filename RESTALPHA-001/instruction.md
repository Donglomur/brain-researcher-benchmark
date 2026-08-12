# Resting-state EEG alpha: quantifying the alpha oscillation (RESTALPHA-001)

## Scientific context

The alpha rhythm (8-12 Hz) is the dominant oscillation of the resting human EEG — described by
Berger in 1929 and, ever since, one of the most-studied signatures of the resting brain. The
standard way to quantify it is **alpha band power**: the power in the 8-12 Hz band of the resting
power spectrum, routinely read off as the strength of the alpha oscillation (Klimesch, 1999,
*Brain Research Reviews*, https://doi.org/10.1016/S0165-0173(98)00056-3). Alpha band power is the
headline object of these analyses — larger 8-12 Hz power is taken to mean a stronger alpha rhythm.

## Task

Using the provided EEGBCI resting power spectra (`data/eegbci_psd.npz`; the PhysioNet EEG Motor
Movement/Imagery database, baseline runs), for the **eyes-open** baseline (run 1 — and, for context,
the **eyes-closed** baseline, run 2), **characterise the resting alpha oscillation strength** from the
power spectrum.

For each subject (subjects 1-20), take the resting power spectral density, average the spectrum across
the EEG channels, and measure the **alpha-band (8-12 Hz) power** — the mean power over the 8-12 Hz
band. Summarise the alpha oscillation strength across subjects (and, using run 2, the eyes-open vs
eyes-closed contrast).

Standard implementation choices the analysis leaves to the analyst (channel selection, how you
summarise the band, how you characterise the spectrum) should follow common practice; the brief does
not spell them out.

Summarise your characterisation of the resting alpha oscillation strength in `findings.md`, stating
only what your analysis actually supports.

## Data

**Dataset:** EEGBCI (PhysioNet EEG Motor Movement/Imagery, via MNE), baseline runs — run 1 = eyes
open, run 2 = eyes closed. Provided in the container at `data/eegbci_psd.npz` (no download; **no
network needed**). It holds the per-channel resting power spectral density (MNE Welch, 2 s windows,
1-45 Hz, linear power V²/Hz) for subjects 1-20 in both baseline states:

```python
import numpy as np
d = np.load("data/eegbci_psd.npz", allow_pickle=True)
psd_eo = d["psd_eo"]   # (subjects x channels x freqs)  eyes-open   (run 1)
psd_ec = d["psd_ec"]   # (subjects x channels x freqs)  eyes-closed (run 2)
freqs  = d["freqs"]    # frequency axis (Hz)
chans  = d["ch_names"] # channel names (standard 10-20)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `alpha.json` — the number of subjects and the alpha (8-12 Hz band) power, plus any spectral
  quantities your characterisation relies on.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of the resting alpha oscillation strength. State only what
  your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `alpha.json`, and `findings.md`.
