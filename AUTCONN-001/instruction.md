# Group differences in resting-state connectivity in autism (AUTCONN-001)

## Scientific context

A large literature asks whether **autism spectrum disorder (ASD)** shows altered resting-state
functional connectivity relative to **typically-developing (TD) controls** — for example,
reduced default-mode-network connectivity in ASD (Assaf et al., 2010, *NeuroImage*,
https://doi.org/10.1016/j.neuroimage.2010.05.067). The ABIDE initiative (Di Martino et al.,
2014, *Molecular Psychiatry*) aggregates resting-state fMRI across sites specifically to test
such case–control connectivity differences at scale.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"])`, ASD vs
TD controls), form each subject's ROI×ROI functional connectivity matrix over the
**Dosenbach-160** parcellation, and test **which functional connections differ between the two
groups**. Report the connections that significantly differ.

The standard analytic choices the analysis leaves to the analyst (correlation type, the
group-comparison test) should follow common practice.

Report, in plain terms, **whether and where ASD and TD controls differ in resting-state
connectivity on these data** — stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Dosenbach-160 ROI time series). It is downloaded programmatically at runtime by the loader used in the Task section — nothing is pre-placed in the container, so **internet access is required** on the first run (the download is cached locally afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_dosenbach160"], quality_checked=True)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `group_differences.json` — `n_edges_tested`, `n_significant` (the number of connections you
  conclude **significantly differ** between the groups), and the significant connections (as a
  list of ROI-pair indices, or a summary).
- `run_metadata.json` — dataset, atlas, number of subjects per group, the test used, and the
  analytic choices you made.
- `findings.md` — a short written summary of whether/where ASD and TD controls differ in
  resting connectivity. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `group_differences.json`, and
`findings.md`.
