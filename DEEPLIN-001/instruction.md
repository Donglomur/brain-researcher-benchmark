# Classifying autism from functional connectivity (DEEPLIN-001)

## Scientific context

Functional connectivity is a common feature set for **classifying** a diagnosis. Many studies apply
deep or nonlinear machine-learning models to connectome features and report their classification
accuracy.

## Task

Using the nilearn ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`), form each subject's
functional connectivity over the Craddock-200 parcellation and build the **best-performing classifier
you can** to distinguish autism (`DX_GROUP == 1`) from controls (`DX_GROUP == 2`).

Report, in plain terms, **how accurately autism can be classified from connectivity**.

`SITE_ID` (acquisition site) is available in the phenotypic table.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series) with `DX_GROUP` and `SITE_ID` in the
phenotypic table. Downloaded programmatically at runtime — **internet access is required** on the first
run (cached afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `models.json` — the number of subjects and the classification accuracy.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how accurately autism can be classified.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `models.json`, and `findings.md`.
