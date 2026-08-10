# Classifying autism from functional connectivity (DEEPLIN-001)

## Scientific context

Functional connectivity is a common feature set for **classifying** a diagnosis, and deep and
nonlinear machine-learning models are widely applied to connectome features. On the ABIDE autism
cohort, deep neural networks trained on resting-state functional connectivity have been reported
to distinguish autism from controls (Heinsfeld et al., 2018, *NeuroImage: Clinical*,
"Identification of autism spectrum disorder using deep learning and the ABIDE dataset",
https://doi.org/10.1016/j.nicl.2017.08.017, ~70% accuracy). Reporting the classification accuracy
of such a model is the headline result of these analyses.

## Task

Using the nilearn ABIDE derivatives
(`nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])`), form each
subject's functional connectivity over the Craddock-200 parcellation and **build the
best-performing classifier you can** to distinguish autism (`DX_GROUP == 1`) from controls
(`DX_GROUP == 2`). Then **characterise how accurately autism can be classified from
connectivity**.

The connectome features are the vectorised ROI×ROI correlation matrices; the label is `DX_GROUP`;
`SITE_ID` (acquisition site) is available in the phenotypic table, so the data span ~20
acquisition sites. Standard modelling choices the task leaves to the analyst (the model family
and its hyper-parameters, dimensionality reduction, feature scaling, and the cross-validation
scheme) should follow common practice; the brief does not spell them out.

Summarise your characterisation in `findings.md`, reporting **how accurately autism can be
classified from connectivity** — stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state (Craddock-200 ROI time series) with `DX_GROUP` and `SITE_ID` in
the phenotypic table. Downloaded programmatically at runtime — **internet access is required** on
the first run (cached afterwards). Fetch it with:

```python
nilearn.datasets.fetch_abide_pcp(pipeline="cpac", derivatives=["rois_cc200"])
```

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `models.json` — the number of subjects and the classification accuracy.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how accurately autism can be classified. State only
  what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `models.json`, and `findings.md`.
