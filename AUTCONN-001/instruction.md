# Group differences in resting-state connectivity in autism (AUTCONN-001)

## Scientific context

A large literature asks whether **autism spectrum disorder (ASD)** shows altered resting-state
functional connectivity relative to **typically-developing (TD) controls**. A frequently-cited
example is reduced connectivity within the **default-mode network** (PCC/mPFC) in ASD (Assaf et al.,
2010, *NeuroImage*, https://doi.org/10.1016/j.neuroimage.2010.05.067). The ABIDE initiative
(Di Martino et al., 2014, *Molecular Psychiatry*, https://doi.org/10.1038/mp.2013.78) aggregates
resting-state fMRI across sites specifically to test such case-control connectivity differences at
scale, and the whole-brain edgewise comparison — which connections differ between the groups — is the
result these analyses report.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"], quality_checked=True)`,
ASD vs TD controls), **characterise which resting-state functional connections differ between the two
groups** on these data.

For each subject, form the ROI×ROI functional connectivity matrix over the **Dosenbach-160**
parcellation (Pearson correlation between ROI time series, Fisher-z transformed), giving the
160×159/2 ≈ **12,720 unique connections**. Then compare the two groups **edge by edge** — a two-sample
(e.g. Welch) test of ASD vs TD at each connection — and report the connections you conclude
significantly differ, plus the within-default-mode-network connectivity in each group for context.

Standard analytic choices the analysis leaves to the analyst (nuisance handling, band-pass filtering,
how degenerate/NaN edges are dealt with, the exact test) should follow common practice; the brief does
not spell them out.

Summarise, in plain terms, **whether and where ASD and TD controls differ in resting-state connectivity
on these data** in `findings.md`, stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Dosenbach-160 ROI time series). It is downloaded programmatically at
runtime by the loader used in the Task section — nothing is pre-placed in the container, so **internet
access is required** on the first run (the download is cached locally afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"], quality_checked=True)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `group_differences.json` — `n_edges_tested`, `n_significant` (the number of connections you conclude
  **significantly differ** between the groups), and the significant connections (as a list of ROI-pair
  indices, or a summary).
- `run_metadata.json` — dataset, atlas, number of subjects per group, the test used, and the analytic
  choices you made.
- `findings.md` — a short written summary of whether/where ASD and TD controls differ in resting
  connectivity. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `group_differences.json`, and `findings.md`.
