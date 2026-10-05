# Whole-brain object-category decoding with nested feature selection

Haxby et al. (2001, *Science*, https://doi.org/10.1126/science.1063736)
studied distributed category-related response patterns in ventral temporal
cortex. This task uses their public subject-2 data for a modern whole-brain
classification method case. It does not reproduce the original six-subject
pattern-correlation result or establish occipitotemporal localization.

Estimate eight-category, leave-one-run-out accuracy of a linear SVM using
500 features selected independently within each training fold. Report the
source-indexed held-out predictions and selected features, so the result can
be traced to the actual samples and training-only selection.

## Data and scope

Original BOLD, labels and supplied whole-brain mask are baked into
`/app/data/objcat`; `data_manifest.json` records exact filenames, hashes,
source URLs and terms. Do not fetch data at runtime or substitute a VT mask.
The public numerical metadata template is `/app/method_contract.json`.

Use subject 2 only: all 1,452 original volumes for runwise preprocessing,
then all 864 non-rest volumes in the eight categories `bottle`, `cat`,
`chair`, `face`, `house`, `scissors`, `scrambledpix`, `shoe`.
Original labels determine run IDs 0–11 and zero-based original volume IDs.
There are 72 non-rest volumes per run. Never renumber retained volume IDs.

The separately distributed whole-brain mask is a fixed supplied input. Its
generation history and independent-selection provenance are not established;
do not interpret it as independently validated anatomical discovery.

## Analysis

1. Verify the supplied hashes and BOLD/mask shape and affine alignment; no
   resampling or smoothing. Use the finite binary mask's nonzero voxels in
   NumPy C order. A feature index is its zero-based position in this mask
   ordering; `(i,j,k)` is its zero-based source voxel coordinate.
2. Extract scaled source BOLD as float64. Clean every complete acquisition run
   **including rest**, separately: remove each voxel's intercept and linear
   trend, then divide by its sample standard deviation (`ddof=1`). The fixed
   implementation is `nilearn.signal.clean` with original `runs`,
   `detrend=True`, `standardize="zscore_sample"`, `t_r=2.5`, no confounds or
   temporal filters. Constant residual signals stay zero under Nilearn's
   constant-signal convention. Only after cleaning remove `rest`. This is
   offline unlabeled normalization of the held-out run, not online decoding.
3. Leave one acquisition run out. Within the other 11 runs (792 volumes),
   compute the eight-group one-way ANOVA F statistic with `f_classif` and
   select the 500 highest-scoring features. Selection must not see any
   held-out labels or volumes. Use scikit-learn 1.8 `SelectKBest` ordering:
   stable ascending sort, take the last 500; exact tied scores favor later
   feature indices. Constant-feature NaNs rank as the smallest representable
   float64 value. Require at least 500 finite-F candidates and finite selected
   scores; otherwise stop, rather than substituting features. Pass selected
   columns to the classifier in ascending feature-index order.
4. Fit `SVC(kernel="linear", C=1.0, tol=0.001, shrinking=True,
   cache_size=200, probability=False, class_weight=None, max_iter=-1,
   decision_function_shape="ovr", break_ties=False, random_state=None)`.
   Other declared settings are `degree=3`, `gamma="scale"`, `coef0=0.0`
   (irrelevant to this linear kernel). Predict the 72 held-out volumes once.
   Repeat for all 12 runs. No hyperparameter search or sample exclusions.
5. Report each fold's correct-count/72 accuracy and their arithmetic mean.
   Equal fold sizes also make this the pooled accuracy. The nominal balanced
   chance level is 1/8; no above-chance test or population inference is asked.

The supplied stack uses NumPy 2.2.6, SciPy 1.17.0, scikit-learn 1.8.0,
NiBabel 5.4.2 and Nilearn 0.13.1. The explicit float64 recipe is the target,
not the older task's rounded accuracy. Equivalent implementations of these
operations are acceptable. ANOVA scores rank features; they are not valid
voxelwise significance tests for autocorrelated fMRI volumes.

## Outputs

Write to `${OUTPUT_DIR}` (default `/app/output`):

- `decoding_results.json`: `status`, `pipeline_id`, `cv_accuracy`, `n_samples`,
  `n_voxels` (mask before selection), `n_selected` (500), `n_categories`,
  `n_runs`, `chance`.
- `predictions.csv`: each non-rest source volume exactly once, with
  `volume_id,held_out_run,true_label,predicted_label`.
- `per_fold.csv`: one row per held-out run, with
  `fold,held_out_run,n_train_samples,n_test_samples,accuracy`. `fold` is the
  one-based ordinal of the held-out run in ascending run order.
- `selected_features.csv`: exactly 500 rows per run, with
  `held_out_run,feature_index,i,j,k,f_statistic`; no duplicate run/feature pairs.
- `run_metadata.json`: the fields of `/app/method_contract.json`, plus
  `status`, `n_samples`, `n_voxels`, `n_selected`, `n_categories`, `n_runs`,
  `n_full_volumes`, `cleaned_dtype` (`float64`). The template is public metadata,
  not a numerical answer. Additional fields are allowed.
- `findings.md`: a short account of the measured result, evaluation and limits.
  Do not claim a particular accuracy, circular-comparison gap, localization or
  population effect in advance. No special prose wording is required.

For a successful complete analysis, both JSON `status` fields must be strings
equal to `"ok"` or `"success"`; these are equivalent success labels. Neither
omitting the field nor reporting a failed/partial status is accepted. JSON
counts must denote exact integers, `cv_accuracy` and `chance` finite numbers,
and `pipeline_id` the string supplied in the public template. Preserve the
template's structure and values in `run_metadata.json`: hashes are strings in
the supplied filename-to-hash object, ordered arrays remain arrays, nested
settings remain objects, and strings/booleans/null retain their JSON types. The added
count fields must agree with the analyzed source, and `cleaned_dtype` is the
string `"float64"`. Extra metadata fields are allowed but do not override these
required fields.

CSV row order is immaterial. Equivalent integer notation is accepted for IDs
and counts. All reported numeric values must be finite; F-statistic tolerance
is absolute `1e-8` plus relative `1e-6`, accuracy tolerance is absolute `1e-6`.
Retain enough precision; labels and selected membership are exact, and ties
are decided from unrounded scores, not rounded CSV values.

A select-once comparison is not required. If discussed, it is a different,
label-leaking procedure and cannot replace the nested result; no predetermined
direction or magnitude of its accuracy difference is assumed.

On missing/mismatched inputs, invalid geometry/support or a failed fit, exit
nonzero and write parseable metadata/results with `status="failed_precondition"`
and a nonempty reason, plus `findings.md`. Do not invent outputs or silently
drop inconvenient samples/features. Public source availability does not settle
redistribution permission; preserve the source notices in the manifest.
