# Reproducing the fMRI brain-maturity prediction result (BRAINMATUR-001)

## Scientific context

Dosenbach et al. (2010, *Science*, https://doi.org/10.1126/science.1194144, "Prediction of
Individual Brain Maturity Using fMRI") showed that a model trained on **resting-state functional
connectivity** can **predict an individual's age**, and read the cross-validated accuracy of that
prediction as a **"brain maturity" index** — how well the connectome tracks brain maturation.
Across a broad developmental sample the model predicts age with high accuracy, and this
connectivity→age prediction is widely taken as evidence that functional connectivity strongly
tracks maturation.

## Task

Using the provided ABIDE cc200 connectome bundle (`${BUNDLE_DIR}/cc200_range.npz`),
**reproduce this brain-maturity prediction and report whether it holds on these data.**

Each subject's **functional connectivity** over the **Craddock-200** parcellation is already
provided as a vectorised edge feature vector (`X`, below). Train a **cross-validated** model to
**predict age** (`age`, `AGE_AT_SCAN` in years) from each subject's connectivity — e.g. a Ridge
regression on PCA-reduced connectivity features, evaluated with 5-fold cross-validation — and
quantify the accuracy as the **correlation between predicted and true age**. The standard analytic
choices the analysis leaves to the analyst (dimensionality reduction, regulariser, number of
cross-validation folds) should follow common practice.

Report, in plain terms, **how well connectivity predicts age (tracks brain maturation) on these
data** — stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state cc200 connectomes, provided **in the container** at
`${BUNDLE_DIR}/cc200_range.npz` (default `/opt/bundle`) — **no download; no network available or
needed** (the data is already present). Load with

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "cc200_range.npz"),
            allow_pickle=True)
```

It holds:

- `X` — float16 array, **1035 subjects × 19,900 edges**: the upper triangle of each subject's
  Craddock-200 functional connectome (pairwise Pearson correlation of the ROI time series,
  Fisher-z transformed). A small fraction of edges are `NaN`; handle them (e.g. treat as 0) before
  fitting.
- `age` — float32, each subject's age in years (`AGE_AT_SCAN`); already restricted to subjects
  with valid age.
- `site` — string, the scanner/acquisition site for each subject.
- `subid` — integer subject identifier.

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `maturity.json` — the number of subjects and how well connectivity predicts age (the accuracy
  your analysis supports, e.g. the predicted-vs-true age correlation).
- `subject_predictions.csv` — one row per subject: `subid`, `age` (true age), `predicted_age`
  (the cross-validated prediction), and `site`.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how well connectivity predicts age / tracks
  maturation. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `maturity.json`, and `findings.md`.
