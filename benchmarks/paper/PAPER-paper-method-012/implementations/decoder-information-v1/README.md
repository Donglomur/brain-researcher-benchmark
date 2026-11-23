# Explicit CA1 decoder information replay

This standard-library component fills the selected endpoint's missing prediction-to-information calculation. It joins held-out decoder labels to separately supplied operator targets, constructs confusion counts, and replays the pinned CA1 driver's per-fold `shuffSub` calculation. The existing pair-information and Poisson components address different quantities.

The component is **unqualified**. It does not train a decoder, authenticate the original support, resolve preprocessing or partitions, reproduce a figure, or establish improvement. The source status and selected endpoint remain unchanged. Inputs and resulting confusion records belong on the operator side because they contain or reveal protected targets.

## Source and mathematical scope

The pinned [CA1 driver](https://github.com/panzerilab/MINT_figures/blob/a90eb535205c2df668e4e59c8f8d748c37fa815e/Figure2/CA1.m) requests held-out predictions and test indices, then computes information separately in each test fold. It selects `shuffSub`, 30 MI permutations and no rebinning. Both linear and RBF kernels receive real responses and two conditional-response shuffle realizations. The conditional-response shuffles remain distinct from the 30 MI bias-subtraction permutations. This component expects their predictions; it performs neither neural-response shuffling nor model fitting.

The [MI branch of shuffle_subtraction.m](https://github.com/panzerilab/MINT/blob/f0d43b68a6e8541f56b3ca67d9af5a7a0e76acbb/src/core_functions/BiasCorrection/shuffle_subtraction.m#L346-L390) permutes both inputs separately and subtracts the mean shuffled plugin value. The component computes discrete plugin information from counts, `sum p(t,p) log2(p(t,p)/(p(t)p(p)))`, and subtracts the average of 30 replayed null values. It adds no pseudocounts, quadratic correction, clipping or significance test. Negative corrected values are retained. Both input permutation streams must be supplied explicitly; no distributionally equivalent replacement stream or Python RNG is substituted for native draws. Exact native numerical parity and historical draw provenance remain unverified.

The pinned driver selects two outer folds; the [paper](https://doi.org/10.1371/journal.pcbi.1012934) and appendix specify five. The caller must declare either source-described fold count and provide all memberships, separately for every decoder run. The component does not choose between them or require common folds across runs. The driver also swaps its final shuffled-kernel storage assignments; callers must supply computation-kernel identities with separately justified provenance, not blindly import those field names. No alias correction is performed here.

## Interfaces

`evaluate(support, submission)` accepts JSON-compatible objects. Both carry `schema_version: 1` and `task_id: PAPER-paper-method-012`. The generated fixture in `test_decoder_information.py` is a complete example; its identifiers, classes, folds and null maps are engineering controls.

The operator support contains:

- `data_kind`: `generated_engineering_control` or `operator_prepared_unqualified`.
- `outer_fold_count`: explicitly 2 or 5; `label_order`: all twelve distinct integer spatial-class labels in the operator's declared order, including classes absent from a fold. No encoding is inferred.
- Eleven `sessions`, each with a unique `session_id`, an explicit `animal_id`, `sample_ids`, aligned `targets`, and six `runs`. The seven-animal count is checked; identities remain unauthenticated.
- Each run identifies `kernel` (`linear` or `RBF`), `condition` (`real` or `conditionally_shuffled`), and `conditional_shuffle` (0 for real; 1 and 2 for shuffled). Its `folds` contain unique `fold_id`, ordered `sample_ids`, and 30 `null_orders`.
- Each null order has independent `prediction` and `target` permutations, encoded as zero-based indices relative to that fold's ordered sample IDs. Each run's folds must partition every session sample exactly once. Duplicate random permutations are allowed because native random draws can coincide.

The submission contains `support_sha256` from `digest(support)` and the complete `folds` collection. Each submitted fold has `session_id`, `kernel`, `condition`, `conditional_shuffle`, `fold_id`, and `predictions` records with `sample_id` and integer `label`. ID joins preserve support order even if predictions arrive out of order. Missing, duplicate or foreign predictions/folds are rejected. A matching hash binds content; it does not prove a support freeze time, authorized provenance or independence. The operator must maintain that boundary externally.

Output retains the original fold and run coordinates, class order, target-row/prediction-column confusion counts, all 30 null confusion matrices and plugin scores, observed plugin information, and corrected information in bits. It also binds both input objects. It emits **no aggregate**: authentic reduction/SEM semantics, field reconciliation, reference vectors and agreement criteria remain unresolved. This arithmetic component cannot admit a benchmark score or select a strongest comparator.

```sh
python3 decoder_information.py support.json predictions.json information.json
python3 -B -m unittest -v test_decoder_information
```

Generated controls cover exact binary-channel information, empty-class retention, confusion orientation, both null streams, negative correction, complete 11-session/7-animal and kernel/condition/shuffle support, two- and five-fold declarations, independent run memberships, protected-support binding and malformed coverage/maps. No authentic CA1 data, models, native MATLAB runtime or scientific result is involved.
