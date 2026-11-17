# Original MEG selected-feature producer and classifier

This implementation connects the complete released regional time series to the
selected **CS↔PFC maximum-squared-DTW-barycenter** result and the existing original
fold scorer. It preserves all94 participants, the task-irrelevant first1000ms
ON window, and the face-versus-object endpoint. Four categories are retained
through source feature QC; only then are face/object rows selected for fitting.

The publication's **64.3% accuracy, 9.4 percentage-point fold SD** is a descriptive
anchor. This package does not turn that rounded number into a pass threshold,
authenticate the historical folds, or establish a reproduction/improvement.
It adds no benchmark ID and does not replace the current task policy.

## Three executable steps

Run from this directory using an existing environment. Fresh output directories
are mandatory; incomplete attempts are retained. These commands describe the
source path, not permission to start scientific execution under a local study.

```sh
python producer.py prepare --archive /path/to/empirical.zip --output /path/to/prepared
python producer.py features --prepared /path/to/prepared --output /path/to/features
python producer.py classify --features /path/to/features/FEATURES.json --output /path/to/classification
```

1. **Prepare:** authenticate the complete220609250-byte source ZIP against its
   SHA256 and publisher MD5, require all94 original CSV members and their complete
   coordinate support, parse finite float64 values, and select exactly0..999ms.
   No interpolation, resampling, feature calculation or model fitting occurs.
   Each output is `[4 categories,4 regions,1000 times]`; all94 NPY files contain
   1504000 values (12044032 total bytes including ordinary NPY headers).
   CSV validation checks the full -500..2000ms grid, all three relevance types,
   and all four regions. Only the two previously censused wholly absent target
   groups are allowed: CB027/False and CB042/face. Irrelevant rows cannot be absent.
   Inputs are **known-category epoch averages**, not label-independent trials.
2. **Features:** validate every prepared file's identity and NPY allocation
   geometry before loading. For each of376 category blocks, z-score every ROI
   using sample SD (`ddof=1`), then linearly detrend. Compute the original six
   unique DTW-barycenter pairs in source traversal order, retaining the symmetric
   cache convention and whole-SPI failure boundary. CS↔PFC receives `[PFC,CS]`.
   The scalar is `nanmax(barycenter**2)`, not squared DTW distance. Full successful
   extraction entails2256 native DBA calls. Source Data/preprocessing failures
   abort; a per-SPI solver exception becomes an explicit null with diagnostics,
   which the original feature QC handles. No proxy, shorter signal or alternate
   solver is used.
3. **Classify:** apply original four-category QC and mean imputation, then fit
   balanced L1 logistic regression (`C=1`, `liblinear`, seed127) in ten
   participant-grouped folds. Return188 held-out probability rows with the full
   observation/fold join, per-fold model/scaler records, original mean fold
   accuracy and population SD, and separate fold/mean/SD AUC companions. The
   primary score is delegated to `original-fold-score-v1/score.py::score_cell`.

`features` requires installed **tslearn==0.6.3** and preserves its native default
DBA implementation: length1000, arithmetic-mean initialization, equal weights,
30 maximum iterations, tolerance1e-5, one initialization, unconstrained DTW.
NumPy and SciPy are required for preparation/feature calculation; scikit-learn is
required for fitting. PySPI itself need not be installed: this source follows
its selected Data/Barycenter route without loading the broader incompatible
YAML or changing the selected calculation. No dependency is installed by this
package. Runtime versions are recorded; historical environment parity remains
unverified. Author declarations include NumPy2.2.4, SciPy1.15.2,
scikit-learn1.6.1, and tslearn0.6.3. The generated controls used NumPy2.2.6,
SciPy1.15.3, and scikit-learn1.6.1; tslearn was unavailable.

## Original normalization and ordering

Source mean imputation and feature screening use the complete four-category
block before pair selection/CV. The mixed-sigmoid scaler fits location and scale
on each training fold, using the source expression `(x-median)/IQR/1.35` or the
mean/SD branch if IQR is zero. Its final min/max normalization uses **each
transform batch's own extrema**, including the held-out batch. This transductive
behavior is preserved and recorded. Replacing it with training extrema is a
method change. Exactly10% missingness is neither imputed nor excluded by the
source's strict inequalities; remaining nonfinite values fail explicitly.

The producer declares roster order followed by each CSV's first category
occurrence. This is reproducible **newly declared order**, not the original
unsorted filesystem `glob` order. Default fitting realizes
`StratifiedGroupKFold(10,shuffle=True,random_state=127)` on these rows; seed identity
alone does not prove historical fold identity. A supplied JSON participant-to-fold
mapping can instead be used with `--folds` and a required `--fold-evidence`
description. Coverage, group disjointness and labels are checked; evidence text
is recorded, not automatically authenticated. The lower-level `source_oof` API
preserves explicitly supplied duplicate-category multiplicity with unique IDs;
the selected producer/CLI enforces exactly one row per participant/category.

Candidate predictions can be evaluated by the existing `score_cell` on the
identical admitted observation ledger and realized folds. Reference reproduction
and candidate improvement remain separate outcomes. A candidate comparison must
freeze its method and reference population/splits, retain the original broader
feature-search exposure, and follow the root task's scientific comparison policy.
This package does not invent an improvement margin or an uncertainty test.

## Validation and remaining scientific holds

Generated controls cover complete94-person preparation, exact source masks and
axes, source failures, safe NPY preallocation, selected-feature math/order,
original classifier behavior, and integration with the original scorer. The
analytical DBA seam tests identical normalized series, where the barycenter is
known; it **does not run or validate native tslearn**. Generated classifier fits
are engineering controls, not results on authentic data.

```sh
python -B -m unittest discover -s tests -p 'test_*.py' -v
```

Native library execution and complete authentic preparation are not established
by those tests. Additional unresolved requirements include the publication's
v1/v2 empirical-release and corrected-supplement join; original row multiplicity,
ordering and realized folds; authenticated historical native runtime; full-
precision original feature/distribution and fold-output joins; source comparator
execution; and a justified paired, selection-aware improvement decision rule.
The author's generic result-file glob does not by itself settle Raw/Abs output
multiplicity. This implementation explicitly selects Raw under the adopted
endpoint, and does not claim that this resolves the historical file join.

File hashes protect internal consistency, not adversarial provenance: prepared
arrays and their binding must be sealed by the evaluator after authenticated
preparation. Whole-release hash verification establishes the identified release,
not equivalence to the publication's historical inputs. The old nested246-feature
evaluator remains an extension; it is not this original-task reference.

Primary source links, source pins and exact semantics are in [SOURCE.md](SOURCE.md).
