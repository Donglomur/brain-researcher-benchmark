# Leakage-corrected source-space connectivity (orthogonalised AEC-c)

## Task
`/app/data/` holds a cohort of resting-state MEG exams (`sub-01` … `sub-08`) after source
reconstruction. Each subject is a set of band-limited (alpha) source time series, one per
cortical ROI. From these signals, estimate the **leakage-corrected amplitude-envelope
correlation** (orthogonalised AEC-c) between every pair of ROIs and write out the connectivity
matrix.

Spatial leakage in source reconstruction induces spurious zero-lag correlation between ROIs, so
the amplitude-envelope correlation must be computed on **leakage-orthogonalised** signals. The
cohort is **heterogeneous**: each subject's sidecar records the `inverse_method` used to
reconstruct its sources, and that dictates which leakage-correction scheme applies — a pipeline
that assumes one fixed recipe will not fit them all. **Provide a value for every ROI pair the
data determines; where a pair's leakage-corrected AEC-c is not determined, omit it (write NaN).**
There is no connectivity toolbox provided — implement the estimator yourself and get the
orthogonalisation, the envelope, and the per-subject scheme right.

Grading is **outcome-based and entrywise**: your matrix is recomputed from the signals by a
held-out reference and compared pair-by-pair. Partial cohorts and partial matrices are scored
proportionally, so produce every pair you can support and omit the rest.

## Shared conventions and output contract (`/app/data/protocol.json`)
A single JSON with the definitions common to all subjects: the exact **orthogonalised AEC-c**
for each scheme (`pairwise_definition`, `symmetric_definition`), the mapping from
`inverse_method` to scheme (`scheme_by_method`), the **envelope** convention (magnitude of the
discrete analytic / Hilbert signal), the **correlation** (Pearson), and the **output spec**.
Read it before you start. The AEC-c is convention-invariant: it is invariant to per-ROI sign
and positive scaling, so any correct factorisation of the symmetric orthogonaliser gives the
same values.

## Per subject (`/app/data/sub-XX/`)
- `sidecar.json` — `inverse_method` (`"MNE"` or `"LCMV"`), `n_roi`, `n_time`, `fs_hz`,
  `band_hz`, `roi_names`, and `data_file`.
- `roi_timeseries.npy` — a float32 array of shape `(n_roi, n_time)`: one real band-limited
  source time series per ROI, rows in the sidecar's `roi_names` order.

## Required output (`/app/output/sub-XX/`)
Write `aec.npy`: a float32 **`(n_roi, n_roi)` symmetric matrix** in the sidecar's roi order.
- Set the **diagonal to NaN**.
- Entry `(i, j)` = the leakage-corrected AEC-c between ROI `i` and ROI `j`, using the scheme
  dictated by this subject's `inverse_method`.
- Where a pair's AEC-c is **not determined** by the data, set both `(i, j)` and `(j, i)` to
  **NaN**.

## Failure handling
If a subject cannot be processed for an unexpected reason, still write a valid `aec.npy` for
the subjects you can produce so the rest of the cohort can be graded.
