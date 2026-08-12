# Reproducing post-stroke functional "disconnection" (STROKECONN-001)

## Scientific context

Resting-state functional connectivity (FC) is a standard tool for mapping "disconnection"
after stroke. Carter et al. (2010, *Annals of Neurology*, https://doi.org/10.1002/ana.21905,
"Resting interhemispheric functional magnetic resonance imaging connectivity predicts
performance after stroke"; see also He et al., 2007, *Neuron*) showed that a focal lesion has
remote effects on distant regions: the resulting **reduction in resting-state FC** tracks
behavioural impairment, and regions whose FC with the rest of the brain is reduced are
interpreted as **functionally disconnected** by the injury. Mapping the most-disconnected
regions from reduced resting-state connectivity is one of the standard readouts of the
post-stroke connectome.

## Task

Using the provided post-stroke resting-state ROI time series (`data/stroke_timeseries.npz`),
**reproduce this disconnection mapping and report whether it holds on these data** — that is,
compute each patient's resting-state functional connectivity and **identify the brain regions
of lowest connectivity ("disconnection")**.

For each patient, z-score each ROI time series and form the **ROI×ROI Pearson correlation
matrix** over the **Harvard-Oxford 48-region cortical atlas**. Summarise each region's
connectivity as its **mean correlation with all other regions** (connectivity strength), and
take the regions of **lowest connectivity strength** — pooled across patients — as the
candidate "disconnected" regions. The standard preprocessing choices the analysis leaves to
the analyst (nuisance regression, signal normalisation) should follow common practice.

Report, in plain terms, **which regions are most disconnected and whether the FC-disconnection
result reproduces on these data** — stating only what your analysis actually supports.

## Data

**Dataset:** resting-state ROI time series for post-stroke patients (OpenNeuro **ds003999**,
baseline/`ses-pre` scan), provided analysis-ready in `data/stroke_timeseries.npz`: one array
per subject (`sub-*`), each **timepoints × 48** over the Harvard-Oxford cortical atlas, plus
`tr` (= 3 s).

```python
import numpy as np
d = np.load("data/stroke_timeseries.npz", allow_pickle=True)
subs = [k for k in d.files if k.startswith("sub-")]
ts = d[subs[0]]        # timepoints x 48 ROI time series
tr = float(d["tr"])    # 3.0 s
```

Provenance: derived from the raw OpenNeuro ds003999 resting-state BOLD by the pipeline in
`data/build_worker.py` (dipy MNI affine registration + Harvard-Oxford parcellation + CompCor).
Do not substitute a different dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity.json` — the number of subjects and a summary of the lowest-connectivity /
  "disconnected" regions.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary stating which regions are most disconnected and
  whether the FC-disconnection result reproduces on these data. State only what your analysis
  actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `connectivity.json`, and `findings.md`.
