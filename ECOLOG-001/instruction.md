# Connectivity and age across ABIDE sites (ECOLOG-001)

## Scientific context

Functional connectivity changes across the lifespan. ABIDE aggregates resting-state data from ~20
acquisition sites, which differ in their mean age.

## Task

Using the nilearn ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`), form each subject's
functional connectivity over the Craddock-200 parcellation and summarise it as each subject's mean
connectivity. Then, **across the sites** (`SITE_ID`), examine the relationship between a **site's mean
connectivity** and its **mean age**.

Report, in plain terms, **the strength of the connectivity-age relationship**.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series) with `AGE_AT_SCAN` and `SITE_ID` in the
phenotypic table. Downloaded programmatically at runtime — **internet access is required** on the first
run (cached afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `ecolog.json` — the number of subjects/sites and the connectivity-age relationship your analysis
 supports.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of the connectivity-age relationship.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `ecolog.json`, and `findings.md`.
