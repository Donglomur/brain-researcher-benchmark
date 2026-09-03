# Object-category decoding across occipitotemporal cortex (OBJCAT-001)

## Scientific context

Haxby et al. (2001, *Science* 293:2425, https://doi.org/10.1126/science.1063736)
showed that the distributed pattern of response across occipitotemporal cortex carries
information about which object category a person is viewing. Because the whole-brain mask
contains far more voxels than there are training samples, MVPA pipelines routinely reduce
the feature set to the most category-selective voxels before training a classifier, and
report the **cross-validated decoding accuracy** of that classifier.

## Task

Using the classic Haxby dataset (`nilearn.datasets.fetch_haxby`), **decode the eight object
categories from occipitotemporal cortex after reducing to the most category-selective
voxels, and report the cross-validated 8-way decoding accuracy** of a linear
support-vector classifier.

Work with **`subject 2`** only. Fetch it with `fetch_haxby(subjects=[2])`; the returned
object gives the 4-D BOLD run (`func[0]`), the whole-brain analysis mask (`mask`), and a
labels/session table (`session_target[0]`) that lists, for every volume, the stimulus
category (`labels`) and the acquisition run it belongs to (`chunks`).

Pin the analysis as follows so the number is comparable:

- **Samples:** every volume whose `labels` is one of the eight object categories
  (`bottle, cat, chair, face, house, scissors, scrambledpix, shoe`) — i.e. drop only the
  `rest` volumes and keep the eight object conditions.
- **Features:** the voxels inside the whole-brain mask (`mask`), extracted with `nilearn`'s
  `NiftiMasker` using per-run z-scored, detrended voxel time series
  (`standardize="zscore_sample"`, `detrend=True`, with the acquisition runs passed as
  `runs=chunks` so each run is standardized separately).
- **Feature reduction:** restrict the classifier to the **500 voxels most selective for
  object category** — the 500 voxels with the highest ANOVA F-statistic (scikit-learn
  `sklearn.feature_selection.f_classif` / `SelectKBest(k=500)`) computed across the eight
  categories.
- **Classifier:** a linear SVM, `sklearn.svm.SVC(kernel="linear", C=1.0)`.
- **Cross-validation:** leave-one-run-out over the acquisition runs (`chunks`).

Report the leave-one-run-out cross-validated 8-way decoding accuracy of this classifier on
the 500 selected voxels (chance = 1/8 = 0.125).

## Output Location

Write all outputs to `${OUTPUT_DIR}` (default `/app/output`).

## Required Outputs

- `decoding_results.json` — at least a field `cv_accuracy` (float in 0–1), the
  cross-validated 8-way decoding accuracy you obtained, plus `n_samples`, `n_voxels`
  (voxels in the mask before reduction), `n_selected` (500), `n_categories`, `n_runs`, and
  `chance`.
- `run_metadata.json` — dataset id, subject, mask, and the preprocessing / feature-reduction
  / classifier choices you made.
- `findings.md` — a short written summary stating the cross-validated 8-way decoding
  accuracy and how you evaluated it. State only what your analysis actually supports.

## Failure handling

If the dataset cannot be resolved, exit non-zero with `failed_precondition` and a non-empty
reason, and still write parseable `run_metadata.json`, `decoding_results.json`, and
`findings.md`.
