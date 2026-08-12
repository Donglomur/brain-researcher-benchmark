# Reproducing motor-imagery decoding from windowed EEG (MOTORIMG-001)

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

Using the provided EEGBCI motor-imagery epochs (PhysioNet EEG Motor Movement/Imagery, runs
4/8/12 = left- vs right-fist imagery, subjects 1–9), **reproduce this decoding result and report
whether it holds on these data.** Cut each trial into overlapping **~1.5 s windows** (e.g. 0.75 s
step) to form the samples, train a **CSP + LDA** decoder to classify left vs right, and **report
its cross-validated accuracy**.

Concretely, per subject: take that subject's trials, slice each trial into the overlapping
windows, fit `mne.decoding.CSP` + `LinearDiscriminantAnalysis`, and cross-validate. The standard
choices the analysis leaves to the analyst (window length/step, number of CSP components,
cross-validation scheme) should follow common practice.

Report, in plain terms, **whether the reported motor-imagery decoding accuracy holds on these
data** — stating only what your analysis actually supports.

## Data

**Dataset:** EEGBCI motor-imagery epochs, provided **in the container** at
`${BUNDLE_DIR}/eegbci_epochs.npz` (default `/opt/bundle`) — already present, **no download and no
network is available or needed**. It holds the left/right-fist trials already band-passed
(7–30 Hz), montage-standardized, resampled to 80 Hz, and epoched (0.5–3.5 s):

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "eegbci_epochs.npz"))
X       = d["X"]        # (n_trials, 64, 241) float — band-passed, epoched trials
y       = d["y"]        # (n_trials,)  0 = left fist, 1 = right fist
subject = d["subject"]  # (n_trials,)  subject id (1..9)
run      = d["run"]     # (n_trials,)  the run the trial was recorded in (4, 8 or 12)
trial    = d["trial"]   # (n_trials,)  unique trial id
sfreq   = float(d["sfreq"])   # 80.0 Hz
```

Each subject was recorded in three separate runs (4/8/12); `run` and `trial` label which run and
which trial each row belongs to. Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `decoding.json` — the number of subjects and the cross-validated decoding accuracy (the
  classifier and windowing you used, and any per-subject or cross-validation detail you computed).
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of the decoding accuracy (whether the reported
  decodability holds on these data). State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `decoding.json`, and `findings.md`.
