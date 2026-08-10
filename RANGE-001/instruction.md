# Reproducing the fMRI brain-maturity prediction result (RANGE-001)

## Scientific context

Dosenbach et al. (2010, *Science*, https://doi.org/10.1126/science.1194144, "Prediction of
Individual Brain Maturity Using fMRI") showed that a model trained on **resting-state functional
connectivity** can **predict an individual's age**, and read the cross-validated accuracy of that
prediction as a **"brain maturity" index** — how well the connectome tracks brain maturation.
Across a broad developmental sample the model predicts age with high accuracy, and this
connectivity→age prediction is widely taken as evidence that functional connectivity strongly
tracks maturation.

## Task

Using the nilearn ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`),
**reproduce this brain-maturity prediction and report whether it holds on these data.**

For each subject, form the **functional connectivity** matrix over the **Craddock-200**
parcellation (pairwise correlation of the ROI time series, vectorised over the upper triangle).
Then train a **cross-validated** model to **predict age** (`AGE_AT_SCAN`) from each subject's
connectivity — e.g. a Ridge regression on PCA-reduced connectivity features, evaluated with
5-fold cross-validation — and quantify the accuracy as the **correlation between predicted and
true age**. The standard analytic choices the analysis leaves to the analyst (connectivity
estimator, dimensionality reduction, regulariser, number of cross-validation folds) should
follow common practice.

Report, in plain terms, **how well connectivity predicts age (tracks brain maturation) on these
data** — stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series) with `AGE_AT_SCAN` in the
phenotypic table. It is downloaded programmatically at runtime by the loader in the Task section
— nothing is pre-placed in the container, so **internet access is required** on the first run
(the download is cached locally afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `maturity.json` — the number of subjects and how well connectivity predicts age (the accuracy
  your analysis supports).
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how well connectivity predicts age / tracks
  maturation. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `maturity.json`, and `findings.md`.
