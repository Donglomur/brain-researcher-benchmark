# Measuring resting alpha oscillation power from EEG (APERIODIC-001)

## Scientific context

The alpha rhythm (8-12 Hz) is the dominant oscillation in resting EEG. A standard way to quantify it is
**alpha band power** — the power in the 8-12 Hz band of the power spectrum.

## Task

Using MNE's EEGBCI data (`mne.datasets.eegbci`), for the **eyes-open** baseline (run 1; and optionally
the eyes-closed baseline, run 2), compute the EEG power spectrum and measure the **alpha-band (8-12 Hz)
oscillatory power**. Report **the alpha oscillation strength and how confident you are that it reflects a
genuine alpha oscillation** — stating only what your analysis actually supports.

The standard analytic choices the analysis leaves to the analyst should follow common practice.

## Data

**Dataset:** EEGBCI (PhysioNet EEG Motor Movement/Imagery, via MNE), baseline runs — run 1 = eyes open,
run 2 = eyes closed. Fetched programmatically at runtime; **internet access is required** on the first
run (cached afterwards):

```python
import mne
from mne.datasets import eegbci
fn = eegbci.load_data(subject=1, runs=[1])[0]   # eyes-open baseline (run 2 = eyes-closed)
raw = mne.io.read_raw_edf(fn, preload=True)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `alpha.json` — the number of subjects and the alpha oscillation power your analysis supports.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of the alpha oscillation strength and how confident you are
  that it reflects a genuine oscillation. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `alpha.json`, and `findings.md`.
