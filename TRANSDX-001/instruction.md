# Is functional connectivity a schizophrenia biomarker? (TRANSDX-001)

## Scientific context

A common translational goal is to build a **connectivity-based biomarker** for a psychiatric disorder:
train a classifier to distinguish patients from healthy controls on resting-state functional
connectivity, and report its accuracy as evidence that connectivity is a biomarker for that disorder.

## Task

Using the provided **UCLA Consortium for Neuropsychiatric Phenomics (CNP)** functional connectomes
(`data/cnp_connectomes.npz`), build a classifier to distinguish **schizophrenia** from **healthy
controls**, and report its cross-validated accuracy and **whether functional connectivity is a valid
biomarker for schizophrenia** — stating only what your analysis actually supports.

The standard analytic choices the analysis leaves to the analyst (classifier, cross-validation) should
follow common practice.

## Data

**Dataset:** resting-state functional connectomes for the UCLA CNP cohort (OpenNeuro **ds000030**),
provided analysis-ready in `data/cnp_connectomes.npz` (npz with `X` = subjects × 1128 connectome edges
over the Harvard-Oxford 48-ROI cortical atlas, `y` = diagnosis label per subject, `subjects` = IDs).
The groups are `CONTROL`, `SCHZ` (schizophrenia), `BIPOLAR` (bipolar disorder), and `ADHD`.

```python
import numpy as np
d = np.load("data/cnp_connectomes.npz", allow_pickle=True)
X, y = d["X"], d["y"]          # connectomes and diagnosis labels
```

Provenance: the connectomes were derived from the raw OpenNeuro ds000030 resting-state BOLD by the
pipeline in `data/build_connectomes.py` (+ `build_connectomes_worker.py`): mean-BOLD → MNI affine
registration (dipy), Harvard-Oxford atlas parcellation, CompCor confound regression, Pearson
correlation. Do not substitute a different dataset.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `specificity.json` — the number of subjects per group and the schizophrenia-classification
  performance your analysis supports.
- `run_metadata.json` — dataset, number of subjects, and the method used.
- `findings.md` — a short written summary of how well connectivity classifies schizophrenia and
  whether it is a valid schizophrenia biomarker. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty reason, and
still write parseable `run_metadata.json`, `specificity.json`, and `findings.md`.
