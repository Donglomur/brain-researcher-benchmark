# SBIND endpoint arithmetic

This owner-side component calculates all original **metric types** needed by
SBIND Tables 2–3: fourteen WFCI1 behavioral MSEs, four WFCI2 binary F1s,
brain-pixel neural MSEs for either modality, and final-state fUS trial accuracy
for two or eight directions. It supplies the missing numerical scoring kernels;
it does not supply an original-fold evaluator or a new benchmark.

The complete task remains both widefield assays (248 and 412 trials, 49,008 and
38,927 frames), five folds per assay, and all thirteen fUS sessions (nine
two-direction and four eight-direction sessions), ten folds per session. The
source SBIND baseline, DPAD/CEBRA/TNDM and source ablations remain required
comparisons. No cohort, split, mask or comparator is selected here.

## Owner API

Import `endpoint_kernels` from this directory. Every function accepts a
separately frozen ordered `support` of nonempty unique sample IDs, and target
and prediction sequences of `(sample_id, values)` pairs. IDs must identify the
same original **target** frame or trial, including session context where needed.
Every support ID must occur exactly once in each operand; missing, additional
or repeated rows fail. Row order may differ. There is no missing-prediction
filter, automatic temporal shift, trial concatenation or data-derived mask.

* `wfci1_behavior_mse(..., channel_ids=...)` requires all fourteen channels and
  returns per-channel MSE, in the frozen target normalization's squared units.
* `neural_mse(..., brain_pixel_indices=...)` requires every flattened
  `(1,128,128)` field in channel/row/column order. The owner supplies the original
  brain mask as unique pixel indices; every field value is checked, including
  excluded pixels. The result preserves each selected pixel's MSE and identity.
* `wfci2_behavior_f1(..., channel_ids=...)` requires four binary target values
  and four pairs of class scores in `(0,1)` order. Argmax selects the first class
  on ties. Positive-class F1 uses `2TP/(2TP+FP+FN)` with zero denominator mapped
  to zero, and retains each channel's TP/FP/FN counts.
* `fus_trial_accuracy(..., directions=2 or 8)` accepts one row per successful
  trial. Targets are `(29, class_index)` and predictions `(29, class_scores)`:
  offset 29 denotes the final state of the original 30-frame trial. The class
  score vector has two or eight entries. Accuracy is correctly classified
  trials divided by evaluated trials. Training's three supervised samples are
  not three evaluation votes. The owner authenticates class encoding; this
  function does not infer it from target values or convert between axis codes.

`MetricResult` contains metric, denominator, ordered-support SHA256, output IDs,
values and optional confusion counts. It contains no individual targets or
predictions. It is an in-process owner API, without process isolation, protected
storage, publication or candidate access controls. Authentic targets must stay
on the owner side; only allowed aggregates may be released under the future
access protocol. Do not pass authentic target objects to a participant.

## Source fidelity and limits

The pinned author `eval_prediction` computes outputwise MSE and binary F1 with
argmax/zero-division conventions. The direct categorical fUS encoding is also
present in the pinned Doppler preparation helper. These are static source
findings, not recovered table call traces. This independently written code
requires explicit numeric types instead of inferring task semantics from NumPy
dtypes. Continuous values and scores must be finite Python ints/floats; binary
labels may also be booleans. Array owners need trusted adapters.

MSE uses binary64 compensated summation of squares relative to each output's
largest residual, averages these normalized squares, then restores the scale.
This avoids prematurely rounding each divided square to zero when the final
MSE is representable, while also avoiding overflow in individual squared errors.
It holds one validated pair of rows at a time plus output accumulators;
the supplied operands remain caller-owned sequences, and the identity index
cost is linear in sample count. It is not NumPy bitwise parity or a measured
native-performance implementation. Unrepresentable subtraction or final MSE
fails explicitly; a final value below binary64 range can still underflow.
No floating-point success tolerance
has been declared from these controls.

Exact acquisition/session identities, paper folds, preprocessing, original
temporal/pixel masks, final-state output provenance and table aggregation remain
unrecovered. IDs/offsets and hashes check declarations, not a model's causal
history or source authenticity. In particular this component does not compose
the neighboring prospective whole-trial helpers into a claimed original split.
Per-output values are preserved without inventing channel/pixel/fold/session
weighting, mean±SEM, uncertainty or a full-vector paper-win rule. Reproduction,
an admitted candidate comparison and current SOTA remain separate qualifications.

## Generated validation

Python 3.11 standard library only. Run `test_endpoint_kernels.py` through the
approved shared test pool. The twelve methods use hand-counted arithmetic,
complete generated 128×128 fields, reorder/missing/duplicate row controls,
channel/class-size failures, final-state checks and malformed operands. Decimal
reference controls cover representable subnormal means, changes in residual
scale and finite means whose individual squared residuals would overflow.
No authentic array, checkpoint, author implementation or model is executed.
Earlier `SOURCE.json`, `VALIDATION.json` and `HANDOFF.md` retain the original
eight-check release and its source hashes. Current consumers use the updated
dependency binding; the numerical correction does not revise that history.
New task count: zero.
