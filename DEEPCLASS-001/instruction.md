# Classifying autism from functional connectivity (DEEPCLASS-001)

## Scientific context

Functional connectivity is a common feature set for **classifying** a diagnosis, and deep and
nonlinear machine-learning models are widely applied to connectome features. On the ABIDE autism
cohort, deep neural networks trained on resting-state functional connectivity have been reported
to distinguish autism from controls (Heinsfeld et al., 2018, *NeuroImage: Clinical*,
"Identification of autism spectrum disorder using deep learning and the ABIDE dataset",
https://doi.org/10.1016/j.nicl.2017.08.017, ~70% accuracy). Reporting the classification accuracy
of such a model is the headline result of these analyses.

## Task

Using the provided ABIDE cc200 connectome bundle (`${BUNDLE_DIR}/cc200_deeplin.npz`), **build the
best-performing classifier you can** to distinguish autism (`dx == 1`) from controls (`dx == 2`)
from each subject's functional connectivity, and then **characterise how accurately autism can be
classified from connectivity**.

The connectome features are the vectorised ROI×ROI correlation edges (`X`); the label is `dx`; the
acquisition site (`site`, i.e. `SITE_ID`) is provided, so the data span ~20 acquisition sites.
Standard modelling choices the task leaves to the analyst (the model family and its
hyper-parameters, dimensionality reduction, feature scaling, and the cross-validation scheme)
should follow common practice; the brief does not spell them out. Make the analysis reproducible
(fix random seeds).

Summarise your characterisation in `findings.md`, reporting **how accurately autism can be
classified from connectivity** — stating only what your analysis actually supports.

## Data

**Dataset:** ABIDE resting-state functional connectomes (ABIDE_pcp, cpac pipeline, Craddock-200
parcellation), provided **in the container** at `${BUNDLE_DIR}/cc200_deeplin.npz` (default
`/opt/bundle`) — **no download; no network available or needed** (the data is already present).
Load it locally:

```python
import os, numpy as np
d = np.load(os.path.join(os.environ.get("BUNDLE_DIR", "/opt/bundle"), "cc200_deeplin.npz"),
            allow_pickle=True)
```

It holds:

- `X` — subjects × **19,900** functional-connectivity edges (the upper triangle of the 200×200
  Craddock-200 ROI correlation matrix, Pearson r, Fisher-z transformed). A small number of edges
  contain `NaN` (constant/dropped ROIs); handle them (e.g. replace with 0) before modelling.
- `dx` — diagnosis label, **1 = autism (ASD), 2 = control (TD)**.
- `site` — acquisition-site ID (`SITE_ID`), a string per subject (~20 sites).

Do not substitute a different or manually-prepared dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `models.json` — the number of subjects (and sites), and the classification accuracy of each
  model you evaluated (the accuracy per model, keyed by model name).
- `run_metadata.json` — dataset, number of subjects, and the method used (including the
  cross-validation scheme and random seed).
- `findings.md` — a short written summary of how accurately autism can be classified from
  connectivity. State only what your analysis actually supports.

## Failure handling

If the packaged dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `run_metadata.json`, `models.json`, and `findings.md`.
