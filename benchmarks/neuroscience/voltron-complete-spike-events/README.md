# Voltron complete spike-event scoring

This standalone scientific source component belongs to the existing draft `NEURAL-DISC-20261114-VOLTRON-SPIKES`. It adds no benchmark ID and requires only the Python standard library. It contains the event scorer, complete input/output contract, and invented tests. It contains no optical or electrical recordings, private answers, animal identities or model weights.

`event_score.py` implements inclusive five-millisecond, one-to-one maximum-cardinality spike matching; complete movie/core/cell coverage; optical/electrical validity intersection; grouped animal-fold validation; and paired candidate/reference metrics. `CONTRACT.md` specifies the interface, aggregation and scientific limits. `PUBLIC_SOURCE_PINS.json` pins these source files. All matched-role predictions are admitted before the trusted evaluator's single private-reference callback.

Run the invented controls from this directory:

```sh
python3 -I -S -B test_events.py
```

The 34 test methods include an independent exhaustive matching oracle over 1,024 tiny event-set pairs and complete fictional twelve-cell/seven-group cases. These are source controls, not additional benchmarks or biological results.

The public API is `grade(public, predictions, private_loader)`. The loader belongs to the trusted evaluator, never the candidate. Actual signal extraction, physical clock conversion, animal mapping, strict serialized-artifact parsing, candidate isolation, baseline generation and resource admission must be supplied and qualified separately. This library does not launch programs, read datasets, authenticate biological evidence or grant permission to run an experiment.

The reported seven animals versus six filename tokens remain unresolved. Complete input/rights/extraction checks and independently qualified baseline results are still required. Successful source tests do not establish full-paper reproduction, neural understanding, improvement, SOTA, submission readiness or native containment.
