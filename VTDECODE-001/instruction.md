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

Work with **`subject 1`** only. Fetch it with
`fetch_haxby(subjects=[1])`; the returned object gives the 4-D BOLD run
(`func[0]`), the ventral-temporal mask (`mask_vt[0]`), and a labels/session table
(`session_target[0]`) that lists, for every volume, the stimulus category
(`labels`) and the acquisition run it belongs to (`chunks`).

Pin the analysis as follows so the number is comparable:

- **Samples:** every volume whose `labels` is one of the eight object categories
  (`bottle, cat, chair, face, house, scissors, scrambledpix, shoe`) — i.e. drop only
  the `rest` volumes and keep the eight object conditions.
- **Features:** the voxels inside `mask_vt`, extracted with `nilearn`'s
  `NiftiMasker` using per-run z-scored, detrended voxel time series
  (`standardize="zscore_sample"`, `detrend=True`, `t_r=2.5`).
- **Classifier:** a linear SVM, `sklearn.svm.SVC(kernel="linear", C=1.0)`.

Report the cross-validated accuracy of this classifier on these eight categories
(chance = 1/8 = 0.125).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `decoding_results.json` — at least a field `cv_accuracy` (float in 0–1), the
  cross-validated decoding accuracy you obtained, plus `n_samples`, `n_voxels`,
  `n_categories`, and `chance`.
- `run_metadata.json` — dataset id, subject, mask, and the preprocessing /
  classifier choices you made.
- `findings.md` — a short written summary stating the cross-validated decoding
  accuracy for the eight object categories and how you evaluated it. State only what
  your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a
non-empty reason, and still write parseable `run_metadata.json`,
`decoding_results.json`, and `findings.md`.
