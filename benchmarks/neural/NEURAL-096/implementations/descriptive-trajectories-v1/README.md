# Descriptive Set–Go trajectory interpretation

This component asks for a compact, explicitly descriptive comparison of prior
contexts in the already prepared **204-trial, 54-unit** Haydn recording. It
preserves the original **150 training / 54 validation** labels, all six recording
segments and every response-effector/direction cell. It does not substitute the
older 177-trial pre-Set reconstruction.

The [scientific contract](CONTRACT.json) binds the
[prospective summary selection](ROOT_SELECTION.json). These are new benchmark
summaries, not an original paper metric. The broader task's calibrated uncertainty
and complete scientific qualification remain unresolved.

## What participants estimate

There are 48 split × recording-segment × effector × direction cells. For each
prior group, divide each trial's bin counts by that trial's actual seconds of
exposure, then take the **equal-trial mean**. Pooling counts and exposure would
weight trials differently and is not this estimand.

For every supported cell, take **long-prior minus short-prior** mean rates and
report eight numbers:

- Four signed means, one for each fixed five-bin quarter of the 20-bin interval.
- Four RMS differences over the same five bins and all 54 units.

Both are in spikes/s/source unit (Hz). The evaluator retains complete signed
54×20 differences, but participants do not need to transcribe thousands of
entries. Signed quarters distinguish temporal reversals that RMS and a single
whole-interval mean cannot. These eight summaries still do not identify complete
unit-level geometry.

RMS is a nonnegative descriptive distance. It can be positive under a population
null because cell means vary; it is neither a noise-corrected distance nor a
significance test. A positive effect is never required for success.

An absent prior group yields **unsupported**, with explicit counts and null
numeric answers. Every cell remains in the response. The three empty cells in the
combined preparation do not determine split-specific missingness. No aggregate
prior effect is computed by dropping unsupported cells.

## Two access conditions, identical aggregate information

The matched viewer and programme conditions receive the **same complete
prior-specific 54×20 mean rates and support metadata**. They do not receive
computed differences, private reference summaries or individual-trial responses.

`view.render_cell(observation, cell_id)` supplies a typed SVG view for an exact
cell ID. It shows both priors, all source-unit labels, all phase bins, counts,
missing groups and one shared colour scale across the whole observation. It
does not accept arbitrary analysis code. Numerical programmes receive those same
aggregate values directly. Additional raw-trial access would be a separate
information condition; it is not quietly included here.

SVG colour quantization and human/model visual precision can affect numerical
estimation. Both arms use the same continuous error report; there is no widened
viewer tolerance. This source implementation has not established authentic raster rendering,
provider image delivery, participant execution or model performance.
An observed gap would include representation precision as well as access to
computation; it would not by itself isolate a pure tool-use effect.

## Scientific conclusions and scoring

The answer includes complete support counts/status, a complete/partial/no-supported
conclusion, the scope `descriptive_phase_summary`, and an uncertainty rationale:

- `single_exposed_animal_session`
- `assignment_and_dependence_unverified`
- `recording_segments_not_randomized_blocks`

The corresponding uncertainty status is `not_qualified`. Six observation
segments are not verified randomized assignment blocks or independent animals.
No confidence interval, permutation or bootstrap inference is manufactured from
them. Additional design evidence or explicitly justified model assumptions would
be needed for a separate inferential outcome. Phase alignment is conditioned on
the eventual response and changes speed representation; it does not support
prospective interval prediction or causal conclusions.

`score.grade` reports mean and maximum absolute numerical errors, per-cell
errors, support/count correctness and scientific-qualification correctness
separately. Missing a supported estimate prevents a numerical aggregate; correctly
marking unsupported cells cannot produce a false zero score. A numerical average
describes prediction error on supported reference cells, not an aggregated neural
effect or a completed uncertainty result. There is no combined binary win.

## Operator route

Use Python with NumPy from this implementation directory. The exact original
external `full-set-go-v1` packet is required; it is not bundled here.

```sh
python3 -B prepare.py prepare \
  --packet /path/to/prepared-v1 \
  --output /path/to/new-descriptive-delivery
```

The loader authenticates the earlier 3,688-byte preparation receipt and both
packet files. It checks ZIP expansion and exact numeric array layouts before
allocation, without pickle. Preparation writes `participant/observations.json`
and its manifest separately from `private/reference.json`, the expected answer
and the operator receipt. Keep the entire private directory operator-owned and
outside participant delivery. Freeze the printed completion SHA256 **before**
exposing observations or accepting submissions.

```sh
python3 -B prepare.py grade \
  --delivery /path/to/new-descriptive-delivery \
  --completion-sha256 OPERATOR_FROZEN_COMPLETE_JSON_SHA256 \
  --submission /path/to/submission.json \
  --output /path/to/new-grade.json
```

The completion hash is supplied by the operator, not obtained from a participant's
submission. File commitments establish consistency with that frozen preparation;
they do not themselves prove honest execution or hostile-code isolation. The
operator API is not a participant sandbox, viewer transport or model provider.
Failed partial output is preserved and cannot be reused as a fresh preparation.
Even a partial `COMPLETE.json` filename is not evidence of completion: the
successful operator-returned hash and the exact closed inventory are required.

Exact saved-packet authentication does not retroactively establish an independent
reread of every original NWB spike or independent recovery of the 14 extra unit
identities. The initial source-only revision opened no authentic packet and used
generated checks. The subsequent fixed preparation and independent arithmetic
audit verified the saved outputs for 204 trials, 54 units and all 48 comparison
groups; 27 groups had both priors and 21 remained explicitly unsupported.
[VALIDATION.json](VALIDATION.json) preserves that preparation/arithmetic record.
[DELIVERY_VALIDATION.json](DELIVERY_VALIDATION.json) records a later independently
reviewed local exercise of 48 SVG views, nine fixed grader controls and three
typed-selector refusals. The 51-file observation bundle is an operator package
containing both numeric programme data and SVG views; native participants must
receive only a separately enforced typed visual interface, not that whole bundle.
[DELIVERY_SCOPE.md](DELIVERY_SCOPE.md) distinguishes this local verification from
unqualified raster/provider transport, participant isolation and inference.
Deterministic programmed arithmetic does not establish learned neural understanding. No model was fitted
and no AI participant was run. Canonical task readiness, historical calibration
and uncertainty declarations are unchanged.

## Generated controls

```sh
python3 -B -m unittest discover -s . -p 'test_*.py'
```

Controls include differing exposures, signed temporal reversal, cancellation
across units, unsupported cells, complete output requirements, false uncertainty,
answer withholding, common viewer scales and source/array integrity boundaries.
They use generated fixtures, never biological substitute results.

## Attempt capture and private grading bridge

[ATTEMPT_SCOPE.md](ATTEMPT_SCOPE.md) documents arm-specific materialization,
typed observation requests, one final-answer capture and the operator-only grading
bridge. The final receipt hash returned at capture time must be retained
independently and supplied to later verification and grading; hashing the current
receipt later does not provide that commitment.

[ATTEMPT_VALIDATION.json](ATTEMPT_VALIDATION.json) records 40 generated checks:
20 adapter checks, 17 bridge checks and three integrations using the real adapter
with the scientific grader stubbed. Native requests expose only the sanitized
index and a selected PNG; programme requests expose the same index and the
byte-identical numeric aggregate observations. These are local API/integrity
checks, not evidence of operating-system isolation, provider image transport or
AI performance. Configured request/byte ceilings are engineering limits, not a
validated model-budget policy. A separately accepted three-render generated raster probe established
limited local runtime and fixture legibility. That historical probe documented
small labels and gridlines crossing unsupported-panel text. The current renderer
places the missing-support annotation above the grid on an opaque background;
a generated preview confirms that label is unobstructed. Previously materialized
images retain their original rendering and source bindings. It establishes neither authentic
48-image semantics nor provider delivery or model readiness. The scientific summaries, numerical
error report and uncertainty limitations above are unchanged.
