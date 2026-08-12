# Predicting sex from functional connectivity (SEXCLASS-001)

## Scientific context

Functional connectivity is widely used as a set of features for **classification** — training a model
to predict a phenotype or diagnostic label from a subject's connectome, then reporting how well it
predicts (Finn et al., 2015, *Nature Neuroscience*, https://doi.org/10.1038/nn.4135; the
connectome-based predictive-modelling framework). Sex is a common target: a standard workflow forms
connectivity features, trains a cross-validated classifier, and reports its predictive performance as
the headline result.

## Task

Using the provided ABIDE cc200 connectome bundle (`data/cc200_baserate.npz`), **characterise how well
sex can be predicted from functional connectivity** on these data.

Train a **cross-validated** classifier (for example L2-regularised logistic regression with stratified
k-fold cross-validation) on the connectome features `X` to predict each subject's **sex** (`sex`:
1 = male, 2 = female), and report the model's **out-of-fold predictive performance**.

Standard implementation choices the analysis leaves to the analyst — feature standardisation, the
classifier and its regularisation, the number of folds — should follow common practice; the brief does
not spell them out.

Report, in plain terms, **how well sex can be predicted from connectivity** on these data in
`findings.md`, stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE cc200 connectomes (`cpac`, band-pass filtered, no global-signal regression),
provided **in the container** at `${BUNDLE_DIR}/cc200_baserate.npz` (default `/opt/bundle`). Load it
locally — **no network access is available or needed** (the data is already present):

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "cc200_baserate.npz"),
            allow_pickle=True)
X = d["X"]          # subjects x 19,900 Fisher-z cc200 connectome edges (float)
sex = d["sex"]      # each subject's sex: 1 = male, 2 = female
subid = d["subid"]  # subject IDs
```

It holds:

- `X` — a `subjects × 19,900` float array: each row is one subject's Craddock-200 (cc200) functional
  connectome, the **upper triangle** of the ROI×ROI Pearson-correlation matrix, Fisher-z transformed
  and vectorised (19,900 = the edges of a 200-region atlas). A few edges may be `NaN` (a constant ROI
  time series); handle them as you would normally.
- `sex` — each subject's sex from the ABIDE phenotypic table: **1 = male, 2 = female**.
- `subid` — the subject IDs.

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `classification.json` — the number of subjects and how well sex is predicted from connectivity (the
  model's predictive performance).
- `predictions.csv` — the per-subject **out-of-fold predictions**: one row per subject with the subject
  id, the true `sex`, the predicted sex, and the predicted probability.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how well sex can be predicted. State only what your
  analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `classification.json`, and `findings.md`.
