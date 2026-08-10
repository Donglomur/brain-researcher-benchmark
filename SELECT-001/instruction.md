# The connections that most differ between autism and controls (SELECT-001)

## Scientific context

A common case–control analysis identifies the functional connections that **most strongly
differ** between a clinical group and controls, and reports how large those differences are.
The ABIDE initiative (Di Martino et al., 2014, *Molecular Psychiatry*,
https://doi.org/10.1038/mp.2013.78) is the standard resource for such autism (ASD) vs
typically-developing (TD) connectivity comparisons.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`), form each
subject's ROI×ROI functional connectivity over the **Craddock-200 (cc200)** parcellation, and
**identify the connections that most differ between ASD and TD controls**. Report the **top
differing connections and how strongly they differ** (their effect sizes).

Report, in plain terms, **which connections most differ between ASD and controls on these
data, and how large those differences are**.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `top_differences.json` — the `top_connections` (each an ROI-pair with its effect size, e.g.
 a t-statistic), how many were selected, and `n_subjects`.
- `run_metadata.json` — dataset, atlas, number of subjects per group, the statistic used, and
 the analytic choices you made.
- `findings.md` — a short written summary of which connections most differ and how strongly.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `top_differences.json`, and
`findings.md`.
