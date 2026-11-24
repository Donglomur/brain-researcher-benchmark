# Prepared observation pages for NEURAL-066

This source component supplies the task-specific observation presentation missing
from the current NEURAL-066 implementation. It reads the existing public
`neural066_candidate_input_v3` diagnostic packet and returns escaped HTML tables
through five typed actions. It also checks a complete same-case probability
response without reading targets or computing a score. This makes permitted
observations inspectable without participant-written numerical code.

It is **not an activated direct or restricted-viewer benchmark**. The original
programme, controller, scorer, source inventories and historical qualification
remain unchanged. The output records the packet's original `source_mode`; it
does not relabel frozen-program or adaptive results as unaided interpretation.
No authentic data, model answers, reference fit or native execution was used to
qualify this component.

## Exact input and information support

An operator supplies the existing diagnostic `INPUT.json` and its independently
trusted byte count/SHA256, plus exactly the referenced `train.npy`, `query.npy`,
`TRAIN_LAYOUT.json` and `GEOMETRY.json`. The pin must come from the prepared
capture, not be accepted from a participant who may rewrite it. The component
opens only these fixed names, refuses symlinks and checks descriptor hashes,
complete layouts, source dimensions and current-case identity. It never opens
private source maps, raw recordings, targets, reference outputs or other cases.
Metadata-only pages validate metadata; a values page additionally authenticates
the entire selected matrix, including its header, extent and every finite value.

All six original arms are supported: TIMING, EOG, NEURAL_PRE, NEURAL,
NEURAL_POST and SHUFFLE. EEG retains all 61 neural channels and MEG all 306;
EOG retains its actual declared channel list, with no substituted schema.
Channel windows retain all 25 means and their channel-major order. Pages show
half-open 20-ms bin coordinates and the original normalized 2D layout when
available. These coordinates are layout positions, not physical locations.
The producer does not encode channel physical units; pages state that gap and
show exact native stored float32 values without invented unit labels or scaling.
TIMING uses its declared seconds/indicator units and has no spatial geometry.
This does not resolve the authentic MEG EOG geometry or unit-documentation gaps.

Every training sentence/group, label and original positive weight remains
available through the same interface. Query pages omit labels and private group
identities. Both complete layouts must partition their matrix rows without gaps,
overlaps, omissions or duplicate IDs. Page limits bound each response but never
change the offered support, downsample, crop or substitute an average. The last
feature/key is reachable just like the first. A page limit is not a claim that a
human or model has consumed the complete observation.

## Calling the interface

`present(input_root, input_pin, action, limits)` returns a JSON-compatible object
containing rendered HTML and explicit scope/qualification flags. `limits` must
supply positive integer `read_bytes`, `metadata_bytes`, `response_bytes` and
`wall_seconds`. Calls preserve no cross-case state and execute no supplied code.
All actions have closed field sets:

- `{"action":"overview"}` exposes assistance, class order and complete support counts.
- `{"action":"sentences","realm":"train","offset":0,"count":1}` lists opaque sentence IDs and, for training, the allowed opaque groups. `realm` may also be `query`; page count is 1–64.
- `{"action":"features","offset":0,"count":1}` shows channel/bin/geometry or timing coordinates; count is 1–64.
- `{"action":"values","realm":"query","sentence":"<opaque id>","key_offset":0,"key_count":1,"feature_offset":0,"feature_count":1}` renders exact values. At most four keys and 64 features are returned; training pages also show labels and weights.
- `{"action":"check_response","predictions":{...}}` validates the original `typing_predictions_v1` object. Every query sentence must occur once with exactly `n_keys × 29` finite simplex entries. Missing, extra, duplicate or repaired predictions are refused. A successful check has `score: null` and `campaign_complete: false`.

A CLI accepts one inert JSON action on stdin and writes one complete JSON object
on stdout. For example, with explicit operator-selected ceilings:

```sh
python3 -I -B observation.py \
  --input-root PUBLIC_DIAGNOSTIC_PACKET \
  --input-bytes INPUT_BYTE_COUNT --input-sha256 INPUT_SHA256 \
  --read-bytes READ_CEILING --metadata-bytes JSON_CEILING \
  --response-bytes RESPONSE_CEILING --wall-seconds TIME_CEILING \
  < ACTION.json
```

The CLI validates limits before reading stdin, reserves `metadata_bytes + 1`
for bounded action ingress, and includes ingress under the same deadline/read
ceiling. The API assumes its already-parsed action was admitted by the caller.
It does not open a path supplied inside an action or provide file, shell,
expression, model, network or arbitrary numerical actions.

## Costs, comparison and remaining activation work

Each values call streams and hashes the **whole selected matrix** while keeping
only the requested cells. Memory is bounded by metadata, a 64-KiB scan block
and a constant multiple of the response ceiling for escaped/serialized output; large arrays are not loaded wholesale. Repeated
pages repeat the full matrix read and scan. That cost is deliberately reported
in `reserved_read_bytes`; API failures retain the reservation and elapsed time
on the exception's `observation_costs` attribute. If a CLI call fails before a
page is returned, conservatively charge its entire declared read/time ceilings
and retain the failed invocation rather than infer zero cost from missing output. The caller
must reserve and retain cumulative reads, failures, calls, output bytes and time
across pages. Per-call ceilings do not establish matched campaign budgets or
prove feasible authentic throughput. No partial output is returned when a
ceiling is exceeded.

A future owner must separately qualify the immutable public mount and transport,
participant tool restrictions, fresh case state, authenticated full original
membership, mode chronology, complete response capture, target-last scoring and
budget parity with any comparator. The complete original scope is 78 cases,
six arms and both existing programme modes; this component does not shrink that
scope or claim those 936 programme episodes have run. A newly selected viewer
condition needs its own explicit complete campaign and comparator definition;
this renderer alone cannot establish one.

Successful local response checks are structural only. They must be captured and
bound to the exact packet and original campaign identity before protected
scoring. They cannot establish observed-key accuracy, neural understanding,
reference competence, semantic isolation, physiological latency or unique
cross-modal participant independence.

## Generated controls and integration

Run `python3 -I -B test_observation.py` from this directory. The standard-library
controls exercise complete six-arm EEG and full-dimensional MEG packets,
last-coordinate delivery, exact calibration, class/bin/geometry semantics,
HTML escaping, all-query response validation, forbidden/private fields, invalid
layouts, target-like query columns, changed/truncated/nonfinite matrices and
resource rejection. Fixtures are generated locally and removed afterwards.
Their small row counts are software controls, not a substitute population.

The test's final contract check reads only the retained public `PUBLIC_ABI.json`
and `design/INFORMATION_VIEWS.json`. During isolated candidate review set
`NEURAL066_LEGACY_SOURCE` to that source directory; after repository integration
it resolves the sibling `neural-066/typing-s3-public-v1/source` by default.

Publication should register this directory as an additive observation component
and enroll this test in the current CI job. No changes to the pinned historical
public package are needed. Activating it inside a controller would require a
separately reviewed source inventory, authority bindings and the transport and
scientific qualifications above; registration must not promote readiness.
