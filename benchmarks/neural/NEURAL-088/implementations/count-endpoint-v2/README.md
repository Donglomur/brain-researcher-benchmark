# Current synapse-count endpoint

This standalone Python-standard-library scorer implements the current NEURAL-088 proposed numerical endpoint. It restores useful executable grading code to a task that previously shipped only a runtime declaration. It does not authenticate a source panel or deliver any participant observation mode. Historical definitions, sources, predictions and grading results remain unchanged.

The primary is absolute anatomy-plus-in-vivo Poisson deviance, lower is better. For target count `y`, submitted expected count `mu`, and an operator-frozen positive floor `f`, pair loss is `2 * (max(mu,f) - y + y*log(y/max(mu,f)))`, with the logarithmic term zero when `y=0`. Average pair losses using frozen positive sampling weights within each presynaptic neuron, then average those neuron means equally. Supply `sampling_weight: 1` only when uniform weighting is the frozen design. Sampling weights, floor, eligibility and roster must be fixed before query outcomes or submissions; they are not candidate choices.

Two complete candidate views are required: `anatomy` and `anatomy_plus_in_vivo`. The operator supplies independently fixed reference predictions through a separate argument. Reports retain the signed fixed-reference anatomy-minus-joint contrast, fixed-reference-joint-minus-candidate-joint contrast, and a clearly descriptive candidate self-contrast. Weakening the candidate's anatomy arm cannot improve the primary. Arithmetic cannot verify that reference fitting was independent: training/validation-only fitting, feature equivalence and model freeze receipts still require independent operator review.

The interface requires one prediction for every exact roster ID in both views, forbids duplicate directed pairs, duplicate/missing/extra predictions, booleans, negative/nonfinite rates and noninteger targets, and loads targets only after public submission validation. Operator roster/reference/target errors raise; malformed candidate views return `invalid_submission` without invoking the private loader. Positive finite values that overflow the deviance yield `valid_unscorable_arithmetic`, with null affected values; no rows are dropped and that result must not be ranked as a complete score.

## Interface

`grade(rows, candidate_views, fixed_reference_views, load_private_counts, rate_floor=...)` is the pure Python entry point. `rows` is the **operator-only** roster. Each row has exactly:

```json
{"edge_id":"opaque-pair-key","pre_id":1,"post_id":2,"projection":"A-B","sampling_weight":1}
```

Endpoint IDs are signed-int64 administrative identities used for alignment and grouping, never participant predictors. A public prediction view contains only `{"edge_id":"opaque-pair-key","mean":0.25}` rows. The two-view object maps the exact names above to those lists. The target callback returns `{"edge_id":"opaque-pair-key","count":0}` rows with integer counts from 0 through 2^53. No authentic targets or example scientific predictions are bundled.

The command-line interface takes an operator protocol object with exactly `rows`, `rate_floor` and `fixed_reference_views`, a separate candidate JSON file, a private target JSON list, and an operator-only output path:

```sh
python3 -I -B scorer.py --protocol /operator/protocol.json \
  --candidate /operator/candidate-views.json --targets /operator/targets.json \
  --output /operator/report.json
```

All these example paths are placeholders. Keep real protocols, endpoint identities, references, targets and reports outside Git and outside participant mounts. The report includes a canonical protocol SHA-256 for subsequent receipt matching; this digest is not evidence of a pre-query freeze. The CLI rejects duplicate JSON object keys and nonfinite JSON constants. Exit 0 means arithmetic completed; exit 2 denotes an invalid submission or unsupported arithmetic. Other operational/input errors raise. This is an operator scoring function, not a sandbox, participant runner or feedback service.

## Numerical lineage and controls

The near-saturated deviance series comes from the cached reviewed NEURAL-088 precision successor, pinned in `SOURCES.json`. It prevents subtraction cancellation from turning small nonzero losses into perfect zeros. The remaining formula retains the predecessor's binary64 behavior: strict continuity/monotonicity at the series branch boundary is not claimed. Positive weighted reductions use 80-digit Decimal accumulation to avoid overflow and weight-normalization underflow in intermediate products, then return binary64 results.

`test_scorer.py` exercises hand-derived unequal-group/unequal-weight outcomes, candidate-baseline manipulation, negative/null independent contrasts, permutation-invariant key alignment, private-loader order, malformed candidates/operator inputs, explicit flooring, Decimal precision comparisons, extreme weighted reductions, overflow rejection and real CLI reads/writes on generated temporary fixtures. It imports only this implementation and uses no empirical data.

## Remaining scientific work

The original 6,691-pair, 21-presynaptic historical query panel has not been reauthenticated. This implementation accepts a supplied frozen roster and does not generate a new split, silently rebuild that cohort, or assert endpoint/spatial disjointness. Exact materialization, root/nucleus correspondence, measured-functional joins, reconstruction quality, negative eligibility, weights and reference procedures remain operator dependencies. The historical source describes outcome-dependent cohort ascertainment; this arithmetic does not remove it.

The additional contract diagnostics—count-stratified residuals, zero/nonzero calibration, overdispersion, training-only negative-binomial sensitivity, matched functional shuffle and prespecified endpoint/spatial uncertainty—remain unimplemented and unqualified. Mean absolute count error is reported on the submitted means; the positive floor applies only to deviance.

A processed correlation feature does not establish raw-neural understanding. Direct observation, typed viewer, case-adaptive investigation and frozen-program interpretation remain separate undelivered conditions. One mouse does not establish animal-population replication; observed zero counts are not certified biological nonconnections, and anatomical synapse counts are not physiological efficacy. No authentic-data preparation, model trial, training or scientific qualification occurred here.

## Complete paired direct/program assessment

[PAIRED_ACCESS.md](PAIRED_ACCESS.md) documents the operator-only `paired_access.py` comparison. It validates both candidate access modes against the same complete declared 6,691-pair/21-presynaptic roster before opening targets once, retains the unchanged count endpoint and fixed references, and reports signed direct-minus-program contrasts. Matching operator information bindings are declared equality, not evidence of actual delivery or access enforcement. No authentic cohort, participant runner or direct/program competence is qualified.
