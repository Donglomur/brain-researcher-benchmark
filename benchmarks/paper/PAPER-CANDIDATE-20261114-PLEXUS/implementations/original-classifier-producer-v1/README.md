# Original Figure 4 classifier stage

This component fills the gap between the existing original-fold reconstruction and the prediction scorer. It produces author-method probabilities from supplied, ordered, post-preprocessing feature matrices. It is **unqualified construction source**, not an authenticated author baseline or a complete paper reproduction.

The original [Figure 4 source](https://github.com/pgrosjean/plexus/blob/69ccecbcc00f8462c8ce2a9d699be09f4c53ed66/figure_scripts/Figure4/figure_4.py) uses whole-panel standardization and two reciprocal elastic-net logistic classifiers. The explicit settings are retained. Both fits and predictions must succeed before that guide contributes either fold. The imported split component retains the original asymmetric balancing and source-known exclusions.

`produce(census, features, expected_census_sha256, expected_features_sha256)` imports scikit-learn only when called. Calling it with real inputs requires a separately admitted execution; no authentic input preparation or model fit was performed in this construction. There is no executable CLI. The operator owns protected inputs, source authentication, process/resource limits, prediction commitment and atomic result storage.

The `census` has the existing `plexus-figure4-observations/v1` schema. The `features` object has:

- `schema: "plexus-figure4-features/v1"`, `census_sha256` and the census's `preprocessing_receipt_sha256`;
- exactly four `panels`, one per original family/donor combination;
- per panel: `family`, `donor`, complete ordered `observation_ids`, `matrix_source_sha256`, `dtype` (`float32` or `float64`), and a rectangular numeric `values` matrix;
- `upstream_stage: "source_post_tvn_and_required_aggregation_pre_classifier_scaler"` for each panel.

These declarations and pins are consistency checks, not proof of preprocessing. Other numeric types require explicit reconciliation. Preserve the original floating dtype: casting all inputs to float64 can change the classifier computation. The runtime record includes library versions and every resolved estimator parameter; equal explicit arguments do not prove equality with the historical environment.

The output retains observation-level scores, all guide-level fit states, failure stage and type, convergence warnings, iteration counts, complete panel counts and metadata-known exclusions. A failure in either reciprocal fold discards that guide's pending scores and marks the declared plan incomplete. `assemble_submission` refuses incomplete producer output and validates full joint author/candidate coverage through the unchanged scorer. It does not authenticate the producer receipt. Warnings are retained without introducing a new exclusion rule. A metadata-known one-class reciprocal skip is inherited from the splitter; this component does not recreate the author's wasted first fit in that case.

No numerical preprocessing is implemented here. Upstream aggregation, typical-variation normalization and the manual-feature normalization before WT selection remain separate source obligations. The registered task's final-paper/archive correspondence, original complete roster, independent baseline, common assistance profile, protected evaluation and panel inference policy remain unresolved. There is no scalar paper-win decision, changed endpoint or readiness promotion.

From this component directory, generated controls run with:

```sh
python3 -B tests/test_producer.py
```

The tests reuse the existing original-fold fixture and use recording scaler/classifier substitutes. They perform no statistical learning. The two dependency files are hash-pinned in `SOURCE.json`. Integration must register this new component and its test command; ordinary test discovery does not currently enroll it.
