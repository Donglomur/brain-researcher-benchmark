# Reproducing the autism-vs-control functional-connectivity differences (SELECT-001)

## Scientific context

A cornerstone case–control finding in autism neuroimaging is that resting-state **functional
connectivity differs between autism (ASD) and typically-developing (TD) controls**. The ABIDE
initiative (Di Martino et al., 2014, *Molecular Psychiatry*, https://doi.org/10.1038/mp.2013.78),
aggregating resting-state fMRI across many sites, established that a set of cortico-cortical
connections separates ASD from TD, and a standard analysis identifies **which connections differ
most** between the groups and reports **how strongly** they differ (their effect sizes). These "top"
group-differentiating connections are routinely reported as the strongest autism connectivity
signatures.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`, ~400 subjects with
the `DX_GROUP` phenotype), **reproduce this ASD-vs-control connectivity-difference result and report
whether it holds on these data.**

For each subject, form the ROI×ROI functional connectivity over the **Craddock-200 (cc200)**
parcellation (Pearson correlation of the region time series, Fisher-z transformed), and take the
**upper-triangle edges** (~19,900 connections). For each edge, compute a **group-difference statistic**
between ASD (`DX_GROUP == 1`) and TD (`DX_GROUP == 2`) — a two-sample (Welch) t across subjects.
**Rank the edges by |t| and take the top 100** most-differing connections, and report those **top
differing connections and their effect sizes** (the |t| of each). The standard preprocessing choices
the analysis leaves to the analyst (nuisance regression, temporal filtering, signal normalisation)
should follow common practice.

Report, in plain terms, **whether the autism-vs-control connectivity differences reproduce on these
data, and how large the differences at the top connections are** — stating only what your analysis
actually supports.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series). It is downloaded programmatically at
runtime by the loader in the Task section — nothing is pre-placed in the container, so **internet
access is required** on the first run (cached locally afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `top_differences.json` — the `top_connections` (each an ROI-pair with its effect size, e.g. a
  t-statistic), how many connections were taken, and `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects per group, the statistic used, and the
  analytic choices you made.
- `findings.md` — a short written summary of which connections most differ, how strongly they differ,
  and whether those differences hold on these data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `top_differences.json`, and `findings.md`.
