# Original Fig. 3 source-row endpoint

This additive operator component evaluates arbitrary item predictions against the original three-person, 1,500-sentence search panel. It authenticates the original OSF `data.tar` bytes before streaming the participant CSV, selects `797/841/880` and `lang_LH_netw`, requires every participant/item cell exactly once, and averages people within each item before Pearson correlation. It rejects missing, duplicated, nonfinite, relabeled or modify-panel observations. It neither executes candidate code nor reads the historical private reconstruction oracle.

The prior phase1 numerical component already scores arbitrary vectors against a saved reference. This addition supplies the missing direct path from the authenticated original release, including source item/condition checks and descriptive event-related response effects recomputed from source rows. The registered runtime and 184-handle claim-evidence roster are preserved. This component does not replace their remaining scientific obligations.

Original-finding reproduction and same-task improvement are separate first-class outcomes. This component supports the original Fig. 3 reproduction endpoint and a later matched improvement comparison; neither outcome is qualified by generated tests. Paired paper-plus-data and paper-plus-data-plus-author-code runs must share the same original panel, budgets and access policy. This component adds no task count and does not establish that paired delivery or either scientific result has occurred.

The cached MIT author-final manuscript reports Fig. 3 `r=0.43` across all 1,500 sentences and `r=0.30` across the 1,000 baseline sentences. Its Results and caption also specify averaging the three evaluation people. [Source binding](source_binding.json) gives the exact cached text hash, author-code revision, source archive pin and version limitation: this is author-final evidence, and numeric equivalence with the publisher's typeset version was not separately checked here. Rounded published values are not exact acceptance thresholds.

The evaluator returns candidate and released-author-prediction correlations separately, signed descriptive differences, condition and participant diagnostics, and Fig. 2b descriptive response means. Percent BOLD changes use `response_target_non_norm`, never z-scored responses. A zero raw baseline produces an undefined percentage. Released saved predictions are explicitly **not** an independently refitted author comparator. These descriptive effects do not reproduce the mixed-model statistics, blocked experiment, linguistic controls, uncertainty or complete-paper success rule.

Operator invocation, after authentic-data execution is authorized under the shared native protocol:

```sh
python3 endpoint.py --archive /operator/data.tar \
  --predictions /operator/frozen_candidate_predictions.csv \
  --output /operator/new_measurement.json
```

Predictions are UTF-8 CSV with exactly `item_id,prediction`, one finite prediction for each integer item ID 1 through 1500. Rows may be reordered. The CSV cap is 200 KB. Output creation is exclusive, so an existing measurement is not overwritten. No response arrays or sentence text are emitted. Original raw CSV bytes are parsed to select rows, but outcomes outside the target participants and ROI are never converted to numbers or included in a result.

Only generated software controls have been run in this revision; source metadata inspection was limited to the dictionary and CSV header. Authentic targets were not prepared or scored, author code was not executed, and no candidate/model call occurred. The public source responses and author predictions are historically exposed. Actual evaluation requires operator isolation and a frozen candidate before outcome access. The function itself does not enforce that boundary or establish a whole-registration improvement.

The small standard-library test suite checks analytically known pooling counterexamples, complete panel and stimulus identity, source archive rejection, prediction joins, undefined correlations, signed deterioration, exclusion before numerical conversion, and raw-versus-normalized units. Run it through the coordinator's shared test pool; do not treat generated fixtures as neural evidence.

## Current Pearson arithmetic repair

The current implementation subtracts a finite anchor before scaling each Pearson
input. This preserves representable variation near a common offset; opposite
finite extremes are halved only when their difference would overflow. Constant
columns remain undefined and all original population, grouping, aggregation and
scientific qualification limits remain unchanged. Historical source/provenance
records retain their original hashes; `CURRENT_SOURCE.json` identifies this
maintained numerical revision.

The new `test_centering_regression.py` controls use generated values and an
independent exact-rational/80-digit Decimal oracle. They do not qualify an
authentic reference, candidate run, reproduction or improvement.
