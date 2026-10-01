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

This task retains ABIDE as a paper-derived site/protocol-confounding methods case.
The scientific target is protocol-label prediction on unseen sites, not an identifiable
biological eye-state effect. Use leave-one-site-out CV and pool all held-out subject
predictions before calculating BA=(open recall+closed recall)/2. Do NOT average one-class
site BA scores: their constant-class baseline differs. Report random-10-fold pooled BA
separately, with both always-open/closed pooled baselines and an unseen-site site-only
baseline (training-majority fallback). Site/eye aliasing can survive held-site validation;
it cannot be erased by LOSO. Show site label support and distinguish within-site
identifiability from predictive transfer. No causal or null claim without appropriate
clustered/permutation evidence. Add oof_predictions.csv with exact subject_id, site,
label (1 open/0 closed), fold_site (equal held-out site), prediction, site_only_prediction,
random_fold (0–9), random_prediction. Headline and baselines recompute from these rows.

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
- **Features:** correlations derived from **LedoitWolf-shrunk covariance**, not ordinary
  Pearson correlations. Use `ConnectivityMeasure(cov_estimator=LedoitWolf(store_precision=False,
  assume_centered=False), kind="correlation", vectorize=True, discard_diagonal=True,
  standardize=True)`: per-subject time-series z-scoring and the off-diagonal lower triangle
  (19,900 features). These are the actual pinned nilearn 0.13.1 estimator defaults,
  now disclosed explicitly ([documentation](https://nilearn.github.io/stable/modules/generated/nilearn.connectome.ConnectivityMeasure.html)).
- **Classifier:** fit `StandardScaler(with_mean=True, with_std=True)` on training subjects
  within each fold, followed by `LinearSVC(C=1.0, dual="auto", max_iter=3000,
  random_state=0, penalty="l2", loss="squared_hinge", tol=1e-4, fit_intercept=True,
  intercept_scaling=1, class_weight=None)` (scikit-learn 1.8.0). Do not learn scaling from
  held-out subjects. Random-CV sensitivity uses `StratifiedKFold(10, shuffle=True,
  random_state=0)` in the dataset order.
- **Metric:** **balanced accuracy** (the classes are imbalanced).

Report the cross-validated balanced accuracy of this classifier as your headline
`cv_balanced_accuracy` (chance = 0.5).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `per_fold.csv` — one row per cross-validation fold: `fold_id` (an identifier for the
  held-out fold), `n_test`, and `balanced_accuracy` (descriptive per-site recall;
  the headline is pooled OOF balanced accuracy, not its fold mean).
- `eye_decoding_results.json` — at least `cv_balanced_accuracy` (float in 0–1, the
  cross-validated balanced accuracy you obtained), plus `n_subjects`, `n_features`,
  `n_sites`, and `chance`.
- `run_metadata.json` — dataset id, atlas, connectivity, classifier and evaluation choices
  you made.
  Record `estimator_contract="ledoitwolf-correlation-losocv-v1"`. The complete keyed
  subject predictions, not only aggregate site scores, are numerical proof of the
  specified held-out analysis. Scientifically valid alternatives can be reported as
  separate sensitivity analyses; they are not silently scored against this estimator.
- `findings.md` — a short written summary stating the cross-validated balanced accuracy for
  eyes-open vs eyes-closed decoding on these data. State only what your analysis actually
  supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `eye_decoding_results.json`, and
`findings.md`.
