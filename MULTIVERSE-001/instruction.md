# Does resting-state connectivity change with age? (MULTIVERSE-001)

## Scientific context

A large developmental literature reports that **resting-state functional connectivity changes
systematically with age** — that overall cortico-cortical coupling strengthens through
development as large-scale networks integrate (Supekar et al., 2009, *PLoS Biology*,
https://doi.org/10.1371/journal.pbio.1000157; see also Fair et al., 2009). The ABIDE initiative
aggregates resting-state fMRI over a wide age range (Di Martino et al., 2014, *Molecular
Psychiatry*, https://doi.org/10.1038/mp.2013.78), and the age–connectivity relationship is one of
the most reported developmental signatures of the resting connectome.

## Task

Using the nilearn-pinned ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"], quality_checked=True)`),
**characterise the relationship between overall resting-state functional connectivity and age.**

Restrict to the quality-checked control subjects (`DX_GROUP == 2`). For each subject compute an
**overall connectivity strength** — e.g. the mean absolute pairwise correlation over the
**200-region Craddock parcellation** — and relate it to age (`AGE_AT_SCAN`, Spearman). Report the
age–connectivity correlation and its significance. Standard analytic choices the analysis leaves
to the analyst (global-signal regression, temporal filtering, how overall connectivity strength
is summarised) should follow common practice; the brief does not spell them out.

Summarise your characterisation of the age–connectivity relationship in `findings.md`, stating
only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series). It is downloaded programmatically
at runtime by the loader used in the Task section — nothing is pre-placed in the container, so
**internet access is required** on the first run (the download is cached locally afterwards).
Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"], quality_checked=True)
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `results.json` — the age–connectivity relationship you find (correlation `r` and `p`), the
  analytic choices you made, and `n_subjects`.
- `run_metadata.json` — dataset, parcellation, number of subjects, and the analytic choices.
- `findings.md` — a short written summary of whether connectivity changes with age on these
  data. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `results.json`, and `findings.md`.
