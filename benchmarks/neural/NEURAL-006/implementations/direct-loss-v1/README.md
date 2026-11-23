# Bound static response scoring

`direct_loss.score_response` grades one complete static numeric response for
NEURAL-006's observed development condition. It connects the existing packet
collector to the independent paired-loss arithmetic while retaining the distinct
condition name `direct_numeric_behavior_to_erp_encoding`. The predicted quantities
are hidden FRN/P3b amplitudes from behavioral covariates. A score here does not
measure direct interpretation of neural waveforms.

The trusted operator first commits the exact response bytes, then calls:

```python
score = score_response(projected_case, private_binding, response_bytes,
                       private_projected_held_rows, reference)
```

The existing static collector verifies the originally presented case and packet,
all query tokens, finite predictions and response bytes. Its observed33-person
roster and complete supplied training/query presentation remain required. Only
after collection succeeds does scoring inspect the complete180-row held
trajectory, rebuild the behavior-complete query and paired target mask, and
recompute equal-person training means and variances. Missing targets never excuse
a missing prediction on a behavior-complete query. Every reference arm
`mean`, `N`, `R`, `V`, and `J` remains present.

The output reports separate FRN and P3b MSE, MAE and training-variance-normalized
MSE, plus binding hashes. It never places a direct response under `frozen_program`
or `adaptive_investigation`. The existing paired `score_case` entry point still
requires exactly those two programme modes. Both APIs share one arithmetic
implementation. This companion loads authenticated source bytes of its two
dependencies; changed dependencies require a reviewed pin update.

This is a source component for one supplied development case. It provides no
full33-person aggregate, reserve-eight condition, provider transport, no-tools
enforcement or prediction-commitment mechanism. Hashes identify supplied bytes;
they do not establish authentic source observations, timing or reference
competence. The operator remains responsible for source custody, prior reference
audit and response commitment before access to private targets. Private held
trajectories, bindings and detailed results must not be exposed to participants.
Task eligibility and registered runtime selection are unchanged.

The generated controls exercise hand-calculated paired losses, missingness,
unequal training-row counts, case binding, complete response support, source pins
and the unchanged legacy mode requirement. They use invented values and do not
establish model performance, physical ERP scaling or scientific qualification.

Source basis: [the current understanding contract](../../understanding.v1.json),
[static collection](../static-direct-response-v1/README.md) and
[independent paired arithmetic](../paired-loss-v2/README.md).
