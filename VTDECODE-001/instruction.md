# Decoding object categories from ventral-temporal cortex (VTDECODE-001)

## Scientific context

Haxby et al. (2001, *Science* 293:2425, https://doi.org/10.1126/science.1063736)
showed that the distributed pattern of response in ventral-temporal (VT) cortex
carries information about which object category a person is viewing. Multi-voxel
pattern analysis (MVPA) — training a linear classifier on VT activity patterns and
scoring it out-of-sample — is the standard way to quantify this, and the
**cross-validated decoding accuracy** is the headline number such analyses report.

## Task

Using the classic Haxby dataset (`nilearn.datasets.fetch_haxby`), **decode the eight
object categories from ventral-temporal cortex and report the cross-validated
decoding accuracy of a linear support-vector classifier.**

Work with **subject 1** only. The public PyMVPA 2010-01-14 release is already
staged in `/app/data/subj1/`: `bold.nii.gz` (4-D BOLD), `mask4_vt.nii.gz`
(ventral-temporal mask), and `labels.txt` (stimulus category `labels` and
acquisition run `chunks` for every volume). `/app/data/data_manifest.json`
records the source URL, license, sizes, and SHA256 checksums. Use these local
files; the task and verifier run offline. No runtime dataset download is needed.

Pin the analysis as follows so the number is comparable:

- **Samples:** every volume whose `labels` is one of the eight object categories
  (`bottle, cat, chair, face, house, scissors, scrambledpix, shoe`) — i.e. drop only
  the `rest` volumes and keep the eight object conditions.
- **Features:** the voxels inside `mask_vt`, extracted with `nilearn`'s
  `NiftiMasker` using per-run z-scored, detrended voxel time series
  (`standardize="zscore_sample"`, `detrend=True`, `t_r=2.5`, with full-volume
  acquisition `runs=chunks` passed to the masker constructor).
- **Classifier:** `sklearn.svm.SVC(kernel="linear", C=1.0, tol=0.001,
  shrinking=True)`, with other scikit-learn defaults unchanged. Do not add feature
  selection, spatial smoothing, class weighting, or tune hyperparameters.

Report the cross-validated accuracy of this classifier on these eight categories
(chance = 1/8 = 0.125).
The estimand is generalization to an unseen acquisition run: use leave-one-run-out
over all twelve source `chunks` (0–11). Clean each full run before dropping rest;
do not detrend or standardize across run boundaries. The pinned environment uses
Nilearn 0.13.1 and scikit-learn 1.8.0. This is a paper-derived modern
decoding-method analysis, not Haxby's original pattern-correlation statistic.
Interpret accuracy conditional on the supplied fixed VT mask. This exercise does
not establish that ROI selection was independent of the acquisition data, and
does not estimate performance of a full ROI-discovery pipeline or new subjects.

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `decoding_results.json` — at least a field `cv_accuracy` (float in 0–1), the
  cross-validated decoding accuracy you obtained, plus `n_samples`, `n_voxels`,
  `n_categories`, and `chance`.
- `predictions.csv` — one row per non-rest source volume, with zero-based original
  `volume_id`, `held_out_run`, `true_label`, `predicted_label`. Every volume must
  appear exactly once, in the fold for its acquisition run.
- `per_fold.csv` — one row per cross-validation fold, with columns
  `fold, n_test_samples, accuracy` (the held-out accuracy of each fold in the
  cross-validation you ran). Your reported `cv_accuracy` must be the mean of these
  per-fold accuracies. If your cross-validation groups the samples, also include the
  held-out group/run identifier as a column.
- `run_metadata.json` — record the following machine-readable contract (additional
  descriptive fields are welcome):
  `task_id="VTDECODE-001"`, `dataset_id="haxby2001"`, `subject=1`,
  `mask="mask4_vt"`, `pipeline_id="runwise-clean-loro-v2"`,
  `cross_validation="leave-one-run-out"`, and `n_samples`, `n_voxels`, `n_runs`.
  Set `preprocessing` to an object with `detrend=true`,
  `standardize="zscore_sample"`, `t_r=2.5`, `cleaning_unit="acquisition_run"`,
  `clean_before_rest_removal=true`; set `classifier` to an object with
  `name="SVC"`, `kernel="linear"`, `C=1.0`, `tol=0.001`, `shrinking=true`.
  Include `source_sha256`, mapping each manifest-relative file path to its SHA256.
- `findings.md` — a short written summary stating the cross-validated decoding
  accuracy for the eight object categories and how you evaluated it. State only what
  your analysis actually supports.

## Source-membership auditing

For source-membership auditing, source_labels.txt is frozen in /app/data. Require
every non-rest volume exactly once in predictions.csv with its original acquisition
run and true category. per_fold.csv must include held_out_run (0–11), n_test_samples,
accuracy; these must recompute from predictions.csv. Include n_runs=12 in
decoding_results.json. The label table verifies membership and score arithmetic,
not whether the classifier was actually trained or fitted without leakage.
The verifier additionally compares the source-keyed predicted categories to the
reference implementation of the declared, pinned recipe. Row order is irrelevant.
Report fold accuracy to at least six decimal places and the headline to at least
four; rounding tolerances are 1e-6 and 0.000051 respectively. There is no private
minimum accuracy, required random-split contrast, or prose-keyword gate. Passing
output checks alone is not proof that the submitted code was executed.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `run_metadata.json`,
`decoding_results.json`, and `findings.md`.
