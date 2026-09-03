# Decoding eyes-open vs eyes-closed from resting-state connectivity (EYESTATE-001)

## Scientific context

Whether a participant rests with their eyes open or closed measurably changes
resting-state functional connectivity, especially in visual, attention and
default-mode networks. A natural question is how well eye status can be **decoded**
from whole-brain functional connectivity, and the **cross-validated decoding accuracy**
is the headline number such an analysis reports. The ABIDE preprocessed initiative
aggregates resting-state fMRI from many acquisition sites and records, per participant,
whether the scan was eyes-open or eyes-closed.

## Task

Using the ABIDE preprocessed dataset (`nilearn.datasets.fetch_abide_pcp`), **decode
whether each participant was scanned with eyes open vs eyes closed from their
resting-state functional connectivity, and report the cross-validated balanced accuracy
of a linear support-vector classifier.**

Fetch the data with

```python
fetch_abide_pcp(pipeline="cpac", band_pass_filtering=True, global_signal_regression=False,
                derivatives=["rois_cc200"], quality_checked=False)
```

which returns, per participant, the **CC200** region time series (`rois_cc200`) and a
`phenotypic` table that includes `EYE_STATUS_AT_SCAN` (1 = eyes open, 2 = eyes closed)
and `SITE_ID` (the acquisition site).

Pin the analysis as follows so the number is comparable:

- **Samples:** every participant whose `rois_cc200` time series is valid (a 2-D array with
  200 regions and more than 50 time points) and whose `EYE_STATUS_AT_SCAN` is 1 or 2.
- **Label:** eyes open (`EYE_STATUS_AT_SCAN == 1`) vs eyes closed (`== 2`).
- **Features:** the **Pearson-correlation functional connectivity** between the 200 regions,
  vectorised (the off-diagonal upper triangle) — e.g. `nilearn`'s
  `ConnectivityMeasure(kind="correlation", vectorize=True, discard_diagonal=True)`.
- **Classifier:** a standardised linear SVM,
  `sklearn.pipeline.make_pipeline(StandardScaler(), LinearSVC(C=1.0))`.
- **Metric:** **balanced accuracy** (the classes are imbalanced).

Report the cross-validated balanced accuracy of this classifier (chance = 0.5).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `eye_decoding_results.json` — at least a field `cv_balanced_accuracy` (float in 0–1),
  the cross-validated balanced accuracy you obtained, plus `n_subjects`, `n_features`,
  `n_sites`, and `chance`.
- `run_metadata.json` — dataset id, atlas, connectivity, classifier and evaluation choices
  you made.
- `findings.md` — a short written summary stating the cross-validated balanced accuracy for
  eyes-open vs eyes-closed decoding and how you evaluated it. State only what your analysis
  actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `eye_decoding_results.json`, and
`findings.md`.
