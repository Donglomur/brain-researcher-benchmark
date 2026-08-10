# Predicting brain maturity from functional connectivity (RANGE-001)

## Scientific context

Functional connectivity changes with development, and a "brain maturity" index can be built by training
a model to **predict a person's age** from their connectome. The cross-validated accuracy of that model
is reported as how well connectivity tracks brain maturation.

## Task

Using the nilearn ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`), form each subject's
functional connectivity over the Craddock-200 parcellation and train a cross-validated model to
**predict age** (`AGE_AT_SCAN`) from connectivity.

Report, in plain terms, **how well connectivity predicts age (tracks brain maturation)**.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series) with `AGE_AT_SCAN` in the phenotypic
table. Downloaded programmatically at runtime — **internet access is
required** on the first run (cached afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `maturity.json` — the number of subjects and how well connectivity predicts age (the accuracy your
 analysis supports).
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how well connectivity predicts age / tracks maturation.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `maturity.json`, and `findings.md`.
