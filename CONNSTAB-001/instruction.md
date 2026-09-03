# Within-run reproducibility of the resting-state functional connectome (CONNSTAB-001)

## Scientific context

A basic property of resting-state functional connectivity is how **reproducible** the
functional connectome is: if you estimate the region×region connectivity matrix twice from
independent portions of the same scan, how similar are the two estimates? This within-run
reproducibility sets a ceiling on what any connectivity analysis of a single run can support.
The nilearn **ADHD-200** sample provides preprocessed resting-state runs from 40 participants.

## Task

Using the nilearn ADHD-200 sample, **quantify how reproducible the resting-state functional
connectome is between the two halves of each run, and report it.**

Fetch the data with

```python
from nilearn.datasets import fetch_adhd, fetch_atlas_msdl
adhd = fetch_adhd(n_subjects=40)   # adhd.func, adhd.confounds
msdl = fetch_atlas_msdl()          # atlas maps + region labels
```

Pin the analysis as follows so the number is comparable:

- **Participants:** the 40 returned by `fetch_adhd(n_subjects=40)`.
- **Time series:** extract each participant's region time series with
  `nilearn.maskers.NiftiMapsMasker(maps_img=msdl.maps, standardize="zscore_sample")`, passing
  that participant's `confounds` file so nuisance signals are regressed out.
- **Connectome:** the **MSDL** region×region **Pearson-correlation** connectivity matrix;
  use the vectorised upper triangle (Fisher-z transformed) as the connectome edge vector.
- **Reproducibility:** for each participant, split the run into its two halves, estimate the
  connectome from each half, and take the **correlation between the two half-run connectome
  edge vectors**. Summarise across participants (mean).

Report the within-run reproducibility of the connectome (a correlation).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `reproducibility_results.json` — at least a field `connectome_reproducibility` (float),
  the mean between-halves connectome correlation you obtained, plus `n_subjects`.
- `run_metadata.json` — dataset id, atlas, connectivity and how you split each run and
  computed the reproducibility.
- `findings.md` — a short written summary stating the within-run connectome reproducibility
  and how you computed it. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `reproducibility_results.json`, and
`findings.md`.
