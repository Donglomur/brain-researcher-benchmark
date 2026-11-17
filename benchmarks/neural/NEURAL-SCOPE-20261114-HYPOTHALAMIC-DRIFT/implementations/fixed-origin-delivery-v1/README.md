# Fixed-origin event-history delivery

This component fills the gap between the existing complete-cohort scorer and a
single held-mouse prediction episode. It exports the other five or six mice's
21-session event counts/exposures within the held mouse's biological group,
the held mouse's sessions 1–9 counts/exposures, and the
declared acquisition-time context. It also joins all 31 held-mouse forecast
responses into the unchanged V3 scorer input. The original scorer and historical
definitions remain unchanged.

The representation is **qualified event counts and stable-state exposure**, for
tool-assisted investigation or frozen prediction programs. It does not deliver
raw fluorescence, direct neural interpretation, a viewer, a candidate executor,
or a fitted reference. Source qualification is still required before authentic
inputs can be exported. Generated controls are software evidence only.

## Operator use

Use Python 3.11+ with its standard library. The component verifies the existing
scorer SHA-256 before loading it. Run in an operator-owned directory (0700) with
independently chosen source paths and expected hashes. Do not run it inside a
candidate process: its input contains every mouse's future observations.

```sh
python3 -I -S -B delivery.py export \
  --targets OWNER_TARGETS.json --targets-sha256 OWNER_TARGETS_SHA256 \
  --context OWNER_CONTEXT.json --context-sha256 OWNER_CONTEXT_SHA256 \
  --held-mouse HELD_MOUSE_ID \
  --packet-output NEW_PARTICIPANT_PACKET.json \
  --binding-output NEW_PRIVATE_BINDING.json
```

Both outputs are create-only and mode 0600. Deliver only the participant packet
to its intended episode. The binding retains source hashes, producer/cohort
receipts, packet identity, held-cell identities and the exact within-group
`training_mouse_ids` roster for the evaluator. No full
target hash or receipt appears in participant input. Preserve any partial output
pair after a write failure; a partial pair is not completed delivery. Hash checks
and file permissions are not a process sandbox or biological authentication.

Each fold must run in a fresh isolated environment. **Never deliver all 31 packets
to one participant or share state between folds**: a different fold's training
set within the same group contains this fold's protected future. Mount only the one permitted packet,
use no network access to source targets, and collect the entire 12-session
forecast before scoring. Do not refresh any target or fit a shared model on all
31 trajectories. Cross-group training is outside this delivery condition. A
program must be fixed before evaluation; each fold's fitting
and method selection may use only its declared within-group training data and the
held sessions 1–9. Internal validation must use the same fixed-origin boundary.
This component does not enforce or attest those runtime conditions.

For matched permitted access conditions, reuse the exact same packet bytes.
Additional official code must be separately audited to remove data-bearing demos
and caches; this component does not distribute or audit that code.

The operator collects the 31 private binding objects into a JSON array and pins
that file independently. Collect the 31 participant forecast objects into a
second JSON array. Then run:

```sh
python3 -I -S -B delivery.py join \
  --forecasts COLLECTED_FORECASTS.json \
  --bindings PRIVATE_BINDINGS.json --bindings-sha256 PRIVATE_BINDINGS_SHA256 \
  --output NEW_COMPLETE_PREDICTION.json
```

Public forecast syntax is checked before private bindings are opened. Each
response must match its packet hash and every held neuron; all 31 mice, five
group totals and 1,661 cells must be present. The private training roster must
equal all other mice in that held biological group, with no held mouse or
cross-group substitution. The collection refuses mixed
source cohorts/contexts/producers. Its output is `hypodrift-prediction-v1`, ready
for the existing scorer's *numerical interface*, without establishing a valid
model trial. The private bindings must come from the operator, not the candidate.

## Exact context and response interfaces

Targets use the existing scorer's complete `hypodrift-targets-v1` schema. The
separate operator context document has exactly these keys:

```json
{
  "schema": "hypodrift-context-v1",
  "task_id": "NEURAL-SCOPE-20261114-HYPOTHALAMIC-DRIFT",
  "source_receipt_sha256": "LOWERCASE_64_CHARACTER_SHA256",
  "mice": [{
    "mouse_id": "AUTHENTICATED_MOUSE_ID",
    "sessions": [{
      "session": 1,
      "acquisition_seconds_relative_to_session9": null,
      "zeitgeber_hours": null
    }]
  }]
}
```

The example is schematic: enumerate every mouse and all integer sessions 1–21
in order. Relative seconds are actual acquisition times referenced to the
session-9 **acquisition**, not duration since the end of its recording. Known
times must increase strictly, be negative before session 9, zero at session 9,
and positive afterward. Zeitgeber hours must lie in [0,24). Use null for unknown
time metadata; the exporter never substitutes the baseline schedule for the
first recovery session. The source-qualified context producer must establish
these times independently of calcium activity and future state exposure.
Session ranges determine the registered baseline/acute/chronic phase labels.
No additional context keys, free-text annotations or state-duration fields are
accepted. Numeric allowlisting cannot establish that a trusted producer used
the correct biological clock.

The packet retains null observed counts/exposures, never converts missingness to
zero, and does not include free-text missing reasons. Those reasons remain with
the evaluator. Calibration arrays contain exactly 27 session-major slots;
training arrays contain 63. States are ordered `wake`, `NREM`, `REM`. The held
future contains only 12 context entries and the request for 36 values per cell;
future count, exposure and eligibility arrays are absent.

Each participant returns exactly:

```json
{
  "schema": "hypodrift-held-forecast-v1",
  "task_id": "NEURAL-SCOPE-20261114-HYPOTHALAMIC-DRIFT",
  "mouse_id": "HELD_MOUSE_ID",
  "packet_sha256": "SHA256_OF_EXACT_RECEIVED_PACKET_BYTES",
  "sessions": [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21],
  "states": ["wake", "NREM", "REM"],
  "cells": [{"neuron_id": "HELD_NEURON_ID", "log_rates": []}]
}
```

Enumerate every held neuron with exactly 36 finite nonnegative values in
session-major/state order, even where the unseen target is ineligible. Values
are `log1p(events/minute)`. Duplicate/foreign cells, omitted/extra keys, negative
or nonfinite values, and mismatched packet identities are refused. No future
eligibility feedback or score is part of this response path.

## Evidence and remaining limits

The construction follows the preserved registration's fixed sessions1–9 origin,
31-mouse evaluation, all-21-session training on other mice within the same group,
missingness rules and
conditional actual-time context. The original equal-session→state→neuron→mouse→
group scoring equation remains the sole endpoint. It is a proposed forecast
endpoint, not a reproduction of a published forecasting result.

The local source audit already records complete archive *metadata* for 651
mouse-session rows and the five groups' 1,661 column slots. This is stronger than
the older registration's metadata inventory, but does not authenticate ROI
correspondence, event values or MCH thresholds. The selected official source
includes GUI and event helpers; generic default options do not establish the
study's missing MCH configuration. No source download, authentic array read,
event extraction, model fitting or model trial is part of this component.

Required next scientific work remains authentic event/mask and cohort production,
actual clock qualification, protected fold execution, competent train-only
stationary/context/slow-drift reference selection, mouse-level uncertainty,
registration sensitivity and appropriate contamination controls. Retrospective
whole-study ROI selection and offline preprocessing remain conditional side
information. No benchmark readiness, direct/viewer capability, gain or SOTA
claim follows from this delivery code.

The generated controls exercise a complete invented cohort, exact held-future
and cross-group noninterference, within-group training roster binding,
explicit missing calibration, clock/field admission, complete
case collection into the unchanged scorer, foreign provenance/identity refusal,
and real create-only CLI delivery. Use the wave's reviewed test pool to run
`test_delivery.py`; do not run native data through that lightweight pool.
