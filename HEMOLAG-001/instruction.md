# Regions of reduced connectivity after stroke (HEMOLAG-001)

## Scientific context

Resting-state functional connectivity (FC) is widely used to map "disconnection" after stroke — regions
whose FC with the rest of the brain is reduced are interpreted as functionally disconnected by the
injury.

## Task

Using the provided post-stroke resting-state ROI time series (`data/stroke_timeseries.npz`), compute
functional connectivity for each patient and **identify the brain regions with the lowest connectivity
("disconnection")**. Report **which regions are most disconnected**.

## Data

**Dataset:** resting-state ROI time series for post-stroke patients (OpenNeuro **ds003999**,
baseline/`ses-pre` scan), provided analysis-ready in `data/stroke_timeseries.npz`: one array per subject
(`sub-*`), each **timepoints × 48** over the Harvard-Oxford cortical atlas, plus `tr` (= 3 s).

```python
import numpy as np
d = np.load("data/stroke_timeseries.npz", allow_pickle=True)
subs = [k for k in d.files if k.startswith("sub-")]
ts = d[subs[0]] # timepoints x 48 ROI time series
tr = float(d["tr"]) # 3.0 s
```

Provenance: derived from the raw OpenNeuro ds003999 resting-state BOLD by the pipeline in
`data/build_worker.py` (dipy MNI affine registration + Harvard-Oxford parcellation + CompCor). Do not
substitute a different dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity.json` — the number of subjects and a summary of the lowest-connectivity /
 "disconnected" regions.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of which regions are most disconnected.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `connectivity.json`, and `findings.md`.
