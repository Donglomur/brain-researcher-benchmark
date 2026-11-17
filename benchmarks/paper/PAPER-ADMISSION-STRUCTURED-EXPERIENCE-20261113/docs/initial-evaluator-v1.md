# Initial owner evaluator

This additive package implements the complete finite scoring and split-preparation component for the registered structured-experience task. It constructs 390 per-session/fold/source-context fit units across all 13 sessions, validates the explicit eight-mouse join, builds an owner-only expected row universe, scores complete opaque-ID predictions, and reports the full 13×9 context-pair table. It is construction source, not an activated benchmark or a native Figure 6f reproduction.

The canonical task remains unchanged. No authentic neural archive, model, official decoder, candidate process or scientific campaign was run. No author code is included. All nine admission gates remain open, including native data/reference/baselines, rights, paper-only identifiability, population authentication and production isolation.

## Interfaces

`implementations/initial-evaluator-v1/evaluator.py` exposes:

- `validate_roster(roster)`: validates the exact 13 source session IDs, four mice per shaping stratum and session multiplicities `[2,2,2,2]` / `[1,1,1,2]`. Mouse IDs must come from independently authenticated mapping; no filename-prefix inference occurs.
- `build_expected(roster, secret, policy_sha256, development_assets_sha256)`: constructs source-restricted calibration/query plans and complete 40-bin private targets. The owner secret is at least 32 bytes. Separate HMAC domains produce opaque fit-unit/query IDs. All expected records and fit plans are **owner-only**, including their labels, times, contexts, trial IDs and mice.
- `score_predictions(expected, predictions)`: requires exactly one integer `predicted_bin` in `0..39` for every `query_id`, with no duplicates, extra IDs, missing rows, coercion or additional prediction fields. It reports losses in seconds squared.
- `compare_predictions(expected, candidate, baseline)`: independently validates each complete prediction set on the same expected universe; returns all eight baseline-minus-candidate mouse differences and a descriptive 256-sign two-sided tail fraction.
- `summarize_reproduction(roster, tables, method_route="source_concordance_0p5s")`: accepts a separately reconstructed, complete 13×9 source-workflow MSE table and reports within/across summaries, signed and absolute gaps, mouse summaries and the source-defined pooled session t-test. It applies shared cohort/provenance/trial-support validation, without imposing prospective per-fold context support or a prospective roster route on the original source workflow. It does not establish where the input table came from or assess paper comprehension.

For prospective preparation/scoring, the roster schema is `structured_experience_owner_roster_v1`, with `evidence_kind` set explicitly to `generated_engineering_control` or `owner_authenticated_source`, and `method_route` exactly `prospective_pointwise_0p5s`. Its `provenance` object contains SHA256 values for `behavior_sha256`, `unit_roster_sha256`, `trial_order_sha256`, `animal_mapping_sha256` and `inclusion_policy_sha256`. A hash or claimed evidence kind alone does not authenticate those inputs. Every session record supplies `session_id`, `mouse_id`, `shaping_group`, and source-ordered `trials`. Each trial supplies a unique session-local `trial_id`, one of `LS`, `SL`, `SS`, and `has_any_retained_event: true`.

All-unit-zero-event or unresolved trial support is a hard refusal. This flag does not reconstruct a behavioral trial roster from spike-bearing rows; a contained native reader still must prove that roster and all original unit/row accounting. Individual units without events in an otherwise supported trial are a distinct native preprocessing issue, outside this component.

## Fixed semantics

Loss is `(0.5 * min(abs(predicted_bin - true_bin), 40 - abs(predicted_bin - true_bin))) ** 2`. The scorer averages 40 bins within each trial, trials within each ordered context pair, the six cross-context pairs within session, sessions within mouse, then the eight mice equally. It retains all three within-context pairs, both four-mouse strata and every session/mouse result. The expected universe is reconstructed from the roster during validation, so rehashing a truncated universe does not make it admissible.

Ten folds follow `np.array_split` sizes and the supplied authoritative trial ordering. Each query fold requires all three test contexts and each calibration fold requires all three source contexts. The split planner retains roster order for calibration and includes only the selected source context. This is the prospective improvement plan. The author producer uses Pandas `Index.difference` for calibration; its ordering behavior is not claimed equivalent here. Raw source preprocessing, LDA fitting and scientific baseline construction remain unimplemented admission work.

Policy and per-outer-mouse development-asset hashes are included before held calibration use. The plan lists only seven development mice per held mouse and disjoint source-context calibration/query trials. These structural records do not enforce freeze chronology, arbitrary-candidate process/storage isolation, pointwise behavior, batch/order invariance, cache exclusion, cleanup or shared outer-case resource budgets. Runtime admission remains open.

The selected ephys producer/consumer explicitly use 0.5-second bins. The paper's nearest-1-second RNN wording does not resolve paper-only recoverability. Only the explicit prospective 0.5-second route and separately named source-concordance diagnostic run; paper-only/unspecified routes refuse at runtime. The source diagnostic must never become the sole paper-understanding score or be supplied as an owner recipe to the paper-only actor.

The reproduction diagnostic uses the original absolute across-minus-within session gap and SciPy's `ttest_ind(SL_only, standard, equal_var=True)` with 8 versus 5 sessions and 11 degrees of freedom. The signed gap remains separate. This reproduces a session statistic, not independent-animal inference. Degenerate/nonfinite statistics are reported as undefined rather than serialized as nonstandard JSON. Published rounding anchors are metadata, never fabricated expected results or newly selected tolerances.

The 256-sign diagnostic uses inclusive absolute tails (one floating-point ULP at a tie boundary). Its fraction is descriptive: overlapping leave-one-mouse-out development sets do not establish independent mouse differences or joint sign exchangeability. No p-value, significance, causal, competence or SOTA claim follows.

## Terminal use and validation

Core preparation/scoring uses Python 3.10+ standard library. The reproduction session p-value additionally requires an already available SciPy; construction controls used Python 3.11.6 and SciPy 1.17.1. These are observed engineering versions, not the author runtime. No dependency was installed. Tests that exercise SciPy explicitly skip when it is absent; a full validation run must use an interpreter where the dependency is already available.

From the package directory:

```sh
python3 evaluator.py prepare owner-roster.json frozen-policy.json private-expected.json
python3 evaluator.py score private-expected.json predictions.json score.json --baseline baseline.json
python3 evaluator.py reproduction owner-roster.json source-pair-tables.json source-summary.json --route source_concordance_0p5s
python3 -m unittest discover -s tests -v
```

The freeze JSON supplies `policy_sha256` and `development_assets_sha256` keyed by all eight owner mouse IDs. Predictions are a JSON list of `{ "query_id": "<64 hex characters>", "predicted_bin": 0 }` records. Every output is created with owner-only mode `0600` and exclusive file creation, refusing to overwrite an existing expected universe/result. Strict JSON loading refuses duplicate keys and nonfinite constants. Protect private expected artifacts outside candidate-accessible storage; this CLI is a trusted-owner tool, not a security boundary.

Independent generated controls cover circular wraparound, half-period loss, unequal context trial counts, unequal session counts, uneven ten-fold sizes, complete-universe rejection and descriptive sign ties. Lead controls cover the exact 390-unit/46,800-row minimum generated cohort, source restriction, missing populations, rehashed target omission, held-mouse leakage, unresolved method refusal, source session statistics and exclusive CLI outputs. Generated fixtures carry synthetic mouse/trial identities and test hashes; they are not data authentication evidence. Exact source pins and semantic mappings are in `provenance.json`; external reviewed run evidence accompanies the construction handoff.
