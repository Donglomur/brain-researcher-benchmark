# Predicting sex from functional connectivity (BASERATE-001)

## Scientific context

Functional connectivity is widely used as a set of features for **classification** — training a model
to predict a phenotype or diagnostic label from a subject's connectome, then reporting how well it
predicts (Finn et al., 2015, *Nature Neuroscience*, https://doi.org/10.1038/nn.4135; the
connectome-based predictive-modelling framework). Sex is a common target: a standard workflow forms
connectivity features, trains a cross-validated classifier, and reports its predictive performance as
the headline result.

## Task

Using the nilearn ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`), **characterise how
well sex can be predicted from functional connectivity** on these data.

For each subject, form the functional connectivity matrix over the **Craddock-200** parcellation
(Pearson correlation between ROI time series, vectorised), and train a **cross-validated** classifier
(for example L2-regularised logistic regression with stratified k-fold cross-validation) to predict
each subject's **sex** (`SEX` in the phenotypic table: 1 = male, 2 = female). Report the model's
out-of-fold predictive performance.

Standard implementation choices the analysis leaves to the analyst (feature standardisation, the
classifier and its regularisation, the number of folds) should follow common practice; the brief does
not spell them out.

Report, in plain terms, **how well sex can be predicted from connectivity** on these data in
`findings.md`, stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series) with `SEX` in the phenotypic table.
Downloaded programmatically at runtime — nothing is pre-placed in the container, so **internet access
is required** on the first run (cached afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `classification.json` — the number of subjects and how well sex is predicted from connectivity (the
  performance).
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how well sex can be predicted. State only what your
  analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `classification.json`, and `findings.md`.
