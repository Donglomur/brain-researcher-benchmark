# SenseFOG complete participant request/response bridge

This operator component connects the existing native LFP packet projector to the
unchanged protected primary and paired scorer. It supplies individual public
requests and collects opaque probability responses into the scorer's exact private
case identities. It performs no clinical preparation, candidate execution or
scientific evaluation, and does not qualify an access mode.

## Prepare and freeze

Python 3.11+ standard library is sufficient. Import `sensefog_delivery.py` and call:

```python
delivery = prepare_delivery(
    grid, policy, signal_metadata, aliases, read_segment,
    substrate="original_authorized_support", include_paired=True,
    max_cases=case_cap, max_packet_values=packet_value_cap,
    max_total_values=source_value_cap, max_output_bytes=byte_cap,
)
frozen_delivery_sha256 = canonical_sha256(delivery)
```

The grid, signal metadata, private aliases and reader have the exact existing
`signal-packets-v1` interface. The score policy has the unchanged
`primary-scoring-v1` interface; its classes, probability floor and uncertainty
settings must be prospectively authenticated/frozen by the evaluator. The bridge
loads both modules at their exact reviewed source hashes, and both preserve the
existing mapper dependency. No new clinical categories, units, grid, population,
lag rules, splits, metric or failure imputation are introduced.

`original_core` selects the native two-second core. It cannot be combined with
paired lag delivery. `original_authorized_support` selects the entire authorized
causal history and can add every supported lag packet. This restriction prevents
comparison of core-only original responses against richer-history transformed
responses as if information were matched. The selected substrate remains in the
private receipt and collected output.

Every original case receives a request, including cases whose selected observation
is unavailable. Such requests contain `observation_status="unavailable"` and
`observation=null`; they never fall back to a shorter packet or disappear. The
model can use only its otherwise permitted matched training evidence to respond.
The bridge neither relabels unavailable inputs as unevaluable nor supplies a prior
prediction itself. The protected label and prospective condition-failure policy
remain separate. An undefined/failed condition is not a successful subset score.

With paired delivery, only map-supported lags receive additional requests. The
complete private manifest still retains every original core, original history and
all twenty requested lag rows, with unsupported reasons. Zero supported lags yields
an empty paired prediction table, never a primary-case exclusion.

## Public requests and custody

The entire `delivery` object is **evaluator-only**. Persist it and its independently
stored canonical SHA256 before outcomes. Serve only an individual member of
`delivery["public_requests"]` to a participant. Each public request contains:

- `schema="sensefog_probability_request_v1"` and an independently generated
  opaque 128-bit `request_token`;
- the frozen `class_order`;
- `observation_status` and the exact existing native `observation` packet or null.

The private response bindings retain original case/person identities and lag
multiples; those fields are never in a public request. Public packet bytes remain
unchanged, including physical units, every channel, masks, relative time and
recipient case token. The existing packet montage needs the same semantic audit
for protocol/identity cues. Repeated recipient tokens can link related observations;
an external protocol must enforce its prospectively selected per-case isolation
and state policy. Do not give participants the whole private delivery, source
reader, targets, map, source paths, or scorer outputs.

Prepare once and reuse the same public request bytes and training evidence for all
matched direct, numerical, specialist and execution-mode conditions. Record each
condition separately. An external runner must enforce allowed tools, code freeze,
training folds, per-case state, budgets and exposure. This module neither calls a
model nor implements a network transport, filesystem sandbox, viewer or no-tools
boundary. Hashes establish receipt consistency, not actual equal exposure or neural
understanding.

## Collect complete outputs

Each response has exactly `schema="sensefog_probability_response_v1"`,
`request_token`, `request_sha256=canonical_sha256(public_request)`, and
`probabilities` in the request's class order. Echoing the request hash binds the
reported output to its entire frozen request; it does not prove how it was
computed. Response order is immaterial.

```python
collected = collect_responses(
    delivery, responses,
    expected_delivery_sha256=frozen_delivery_sha256,
    max_output_bytes=byte_cap,
)
report = score(
    grid, policy, protected_targets, collected["predictions"],
    max_cases=case_cap, paired_predictions=collected["paired_predictions"],
)
```

Use the independently frozen digest, never a digest freshly computed from a
modified or candidate-supplied delivery. Any changed packet, class order or private
mapping fails that binding. Missing, duplicate, extra, unknown, nonfinite,
non-normalized or failed responses reject the complete collection. No absent
prediction is imputed and no successful subset is returned. The probability
validator is the actual unchanged scorer's validator. The collected documents use
`sensefog_predictions_v1` and, when selected, `sensefog_paired_predictions_v1`.
The protected scorer remains the final authority on exact grid/target support.

All APIs are in memory and write no files. Input value/case bounds use the existing
projector, and byte caps reject complete output after construction. These are
logical limits, not OS memory/time bounds, hostile-input protection or a physical
read budget. Source reads can already have occurred when a later cap fails;
record failed attempts. The operator remains responsible for private persistence
and byte-faithful serving.

## Controls and remaining limits

Run `python3.11 -I -S -B test_delivery.py` from this directory. Generated controls
exercise twelve participants through the real projector and real scorer, exact
packet custody, all original cases, unavailable history, full paired support,
private-map tampering, missing/failed responses, request/class bindings, bounds
and caller mutation. Invented two-Hz fixtures are not clinical recordings and
these checks provide no model or biological performance result.

Still required are the complete original-release census, native signal reader,
clinical-clock reconciliation, authenticated calibration/montage and target
classes, boundary/exclusion policy, independent trained references, event metrics,
external participant isolation/transport and actual same-case evaluation.
Task readiness and count remain unchanged. Native interpretation and tool/program
construction remain separate outcomes on matched information; this bridge can
collect either and cannot infer which occurred.
