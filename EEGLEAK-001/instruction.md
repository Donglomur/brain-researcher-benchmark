# Reproducing motor-imagery decoding from windowed EEG (EEGLEAK-001)

## Scientific context

Motor-imagery EEG (imagining left- vs right-hand movement) is decodable single-trial with
spatial filters — **common spatial patterns (CSP)** followed by a linear classifier (Ramoser,
Müller-Gerking & Pfurtscheller, 2000, *IEEE Transactions on Rehabilitation Engineering*,
"Optimal spatial filtering of single trial EEG during imagined hand movement",
https://doi.org/10.1109/86.895946), the standard brain–computer-interface pipeline that reports
high left-vs-right classification accuracy. To increase the number of training samples, a common
practice is to cut each trial into several shorter, overlapping time windows and treat each
window as a sample.

## Task

Using MNE's EEGBCI motor-imagery data (`mne.datasets.eegbci`, runs 4/8/12 = left- vs right-fist
imagery, subjects 1–9), **reproduce this decoding result and report whether it holds on these
data.** Band-pass 7–30 Hz, epoch each trial (left vs right fist), cut each trial into
overlapping **~1.5 s windows** (e.g. 0.75 s step) to form the samples, train a **CSP + LDA**
decoder to classify left vs right, and **report its cross-validated accuracy**.

Concretely, per subject: load and concatenate the three runs, standardize the montage, filter
7–30 Hz, build epochs (e.g. `tmin≈0.5`, `tmax≈3.5`), slice each epoch into the overlapping
windows, fit `mne.decoding.CSP` + `LinearDiscriminantAnalysis`, and cross-validate. The standard
choices the analysis leaves to the analyst (montage standardization, epoch time limits,
band-pass filter design, number of CSP components) should follow common practice.

Report, in plain terms, **whether the reported motor-imagery decoding accuracy holds on these
data** — stating only what your analysis actually supports.

## Data

**Dataset:** EEGBCI motor-imagery (PhysioNet EEG Motor Movement/Imagery, via MNE), fetched
programmatically at runtime; **internet access is required** on the first run (cached
afterwards):

```python
import mne
from mne.datasets import eegbci
fns = eegbci.load_data(subject=1, runs=[4, 8, 12], update_path=True)  # per subject
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `decoding.json` — the number of subjects and the cross-validated decoding accuracy.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of the decoding accuracy (whether the reported
  decodability holds on these data). State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `decoding.json`, and `findings.md`.
