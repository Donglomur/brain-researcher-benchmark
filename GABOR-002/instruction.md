# Voxel-wise visual-encoding (Gabor receptive-field) model of a stimulus-response cohort

## Task
`/app/data/` holds a cohort of visual-encoding experiments (`sub-01` … `sub-08`). Each subject
viewed a large set of stimuli whose **Gabor-wavelet pyramid features are precomputed and
shipped**; for every voxel the stimulus-evoked response is a regularised linear receptive field
over those features. Fit that receptive field per voxel from the **training** stimuli and use it
to **predict the responses to a held-out set of TEST stimuli**.

The cohort is **heterogeneous**: each subject's sidecar declares how its training responses are
represented and what files it provides, and you must adapt the analysis per subject — a pipeline
that assumes one fixed recipe will not fit them all.

Grading is **outcome-based**: for each subject your predicted test responses are recomputed and
compared against a held-out reference fit. Partial cohorts and partial voxel sets are scored
proportionally, so produce the best prediction you can for every voxel you can support.

## Shared model and output contract (`/app/data/protocol.json`)
A single JSON with the model and conventions common to all subjects: the **encoding model**
(per-voxel regularised linear receptive field over the shipped feature vector), the exact
**response representation** rules (`betas` vs `timeseries`, including the HRF-deconvolution recipe
for the time-course subjects), the **canonical HRF** samples to use, the **fittable-voxel /
exclusion** convention, the **grading metric** (predictions are scored by their *correlation*
across the test stimuli, so any global gain, offset, or regularisation strength cancels — only
the receptive-field direction is graded), and the exact **output spec**. Read it before you start.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `n_vox`, `n_train`, `n_test`, `n_features`, `response_kind`, and the file
  names for the features, the training responses, and (for a time-course subject) the onsets.
- `features_train.npy` — float32 `(n_train, n_features)`: the Gabor-pyramid features of the
  training stimuli (already compressively normalised and column-standardised; use directly).
- `features_test.npy` — float32 `(n_test, n_features)`: the features of the held-out test stimuli.
- the **training responses**, in one of two forms declared by `response_kind`:
  - `betas` → `resp_train.npy`, float32 `(n_train, n_vox)`: per-stimulus response amplitudes,
    ready to regress against `features_train`.
  - `timeseries` → `ts_train.npy`, float32 `(n_TR, n_vox)`: the detrended BOLD time-course, plus
    `onsets.npy`, int `(n_train,)`: the TR index at which each training stimulus was presented
    (same order as `features_train`). Recover the per-stimulus amplitudes as the protocol
    describes before fitting the receptive field.

## Required outputs (`/app/output/sub-XX/`)
Write one float32 `pred.npy` per subject, of shape `(n_test, n_vox)`: the predicted response of
every voxel to each test stimulus, in the subject's stimulus and voxel order. For a voxel whose
receptive field your fit cannot reliably determine, write **NaN** down its entire test column —
that column is scored as excluded rather than predicted.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write a valid `pred.npy` for the
subjects you can handle so the rest of the cohort can be graded.
