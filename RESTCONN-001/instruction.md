# Is the cerebellum functionally connected to the default-mode network? (RESTCONN-001)

## Scientific context

The cerebellum is now understood to participate in the cerebral association networks,
including the default-mode network (DMN) (Buckner et al. 2011, *J. Neurophysiol.*; Habas
et al. 2009). A basic question for any single resting-state dataset is therefore whether a
DMN cortical node and a cerebellar node show a **functionally connected** BOLD signal — i.e.
whether their resting time series are correlated beyond what would be expected by chance.

## Task

Using nilearn's copy of the **ADHD-200** resting-state sample
(`nilearn.datasets.fetch_adhd`), analyse **subject `0010064`** and decide whether its
right default-mode node and its cerebellar node are functionally connected.

Define the two regions with the **MSDL probabilistic atlas**
(`nilearn.datasets.fetch_atlas_msdl`): the ROI labelled **`R DMN`** and the ROI labelled
**`Cereb`**. Extract each region's mean BOLD time series with
`nilearn.maskers.NiftiMapsMasker` using standard resting-state settings:

- `detrend=True`, z-score standardisation, band-pass **0.01–0.1 Hz**, `t_r=2.0`;
- regress the nuisance signals provided in the subject's regressors file
  (`*_regressors.csv`, **tab-separated**): the **6 head-motion parameters**
  (`motion-*`), the **5 CompCor components** (`compcor1`–`compcor5`), and the **CSF** and
  **white-matter** signals (`csf`, `wm`).

Then compute the **Pearson correlation** between the `R DMN` and `Cereb` time series, and
determine **whether the two regions are significantly functionally connected** (at
`alpha = 0.05`). Report the correlation coefficient together with its statistical
significance, and state a clear conclusion.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `connectivity.json` — the result of the analysis, with at least:
  `{"subject", "region_a", "region_b", "n_timepoints", "r", "p_value", "significant"}`
  (`significant` is your boolean verdict at `alpha = 0.05`).
- `run_metadata.json` — dataset, subject, atlas, number of timepoints, and the
  preprocessing you applied.
- `findings.md` — a short written summary reporting the correlation between `R DMN` and
  `Cereb` and whether they are significantly functionally connected on these data. State
  only what your analysis actually supports.

## Failure handling

If the dataset or atlas cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `run_metadata.json`, `connectivity.json`, and
`findings.md`.
