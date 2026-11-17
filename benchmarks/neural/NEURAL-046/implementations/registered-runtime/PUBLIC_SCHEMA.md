# Proposed prediction contract

The materialized PUBLIC_CONTRACT.json will supply the exact packet_fingerprint and the ordered roster of 2,795 rows `[asset_uuid, cue_event_row0, mouse_id, condition]`. No empirical roster is synthesized during source preparation. Source event rows are zero-based event-log indices, not contiguous cue ordinals. Preserve the exact asset UUID and index.

A complete submission has exactly these fields:

```json
{
  "schema_version": "neural046-single-predictor-v1",
  "packet_fingerprint": "<exact public SHA256 fingerprint>",
  "predictor_id": "one predictor name",
  "status": "complete",
  "predictions": [["<asset UUID>", 123, 0.25]]
}
```

The abbreviated row list above must be replaced by every eligible identity exactly once. Ordering is free. The file is UTF-8 JSON, at most 524,288 bytes. A prediction is a finite JSON number interpreted as binary64, including finite negative or inaccurate values. Boolean, null, NaN and infinity predictions are invalid. Duplicate JSON members, extra top-level fields, duplicate/unknown/missing identities and invalid Unicode labels are invalid. Predictor labels must be nonempty printable UTF-8 up to 80 bytes. Any finite integer literal is converted to the same binary64 interpretation as other JSON numbers; no arbitrary-precision input claim is made.

A nonzero numeric literal that would round to binary64 zero, such as 1e-999, is rejected before any private reference read. Ordinary finite binary64 rounding remains permitted. This input representability guard is separate from the explicit underflow status for derived squared errors of accepted subnormal predictions.

Whole abstention has exactly schema_version, packet_fingerprint, predictor_id, status=`abstain` and a nonempty printable UTF-8 reason up to 256 bytes. It has no predictions field. Abstention is not a numerical score and never reads the private projection. Per-row or per-animal abstention is not part of this component.

The primary result is equal-source-animal MSE, lower is better. Read the entire per-animal, condition, MAE/bias and baseline-comparison report. Native metrics use stored dF/F units; no percentage multiplier is applied. Numerical overflow or underflow is explicit and carries no finite primary score. Descriptive SD/SE do not supply inferential evidence. A low error does not certify training provenance, hidden-test generalization, biological mechanism or scientific understanding.

No full training-label packet is distributed by this proposed artifact interface. The development data and reference history are already exposed. Any later fold-isolated training interface must be separately specified and qualified.
