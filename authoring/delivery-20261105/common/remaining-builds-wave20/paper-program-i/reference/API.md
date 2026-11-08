# Independent reference API

This operator-only implementation follows the accepted `DESIGN.md` (29,818 bytes,
SHA-256 `818b294b51b7ef9f700334eb9cc62f31be0352a96c8f01ed662976c3dd14f569`).
It contains no author code, neural input reader, model loader, filesystem API,
partition construction, automatic tuning or grading. Source implementation
authorization does not activate authentic fitting or scoring.

`encoder.py` uses Python and NumPy only. Model objects contain JSON-compatible
metadata and primitive float64 arrays. The owner's safe serialization layer
must validate and encode these; no pickle or object arrays are supported.
The module itself performs no model serialization. Models, training data,
permutation receipts and reference source remain operator-private.

## Calls and strict legal views

* `configs(profile)` returns 14 configurations for `M` and 15 for `C`, `CM` and
  `CM-shuffled`. Records contain `id`, `representation`, `penalty`, `profile`.
  IDs are `context_average`, then `raw_ridge_1e+06` through
  `raw_ridge_1e-06`, then `spline_ridge_1e+06` through
  `spline_ridge_1e-06`, using the seven accepted penalties. The list is already
  in exact-tie preference order: context-average, raw, spline; larger penalty
  first. `configuration_rank(profile, id)` returns that rank, without selecting
  a model or consuming any errors.
* `fit(train_X, train_Y, sample_weights, schema, configuration,
  label_provenance=None)` fits one configuration jointly for independent cell
  columns. `train_X` is a nonempty list of feature-record dictionaries;
  `train_Y` is finite `[examples,cells]`; weights are finite positive
  `[examples]`. Its return is `{'metadata': ..., 'arrays': ...}`. The same
  matrix factorization can fit all cells; it is still one logical fit per cell
  and configuration. Caller logs per-cell configurations, partitions and times.
* `predict(model, record)` returns a finite vector of every ordered cell for
  one local physical-trial/time/modality record. `predict_with_info` also
  returns `{'context_fallback': bool}`. Evaluation has no state, feedback,
  query-target access or dependence on other query records.

The schema contains exactly `profile`; additionally, `movement_features` is
required for M/CM/CM-shuffled and must equal `list(MOVEMENT_FEATURES)`.
For C/CM/CM-shuffled it also contains `categorical_vocabulary` and
`target_time_grid`. M schemas contain neither time grid nor vocabulary.

Movement records contain exactly `movement`, a map with all 47 names from
`MOVEMENT_FEATURES`: channels position_0, position_1, velocity_0, velocity_1,
speed, each at taps m4,m3,m2,m1,0,p1,p2,p3,p4, then movement_duration and
movement_length. Tap spacing is 0.1 seconds; source clock/units and extraction
are the owner's admission responsibility. Coordinates are numeric or `None`/
NaN when missing. Infinity, additional fields and absent keys refuse.

C records contain exactly `time`, `measured_delay`, `categories`. Combined
records contain those plus `movement`. Categories contain exactly the four
names in `CATEGORIES`: planned_delay, reinforcer, first_reward_order,
delivered_outcome. Each category is a string token from its complete, ordered,
source-census vocabulary, including levels absent from training. These tokens
describe legal task fields, never biological identity. Delay is a continuous
numeric/missing coordinate, separate from categorical planned delay. Time is
finite and must exactly equal one coordinate in the full actual selected
source grid; nominal window boundaries are not accepted substitutes. M records
have no time, context, native index, transport token or trajectory identifier.
Unknown fields fail instead of being silently ignored.

The owner strips transport IDs before this API, authenticates the full census,
all source aliases and mandatory fields, and supplies equal-trial/equal-time
weights after the authorized training-only purge. This API cannot infer
physical trial grouping from deliberately masked feature records. All weights
must be positive; zero weights cannot silently remove required support.

## Frozen numerical conventions

Ridge variants first impute continuous coordinates using observed training
values and renormalized supplied weights. All-missing training coordinates
have imputation zero, no spline columns, and stay numerically zero even if a
query has an observed value. Every continuous coordinate has a missingness
indicator, including the mandatory always-finite time coordinate's constant
zero indicator. Constant zero indicators contribute no effective parameter.

Raw columns are completed continuous values, missingness indicators and full
one-hot category indicators, in that order. Weighted training means and
population SDs standardize them; exact constant columns use scale one and an
exact constant mean. Expanded columns retain all raw standardized columns.
Each non-time continuous feature adds its own cubic basis with observed
training min/max and unweighted empirical type-7 1/3 and 2/3 quantiles;
duplicate/end-point interior knots are removed. No imputed/query values
enter knot estimation. Evaluation clips to training knot endpoints while
retaining the unclipped raw standardized coordinate. Constant/all-missing
training features add no spline basis.

Time adds 12 cubic basis functions: eight equally spaced interior knots from
the actual complete source grid's first/last selected coordinates, with four
copies of each endpoint. This structural grid is frozen before fitting; time
knots do not use query labels. The independent Cox-de Boor implementation
includes a right-endpoint correction and partition-of-unity controls.

C adds time-basis × literal categorical-indicator interactions. M adds only
movement splines. CM/CM-shuffled add both, plus time-basis × raw standardized
M-column and literal categorical-indicator × raw standardized M-column
interactions, including standardized movement-missingness columns. There are
no movement all-pairs interactions. All completed expanded columns are again
standardized with training-only weights. These conventions resolve the design's
type-7 versus weighted-scaling distinction explicitly; they add no query inputs.

Targets stay in released units. Weights are normalized to sum one. An
unpenalized intercept is the weighted training target mean. The fit uses SVD
of the weighted centered/scaled design, with factors s/(s²+lambda), minimizing
weighted MSE plus lambda times squared non-intercept coefficients separately
for each cell. There is no row-count multiplier, target variance normalization,
pseudoinverse truncation or extra fit. All seven positive penalties are exact
design values. Failure to solve or a nonfinite result refuses the complete fit.
The declared normal-equation residual criterion is
norm(Xw.T@(Xw@B-Yw)+lambda*B)/max(1,norm(Xw.T@Yw)) <= 1e-9.
Reported numerical rank is diagnostic and never changes the solution.

Context-average models use the supplied weighted training means separately
for every discrete stratum/time/cell. A query stratum entirely absent from
training uses the all-training mean at that same time, with fallback flagged.
Every required time bin and every seen stratum's complete time support must
exist; partial trajectories refuse instead of inventing interpolation or
partial-stratum fallback. All four continuous/movement fields remain subject
to the profile view validation even when this competitor ignores movement.

## Whole-trajectory shuffled labels

CM-shuffled uses the identical combined feature family but receives already
reassigned targets. `fit` requires a minimal operator-private attestation
`{'kind':'whole_training_trajectory_reassignment','receipt_sha256':<64 hex>}`.
It cannot authenticate the permutation from a hash alone: the trusted owner
must bind that receipt to the exact supplied targets and training partition.
No inverse mapping, seed or source identities are embedded in the model.

`apply_training_permutation(target_blocks, source_for_destination, strata)` is
an optional trusted in-memory adapter. Its input is
`target_blocks[modality][opaque_training_trial] -> [time,cells]`. All modalities
must have the same authenticated physical-trial support. The explicit mapping
must be a complete bijection confined to equal five-token strata (acquisition,
reinforcer, planned delay, first-reward order, delivered outcome). It copies
whole trajectories with the same permutation across cells and modalities,
never independently rearranges time/cells, and returns reassigned blocks,
the exact private receipt and minimal attestation. Singleton identity strata
are explicitly ineffective. Each modality must have consistent full time/cell
axes within this acquisition. Seed construction, receipt retention and fresh
inner/outer-training permutations belong to the owner. This API has no query
target arguments; the owner must ensure supplied blocks are training only.
Neither full receipts nor minimal attestations belong in candidate exposure.

## Controls and limits

`control_checks.py` runs bounded invented controls in RAM only, including the
analytic weighted ridge solution, complete configuration sets, strict view
masks, type-7 knots, source endpoints, spline partition of unity, imputation,
context fallback and paired-modality whole-trajectory reassignment. The first
run passed 35 checks with four invented all-cell fits. After identifying a
constant-column floating-point normalization edge case, `constant_control.py`
tests only that numerical delta with one additional invented fit; the broad
controls were not repeated. Both source hashes and receipts are retained.

The owner performs full inner-support error pooling, per-cell representation/
penalty selection, deterministic exact-tie ordering, final refits, isolation,
safe I/O and hierarchical grading. No authentic reference fit, model/scoring
run, native parity, full-cohort feasibility or scientific competence is claimed.
