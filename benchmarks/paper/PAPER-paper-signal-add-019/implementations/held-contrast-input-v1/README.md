# Original held-contrast candidate fitting inputs

This component supplies the missing numeric input/export join between the accepted author-law input plan and the complete Table 1 scorer. It keeps the nine original targets, both instructions, original global contrast omissions, per-participant fitting support, individual trial weights, separate behavioral/HMP populations and seconds/fraction fitting units. The candidate remains one arbitrary method.

`OperatorExchange` is a trusted-operator object. Its fixed targets, pending identity bindings and final joined predictions stay outside participant access. Only `next_packet()` output is a candidate input. It emits one `(target, instruction, omitted global contrast)` packet with all participants' fitting observations and required queries. A participant without an observation at that omitted contrast still receives a query, as required by the original global-grid predictions.

The implementation calls the accepted `author-law-production-v1.fit_jobs` for the current cell. Before removing the three redundant law labels, it checks each original job digest and exact equality of the remaining fitting operands across all three source laws. It does not choose one law's inputs if they disagree. Every training trial retains its place in the source order and its separate weight; no contrast means replace repeated trials. The original participant and trial identities map reversibly to packet-scoped aliases in `operator_binding()`.

Each public fitting row contains its scoped trial alias, contrast fraction, latency seconds and binary accuracy. The selected source access contract permits fit-contrast durations **and accuracy**. Training correctness is joined from the exact source B/H trial key; omitted-contrast correctness stays private. Raw response/side fields, other targets, event-time vectors, model endpoints, target-file hashes, original identities and fitted reference parameters are absent from public packets. This numeric exporter does not complete the paper/raw-EEG/author-code assistance manifests.

Responses use `decision-times-fitting-response-v1`, the exact case and packet digest, and one prediction per public query alias. Latencies are in seconds; the operator joins them into the existing scorer's milliseconds. Negative finite predictions are retained. Duplicate, unknown, omitted, nonfinite, wrong-packet or extra-field responses fail before state changes. Each complete first answer is final. `parse_response()` provides strict JSON parsing for a future transport, including duplicate-key and nonfinite-token rejection.

Full-data latency companions are mandatory in the existing candidate interface. They are a **separate phase**: `seal_held_predictions()` succeeds only after every original held-contrast query has a committed answer. Before that, no full-data packet is emitted. After the seal, the operator exports all full-data fitting rows and queries for each original target/instruction cell. Those later answers cannot replace held predictions. Candidate accuracy is optional; `predict_accuracy=True` freezes its requirement at construction and then requires complete accuracy coverage in the full-data phase only.

```python
# Trusted operator code; never give this object or targets to the participant.
exchange = OperatorExchange(
    targets, run_id="opaque-run-id", method_id="candidate-method",
    access_condition="paper_data", predict_accuracy=False,
)
packet = exchange.next_packet()          # Deliver this numeric packet only.
private_map = exchange.operator_binding()  # Keep in protected operator custody.
exchange.accept_response(parse_response(response_bytes))
# Repeat once per original held case, with fresh isolated participant contexts.
held_seal = exchange.seal_held_predictions()
# Only now repeat next_packet/accept_response for all18 full-data cells.
result = exchange.finish()
candidate = result["candidate"]          # Existing contrast-panel-v2 method schema.
```

The code enforces an artifact/API phase boundary, not OS or process isolation. Other held packets contain labels withheld by a different fold. A real deployment must supply fresh participant state, filesystem custody, frozen candidate code and independent execution/chronology evidence for each context. Operator-visible seals, aliases and hashes prove consistency only. They do not establish authentic source target identity, a competent baseline, source optimizer parity or protected evaluation. `finish()` returns operator-only joined outputs and reuses the existing held/full prediction validators; it assigns no score, success threshold, paper win or readiness promotion.

The paired assistance conditions retain identical numeric fitting observations; their frozen access-condition labels and response bindings differ. Official code delivery remains a separate unresolved manifest. Original Table 1 versus Results discrepancies, all126 reference findings, stronger-comparator selection and the joint18-cell improvement policy remain unchanged.

Generated controls exercise the actual exporter, response join and accepted plan/validators, with no authentic arrays or fitting. The new maintained command is:

```sh
python3 -I -S -B -m unittest discover \
  -s benchmarks/paper/PAPER-paper-signal-add-019/implementations/held-contrast-input-v1/tests -v
```

The sole integrator must register this command and its exact dependency closure. Existing predecessor test suites are not rerun by this component. No authentic input acquisition, model trial, solver process, source-law fit or scientific performance measurement has been conducted here; original resource requirements remain unmeasured.
