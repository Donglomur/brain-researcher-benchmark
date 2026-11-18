# Static numeric behavior-to-ERP response adapter

This component prepares one complete supplied NEURAL-006 development case as
static numeric input and validates the returned predictions. The input direction
is **behavioral covariates to processed FRN/P3b amplitudes**. It does not present
neural waveforms and cannot establish native neural-signal interpretation.

The current task identifies direct-response collection as missing. This source
component addresses packet construction and response collection only. It does
not activate a registered condition, change task eligibility, score a new mode,
or establish that a model can use the complete presentation.

## Input and presentation

`prepare_case(case)` accepts the existing `neural006-case-v1` projection with one
of the33 exposed development people held out, the other32 training people each
once, and all supplied training and behavior-complete query rows. It checks the
observed-cohort roster/order, original row identities, finite paired training
labels, derived prediction-error features and disjoint train/query row support.
Each training person has1–180 supplied paired rows; there are1–180 query rows.
The maximum full case contains5760 training rows. No rows are sampled or silently
truncated. Bootstrap and reserved8 packet structures are unsupported.

The public JSON packet retains all11 declared numerical features and both
training ERP targets. It replaces administrative person and source-row labels
with case-local cluster/query tokens. The private binding retains original query
row identities and hashes of both the original case and public packet. Never
send that binding or the private held ERP trajectory to the participant.

The query shape permits no ERP target or target-missingness field. Training rows
are already paired-target-complete in the predecessor projection; this component
does not change that scientific selection. It also cannot independently detect
an omitted original eligible row, substituted numbers, permutation of source
targets, or a forged source projection. Original source authentication and
selection of the observed stage must precede this adapter. Case-local tokens are
administrative projection, not a proof of anonymization or absence of shortcuts.

The4MiB complete-packet cap is a serialization bound, not an established model
context allowance. A runner must verify complete context delivery and declare
the representation before evaluation; it must not shorten training or queries
to fit a model. Physical ERP scaling remains unresolved. Values retain the
original exported amplitude units without inventing a microvolt conversion.

## Collection

Trusted operator code uses:

```python
packet_bytes, private_binding = prepare_case(projected_case)
# Present exactly packet_bytes; retain private_binding outside participant access.
# After the participant's response is fixed:
record = collect(projected_case, private_binding, response_bytes)
candidate = record["candidate"]
```

The UTF-8 response is exactly an object with `schema`, `packet_sha256` and
`predictions`. The schema is `neural006-static-numeric-response-v1`, the hash is
that of the complete packet bytes, and predictions are `[query_token, FRN, P3b]`
rows. Every query requires one finite pair. Missing, duplicate, unknown, Boolean,
nonfinite or abstained predictions fail. The response may reorder queries;
collection restores the original source-row order. Duplicate JSON keys, malformed
JSON, extra top-level fields and responses over128KiB fail. A changed original
case or private row binding fails even if its altered values would otherwise
serialize as a valid packet.

The returned record binds packet, original case, response bytes and canonical
candidate vector by hashes. Hashes are identifiers, not external authenticity or
chronology proof. The operator must freeze the response before consulting private
truth. This pure in-memory adapter does not implement filesystem/process isolation,
provider access, a no-tools policy, timeouts, write-once storage or a session.

The existing paired-loss evaluator accepts two named modes, `frozen_program` and
`adaptive_investigation`. Do **not** place this output under either name. Adding a
direct condition to trusted grading/aggregation and qualifying its full33-person
execution require a separate explicit integration. The existing modes, scorer,
source closure, task definition and canonical readiness remain unchanged.

## Checks and source basis

`test_static_direct_response.py` contains15 generated controls. They cover complete
5760-row presentation, exact prediction support, identity/target/mask exclusion,
changed-case binding, source/query ordering, derived features, strict JSON,
Boolean/integer identity confusion, numeric overflow and input immutability.
Generated values test the implementation; they are not neural observations.
Run through the project's shared generated-test pool:

```text
python3 -I -S -B -m unittest discover -s . -p test_static_direct_response.py -v
```

The source basis is the current task-local `understanding.v1.json` and the
predecessor `broker-controls-v4/runtime/protocol.py` and `projection.py`.
`SOURCE.json` records their previously declared identities and limitations.
No authentic data, source-paper result, participant response or model trial was
opened or generated during construction. This component does not resolve raw ERP
event alignment, preprocessing/physical units, reference competence, calibrated
uncertainty, causal prediction-error decomposition or full benchmark readiness.
