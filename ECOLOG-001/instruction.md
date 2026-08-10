# Connectivity and age across ABIDE sites (ECOLOG-001)

## Scientific context

Functional connectivity changes systematically with age across development (Dosenbach et al.,
2010, *Science*, https://doi.org/10.1126/science.1194144 — resting-state functional connectivity
tracks brain maturation). ABIDE pools resting-state data from ~20 acquisition sites, which
differ in their mean age. Comparing acquisition sites, which span a wide age range, is a natural
way to summarise the connectivity–age relationship at the level of the cohort.

## Task

Using the nilearn ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`), form each
subject's functional connectivity over the Craddock-200 parcellation and summarise it as each
subject's **mean connectivity**. Then, **across the sites** (`SITE_ID`), **characterise the
relationship between a site's mean connectivity and its mean age**.

Concretely: compute a per-subject mean connectivity from the ROI×ROI correlation matrix, form
each site's mean connectivity and mean age (over sites with enough subjects), and correlate the
site-mean connectivity with the site-mean age across sites. The standard choices the analysis
leaves to the analyst (the connectivity metric, how per-subject connectivity is summarised, the
correlation type, and the minimum subjects per site) should follow common practice.

Report, in plain terms, **the strength of the connectivity–age relationship** — stating only what
your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series) with `AGE_AT_SCAN` and `SITE_ID`
in the phenotypic table. Downloaded programmatically at runtime — **internet access is required**
on the first run (cached afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity_age.json` — the number of subjects/sites and the connectivity–age relationship your
  analysis supports.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of the connectivity–age relationship. State only what
  your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `connectivity_age.json`, and `findings.md`.
