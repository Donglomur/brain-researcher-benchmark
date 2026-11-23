# Matched DUNL event comparison

This operator interface compares a candidate and a supplied reference using the
[unchanged historical event evaluator](../dunl-historical-events-v1/README.md).
Both use the same operator-selected owner, ordered complete panel and caller
mode. The report retains missed-event and false-event coordinates separately,
with candidate-minus-reference differences and the disclosed schedule control.
There is no scalar paper-win score or inferred significance threshold.

This is the **current-code default** profile: 30 training and 20 test trials,
eleven allocated channels, one kernel and 576 event bins. All 550 rows remain;
train and test results stay separate. The ten selected neurons versus eleven
allocated channels, original Figure 4F operating point, biological grouping and
publication-specific execution remain unresolved. A reference submission is not
automatically authenticated author-model output or a competent baseline.

The original endpoint counts predicted positive bins in the union of inclusive
target neighborhoods. Several predictions may hit one target. It averages row
fractions and clips the complete mean hit at one. This component computes exact
rational differences after that clipping, preserving the empty-prediction rule.
It does not replace those conventions with one-to-one matching or average clipped
row recalls. The operator selects either `standard` or `group` for both arms;
group mode preserves the existing mathematical positive-support union, without
claiming floating-point norm parity.

## Run a comparison

Python 3.11+ and the standard library suffice. Owner and submission schemas are
the same as the historical endpoint. The owner digest is selected by the trusted
operator, and both submissions must match every ordered identity and dimension.
The shared public context alone is insufficient to identify targets: the same
owner object is used for both evaluations, and the CLI binds its full file digest.

```sh
python3.11 -I -S -B paired_events.py \
  --owner /absolute/operator/owner.json \
  --owner-sha256 OPERATOR_SELECTED_SHA256 \
  --candidate /absolute/operator/candidate.json \
  --reference /absolute/operator/reference.json \
  --mode standard \
  --output /absolute/operator/new-comparison.json
```

The CLI uses the existing bounded regular-file reader and creates a mode-0600
output exclusively. It includes the SHA-256 of all three captured input files;
the Python `compare` API additionally reports canonical in-memory value hashes.
The two digest conventions are labeled separately. Ordered row-count hashes
support comparing saved computations without adding row diagnostics to the new
report. Keep reports and owner inputs outside participant access. These checks
do not enforce a sandbox, code-access isolation or a protected-feedback policy.
No candidate code is executed.

The dependency is checked against the published 9,780-byte historical evaluator,
SHA-256 `ddfa29861f8d942b4dd37bac4ca8163c084e7be476bdf5ddee2e31c40b619df0`.
Its [source pins](../dunl-historical-events-v1/SOURCE_PINS.json) retain the original
method evidence and the pinned author implementation. This component changes no
historical source, endpoint or task contract.

## Interpretation and checks

Negative differences mean lower missed/false fractions under the source
convention. They do not imply lower absolute event counts or one-to-one event
recall: denominators can change, and multiple predictions can hit one target.
A tradeoff remains a two-coordinate result. Neither lower
values nor a perfect public-schedule score demonstrate neural understanding,
publication reproduction or scientific improvement. The report explicitly leaves
authentic cohort, reference training lineage, source runtime parity, effect rule,
biological uncertainty and scientific qualification unestablished.

`test_paired_events.py` uses generated panels to check full-row arithmetic,
clip-after-mean behavior, standard/group distinctions, incomplete or reordered
reference refusal, target binding and exclusive file output. These are software
controls. No authentic data, fitted model, paper score or participant attempt is
provided by this source component.
