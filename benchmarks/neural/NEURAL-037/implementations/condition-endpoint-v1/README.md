# Recovered complete-condition endpoint

This package restores executable preparation and scoring source for the declared
six-acquisition, twelve-context endpoint. It does not supply recordings, prepared
targets, a participant runner, model results, or scientific qualification.
The recovered authored source and all derivation pins are in
[SOURCE_RECOVERY.json](SOURCE_RECOVERY.json).

The source is the Figure2 DE panel in [Zenodo record 18726362](https://zenodo.org/records/18726362).
All twelve `panelDE_expt{1..6}_F_{abc,cba}` tensors are required. Original ROI counts
are 251, 203, 139, 114, 257 and 168; there are 50 released trials per condition,
240 native frames for acquisitions 1–4 and 200 for 5–6. There are 1,132 ROI rows
and 2,264 query-row occurrences. These are six acquisitions, not six established
independent animals. Cell indices match between orders only within an acquisition.

## Recovered target and metric

Each target is a cell-by-native-frame trajectory obtained by averaging the finite
values over all 50 trials. `counts` preserves the number of finite observations
at each cell/frame. Mean zero with count zero is a placeholder, not a measured
zero. An entirely absent condition blocks the panel. Every original row and frame
requires a finite prediction, including unavailable target positions. The
historical source census reports seven wholly absent ROI rows per order; their
errors are null and their source absence is reported explicitly.

For each target cell, average squared error over its observed frames. Normalize
by the squared scale computed solely from the visible opposite-order condition
of that acquisition. The scale is the square root of the equal-cell mean of
within-cell population temporal variances of observed training means; no
between-cell offset variance, query-derived scale, epsilon or smoothing is used.
Average normalized cell MSE equally over cells with observations, then take the
square root. The primary is the mean of these twelve context normalized RMSEs.
The two orders have equal weight within each acquisition, so this is also an
equal-acquisition mean of the two order RMSEs. The code reports both levels plus
raw-unit context RMSE and per-cell support. It does not pool all cells or frames
into a single RMSE or take a root after averaging order MSEs.

The numerical reducer uses magnitude-scaled RMS at the frame and cell levels,
then applies the context-constant training scale. This avoids premature residual
squaring, subnormal squared-term division and overflowing intermediate sums.
Equal-order/context means are also magnitude-scaled. A nonzero required result
that cannot be represented is never replaced by zero. The original per-cell MSE
diagnostic must remain a finite, nonzero number for a nonzero error; if that
diagnostic overflows or underflows, or subtraction/RMS cannot be represented,
the whole panel returns `numeric_error` with no metric. This remains a disclosed
floating-point range limit rather than a change to the endpoint or support.

All physical timing and fluorescence-unit interpretation remain unresolved.
Native numeric source units are preserved; full-frame errors may include baseline
and optical artifacts. No stimulus-onset window, millisecond axis, trial-level
uncertainty or population confidence interval is implied.

## Input access and isolation

There are **eleven training conditions across six acquisitions**: the query
acquisition's opposite order and both orders from each other acquisition. There
are not eleven conditions within the query acquisition. The exact contract is
[input.schema.json](input.schema.json); query metadata has no target values or
target availability mask. Complete candidate outcomes follow
[prediction.schema.json](prediction.schema.json).

Reciprocal contexts expose each other's held condition as training data. An
executor must freeze the program before the first query and give each call a
fresh isolated state with only its selected context. Sharing conversation memory,
fitted state, files or source retrieval across calls invalidates this condition
holdout. `prepare.py` stores all contexts under the operator's private tree; that
whole tree must never be mounted for a participant. This package does not enforce
process or agent isolation.

Direct observation, typed viewer and interactive tool-assisted transports remain
undelivered. The recovered source is usable by a future isolated frozen-program
runner; it is not itself a qualified runner or evidence of direct understanding.

## Operator use

Use an existing environment with NumPy 2.2.6. The preparation authenticates the
entire 481,579,348-byte Figure2 NPZ at SHA-256
`652bddde5091218819a0fd4be2e1e7bed03d2cca67a631bb7d135ce7b314b5e6`
before decoding any selected tensor, then checks selected ZIP members and NPY
headers against [SOURCE_MEMBERS.json](SOURCE_MEMBERS.json). The source is external;
this package makes no network request and never unpickles object arrays.

The following commands are operator recipes, not executions performed by this
revision. Authentic preparation requires the program's separately coordinated
native-work protocol and resource allocation. Reuse matching accepted historical
preparation before planning another numerical preparation.

```sh
python prepare.py --source /operator/figure2_data.npz \
  --members SOURCE_MEMBERS.json --output /operator/fresh-prepared \
  --max-output-bytes 150000000

python score.py --public /operator/fresh-prepared/public/panel.json \
  --submission /operator/complete-submission.json \
  --private /operator/fresh-prepared/private/targets.json \
  --private-bytes TARGET_METADATA_BYTES --private-sha256 TARGET_METADATA_SHA256 \
  --output /operator/fresh-score.json
```

Keep targets, arrays, source receipts, predictions and full operator paths outside
Git. Retain the emitted file pins with the operator. The public panel and private
metadata must come from the same trusted preparation; their hashes establish
integrity, not independent authority. The scorer validates every submitted
context/cell/frame before invoking its private loader. Abstention produces no
subset score and does not invoke that loader. Malformed evaluator inputs fail
closed rather than yielding a favorable score.

## Integration and qualification limits

Canonical `task.json`, `understanding.v1.json`, the generated task README and the
legacy runtime declaration are unchanged. Integration should correct their
within-acquisition eleven-condition wording and replace the absent-scorer
uncertainty with the recovered endpoint above after independent review. The
historical runtime's private-grading authorization and native qualification are
not inherited. This recovery does not add a benchmark or establish a result.

The generated controls in `test_endpoint.py` cover source missingness,
training-only normalization, all twelve holdouts, exact geometry, equal-cell and
equal-order aggregation, identity joins, invalid submissions, abstention,
deferred target reads, full NPY transport and hash failures. They use invented
values on the declared dimensions and establish software behavior only. The
numerical controls include the independent reviewer's small-positive-error and
large-single-residual counterexamples, plus explicit range-limit failures. The
source reader itself has not been executed against authentic arrays in this
revision. See the external frozen handoff for the actual test outcome and costs.
