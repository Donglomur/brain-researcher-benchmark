# Predicting sex from functional connectivity (BASERATE-001)

## Scientific context

Functional connectivity is widely used as a set of features for **classification** — for example,
predicting a phenotype or diagnostic label from a subject's connectome. A standard workflow trains a
classifier with cross-validation and reports its accuracy.

## Task

Using the nilearn ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`), form each
subject's functional connectivity over the **Craddock-200** parcellation and train a cross-validated
classifier to predict each subject's **sex** (`SEX` in the phenotypic table: 1 = male, 2 = female).

Report, in plain terms, **how well sex can be predicted from connectivity**.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series) with `SEX` in the phenotypic table.
Downloaded programmatically at runtime — nothing is pre-placed in the container, so **internet access
is required** on the first run (cached afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `classification.json` — the number of subjects and how well sex is predicted from connectivity
 (the performance).
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how well sex can be predicted.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason,
and still write parseable `run_metadata.json`, `classification.json`, and `findings.md`.
