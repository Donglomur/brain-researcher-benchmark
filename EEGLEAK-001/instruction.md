# Decoding motor imagery from windowed EEG (EEGLEAK-001)

## Scientific context

Motor-imagery EEG (imagining left- vs right-hand movement) can be decoded with spatial filters such as
CSP followed by a linear classifier. To increase the number of training samples, a common practice is
to cut each trial into several shorter, overlapping time windows and treat each window as a sample.

## Task

Using MNE's EEGBCI motor-imagery data (`mne.datasets.eegbci`, runs 4/8/12 = left- vs right-fist
imagery), band-pass 7–30 Hz, epoch each trial, and cut each trial into overlapping ~1.5 s windows to
form the samples. Train a decoder to classify left vs right and **report its
cross-validated accuracy**.

## Data

**Dataset:** EEGBCI motor-imagery (PhysioNet EEG Motor Movement/Imagery, via MNE), fetched
programmatically at runtime; **internet access is required** on the first run (cached afterwards):

```python
import mne
from mne.datasets import eegbci
fns = eegbci.load_data(subject=1, runs=[4, 8, 12], update_path=True) # per subject
```

Keep the trial/run structure (which window came from which trial and run) available to your analysis.
Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `decoding.json` — the number of subjects and the cross-validated decoding accuracy your analysis
 supports.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of the decoding accuracy.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `decoding.json`, and `findings.md`.
