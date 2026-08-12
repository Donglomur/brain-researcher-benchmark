# Reproducing the "dynamic functional connectivity" result (DYNCONN-001)

## Scientific context

Resting-state functional connectivity is not static. Using **sliding-window** analysis,
Allen et al. (2014, *Cerebral Cortex*, https://doi.org/10.1093/cercor/bhs352; see also
Hutchison et al., 2013, *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2013.05.079)
reported that inter-regional coupling **fluctuates substantially over time** and recurs into
a small set of reproducible **"dynamic connectivity states."** This time-varying connectivity
is one of the most-cited features of resting-state brain organisation, widely taken as
evidence that the connectome reconfigures dynamically at rest.

## Task

Using the provided ABIDE Dosenbach-160 ROI timeseries bundle (`${BUNDLE_DIR}/dos160_dynfc.npz`,
default `/opt/bundle`; ~60 subjects; **no download, no network needed**), **reproduce this
dynamic-connectivity result and report whether it holds on these data.**

For each subject, take the Dosenbach-160 ROI time series and z-score each ROI over time. Compute
**sliding-window functional connectivity**: slide a **30-TR** window in steps of **4 TR**, and in
each window form the ROI×ROI correlation matrix. Quantify the *amount of time-varying
connectivity* as the **standard deviation of each edge across windows**, summarised as the **mean
edge standard deviation over windows** — the magnitude of window-to-window fluctuation that the
"dynamic connectivity" literature reports. Report this at the **30-TR** window, and also at
**22-TR** and **44-TR** windows.

Report, in plain terms, **whether the dynamic-connectivity result reproduces on these data** —
stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state Dosenbach-160 ROI time series (`cpac`, **band-pass filtered**, no
global-signal regression), provided **in the container** at `${BUNDLE_DIR}/dos160_dynfc.npz`
(default `/opt/bundle`). Load it locally — **no network access is available or needed** (the data
is already present):

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "dos160_dynfc.npz"),
            allow_pickle=True)
ts = d["ts"]                       # object array of ~60 subjects, each (T x 160) float16 ROI series
atlas = d["atlas"]                 # "Dosenbach-160"
preprocessing = d["preprocessing"] # provenance string (cpac filt_noglobal)
```

Each subject is a `T × 160` `float16` array of per-ROI BOLD time series (variable length `T` per
subject) for the **Dosenbach-160** atlas. The time series come from the ABIDE `cpac` `filt_noglobal`
derivative: they are **band-pass filtered** and have **no global-signal regression** applied. Use
them as provided (z-score each ROI over time before computing the windowed correlations). Do not
substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `dynamics.json` — the sliding-window connectivity variability (the **mean edge standard
  deviation across windows**) at each window length (**22, 30, 44 TR**), the primary window
  length, and `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects, window length(s), step, and the
  analytic choices you made.
- `findings.md` — a short written summary stating whether the dynamic-connectivity result
  reproduces on these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `dynamics.json`, and `findings.md`.
