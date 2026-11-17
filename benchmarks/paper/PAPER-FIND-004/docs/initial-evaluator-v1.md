# Initial prior-localization prediction evaluator

This component evaluates safely exported predictions for a complete, declared subset of PAPER-FIND-004. It recomputes prior-decoding scores, pseudo-session inference and regional summaries, and compares neural predictions with matched movement predictions. It implements the generic scripts at author revision `380e7e68f31f9b55ec20e3f4863abec9eec25d30`. It is **not a finished benchmark, journal reconstruction, independent biological replication or qualified submission grader**. Canonical task identity and historical evidence remain unchanged.

The implementation uses only Python 3's standard library. It neither loads pickle nor acquires data, generates authentic pseudo-sessions, trains models, installs dependencies or contacts a service. All executed controls use generated numbers.

## Scientific scope and source discrepancy

The [primary paper](https://www.nature.com/articles/s41586-025-09226-1) and the [pinned author code](https://github.com/int-brain-lab/prior-localization/tree/380e7e68f31f9b55ec20e3f4863abec9eec25d30) disagree on important defaults. Investigation must resolve the executed paper configuration before a journal reference is qualified:

| Meaning | Journal methods | Pinned generic default implemented here |
| --- | --- | --- |
| Ephys estimator/CV | Lasso, nested interleaved 5-by-5 folds | Ridge, native RidgeCV inner selection, 50 outer folds |
| Null sessions | 1,000 | 200 |
| Ten-run summary | Median | Mean of run R² |
| Regional corrected R² | Mean of session corrections | Median real session score minus median session null median |
| Minimum sessions/region | One | Two |
| Minimum good units | Five | Loader ten; downstream regional filter five |
| Maximum reaction time | Two seconds | No ceiling |

The evaluator therefore emits `protocol_scope: pinned_generic_script_defaults_not_journal_reconstruction`. There is no automatic paper-mode switch or fabricated reference target. `provenance.json` records immutable source hashes and line mappings, including the native formatter, configuration and Bayesian target code. The author launcher's unused local estimator variable does not override `fit_target` configuration. Likewise, the native result's `n_folds` scalar can say five while actual outer partitions contain fifty; the adapter checks the actual indices.

The supported target is the `optBay` model's `pLeft` output, not the task's oracle `probabilityLeft` block value. It uses pre-stimulus `[-0.6,-0.1]` seconds relative to `stimOn_times`, reaction time at least 0.08 seconds, excludes no-choice trials and retains unbiased trials. Source Beryl region mapping excludes `root` and `void`; QC threshold is one. The source release family is `2023_12_bwm_release`; this name alone is not an immutable input-object manifest.

## Computation

1. Recompute each real/pseudo repeat's R² over the full concatenated out-of-fold scalar predictions. Do not average fold scores or average predictions before scoring.
2. Average ten run scores separately for each pseudo identity. The real ID is `-1`; null IDs are `1` through `200`. Set session null p to `(1 + count(null_mean >= actual_mean))/201`, retaining ties. Retain the median of the 200 null means.
3. For neural regional summaries, retain source downstream eligibility: at least five units and 250 trials per session, and at least two sessions per region. Report exclusions and insufficient regions explicitly. Compute Fisher's combined session p-value, population standard deviation, real-score median, null-median median, their difference, and fraction with session p below 0.05. Apply Benjamini–Hochberg to all eligible regions in the **declared subset**, with strict adjusted p below 0.01. This is not a paper-wide multiplicity claim. Fisher's source session-level procedure does not account for dependence between sessions from one mouse.
4. Require a motor comparator for every neural region-session and reject unmatched comparators. Compare only identical ordered actual trial IDs and Bayesian targets. Report each model's R² and pseudo p, plus the descriptive neural-minus-motor R². This does not implement the paper's complete embodiment, residual, causal or hierarchical analysis.

The seven motor features follow `prepare_motor`: normalized absolute wheel velocity (the source comment calls it acceleration, but the operation is absolute velocity), lick counts, left nose x-position, left and right whisker motion energy, and left and right paw-position norms. Source extraction applies session-wide z-scoring. The component scores supplied predictions and does not certify feature extraction or replace it with train-only preprocessing. Null seeds include region ordinal, so identical pseudo IDs do not prove identical targets across regions or motor.

## Input and usage

`evaluator.py MANIFEST.json PREDICTIONS.json --output RESULT.json` accepts safe JSON. `example_control.py OUTPUT_DIRECTORY` creates a complete generated fixture with 250 trials, one paired session, ten repeats and all 200 nulls. For example, from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/paper/PAPER-FIND-004/implementations/initial-evaluator-v1/example_control.py /tmp/find004-control
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/paper/PAPER-FIND-004/implementations/initial-evaluator-v1/evaluator.py /tmp/find004-control/manifest.json /tmp/find004-control/predictions.json --output /tmp/find004-control/result.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s benchmarks/paper/PAPER-FIND-004/implementations/initial-evaluator-v1/tests -v
```

The fixture's expected real R² values are one (neural) and 0.75 (motor), with zero null R², p=1/201 and descriptive difference 0.25. Its single neural session cannot pass regional admission. These values are algebraic controls, not observations about mice.

The fixture is the executable input example. Manifest requirements are:

- Exact task and contract hash, exact `SOURCE_PROTOCOL`, explicit evidence kind (`generated_engineering_control` or `native_prediction_export`), and `population_scope: declared_subset_not_paperwide`.
- `expected_cells`, with unique `(subject,eid,region,predictor)` keys, feature/unit count, complete ordered retained trial IDs, immutable input-object-manifest hash, target-generator receipt hash, and canonical-JSON target hash. Multiple probes must already be merged into the single native region-session. A session cannot be assigned multiple subjects.
- Explicit population-manifest and exposure-policy hashes, excluded exposed subjects, and canonical-JSON prediction payload hash. Every expected cell must appear exactly once. A present excluded subject is rejected.
- Prediction cells contain all 201 target arrays and all 2,010 run records. Each run supplies `pseudo_id`, `run_id`, scalar `predictions`, and `test_fold`, one held-out fold ID per ordered retained trial. Native KFold training indices are the complement of the named test fold. All fifty folds must be present and differ in size by at most one.

Canonical hashes use UTF-8 `json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)`. Hashes bind the supplied evidence, not the honesty of its producer or when an assessment was frozen. These materials belong under operator control; they are not candidate-accessible protected labels. Target arrays and predictions must be finite, with priors in [0,1]. A constant target is rejected because its R² is undefined; this is a documented stricter policy than sklearn's finite replacement. The component requires the same ordered retained trials for real and pseudo targets. Variable target masks and widefield/composite regions remain outside this version's scope and must not be silently intersected.

`export_native_run(fit)` converts an already-loaded trusted author fit dictionary, checks `idxes_train` against `idxes_test`, verifies complete outer coverage, and confirms `scores_test_full` against prediction-derived R². It never opens a pickle. `export_native_ephys(native, trial_ids_by_pseudo, input_objects_sha256=..., target_generator_sha256=...)` converts a complete single-region native result and audits the grid. The caller must map each pseudo's original retained mask to immutable original trial IDs. Native `mask` can contain an entire pseudo-mask list; selecting `mask[0]` for every pseudo is not valid. No automatic native-file loading is provided. A motor result can use the same per-run conversion and documented seven-feature cell schema.

## Verification and holds

The test suite includes independent algebraic vectors that distinguish pooled R² from average fold R², correct null ties/plus-one from alternatives, correct Fisher/BH, and the source's difference of medians from a median of paired differences. Full-grid generated tests reject missing cells, missing repeats, duplicate repeats, missing folds, exposed subjects, altered payload pins, oracle targets and mismatched motor trial order. Native-adapter tests reject train/test leakage and inconsistent reported scores. Independent review also checked Fisher/BH numerically against SciPy/statsmodels and directly exercised isolated pinned formatter functions on generated tables; it did not execute native fitting. The complete original formatter is not runtime-qualified: its pandas groupby assumptions failed under an installed pandas 3 environment.

Remaining holds include reconciliation of paper and generic-code configuration; authentic object and complete cohort manifests; author behavioral-model/pseudo-generation dependency closure; native extraction/fitting parity; independently executed empirical reference; target tolerances and meaningful difficulty; protected assessment and exposure policy; data/stimulus/component rights; paper-wide and widefield coverage; and a separately specified mouse/session-held-out improvement with clustered uncertainty. Public IBL recordings shared with FIND-005 do not become independent biological replication. No authentic reference, scientific result, target qualification or submission readiness is claimed.

The exact pinned [MIT license](https://github.com/int-brain-lab/prior-localization/blob/380e7e68f31f9b55ec20e3f4863abec9eec25d30/LICENSE) resolves the canonical record's contradictory code-license note for that snapshot only. It does not resolve data or third-party rights. Source files and paper content are not redistributed in this package; source receipts preserve their identities.
