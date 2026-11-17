# Participant delivery for NEURAL-025

This component converts the existing admitted **within-mouse** calcium decoding
request into a participant packet and a separate operator identity index. It
collects complete predictions and passes them to the existing measured-kinematic
scorer. It adds an executable participant-only frozen reference and typed
full-grid trace/SVG views. Native source preparation and protected participant
execution remain unqualified. No authentic input or model trial was run to build
this component.

The endpoint remains 24 ordered joint angles in degrees **or** 24 joint
velocities in degrees/second. Each request uses the complete declared grid,
selected whole-trial census, five mice and both M1/S1 sessions. The recommended
source-backed grid remains -100 through +400 ms in 10 ms increments; generated
construction fixtures use that same 51-sample grid. Nothing here changes the
prospective train-only recipe, source eligibility, retrospective interpretation,
training-SD NRMSE, equal joint/session/mouse aggregation or companion controls in
[the predecessor](../train-only-decoding-v1/README.md).

## Operator export and collection

Load `delivery.py` using `importlib.util.spec_from_file_location`, or add this
directory to the module search path. It imports the adjacent existing pipeline;
Python 3.11+ and the existing NumPy 2.4.6 installation suffice. No new package,
source download, native MAT processing or model fitting is needed to export.

```python
from delivery import prepare, reference_response, score_response, p

# This step runs only in the operator context, with independently trusted hashes.
participant, private_index = prepare(
    dataset, protocol, context,
    expected_protocol_sha256=frozen_protocol_hash,
    expected_context_sha256=frozen_context_hash,
)
participant_hash = p.digest(participant)
private_index_hash = p.digest(private_index)

# Transfer only participant to the participant environment.
response = reference_response(
    participant, expected_packet_sha256=participant_hash,
    frozen_program_sha256=operator_frozen_code_hash,
)

# Evaluation remains in the operator environment, after response collection.
result = score_response(
    dataset, protocol, response, participant, private_index,
    expected_protocol_sha256=frozen_protocol_hash,
    expected_packet_sha256=participant_hash,
    expected_index_sha256=private_index_hash,
    expected_mode="frozen_program",
    expected_program_sha256=operator_frozen_code_hash,
)
```

The participant packet contains all training calcium and kinematics, all query
calcium, public left/right reach target, fixed time grid and exact target names
and units. ROI selection matches the predecessor: rank training-only neural SD,
break ties by native ROI identifier, retain the declared cell budget. Selected
values are unscaled and uncentered, so participant methods remain free to choose
their own permitted fit. Session-local ROIs, trials, sessions and mice receive
opaque display identifiers; original strings and all source/provenance metadata
remain in operator inputs/index. Equal ROI display names across sessions never
establish correspondence. The public protocol digest contains no target values.

The private index maps complete responses to original identities and binds the
full normalized source fingerprint, including hidden targets. It must never be
transferred alongside the packet. Changing query target values leaves every
participant byte unchanged but invalidates subsequent scoring against the old
index. Arbitrary extra context fields are not copied into the participant view.
The public LR context is authenticated against the complete session/trial census
and declared source hashes, but these declarations still need native validation.

`collect_response` requires exactly ten sessions, every selected query trial,
every grid point and all 24 joints. It rejects extras, omissions, nonfinite or
boolean values, wrong units/joint order/grid, changed packet/index identities,
and cross-mode responses. It never assigns a score to a surviving subset.
`score_response` calls the predecessor scorer on the exact original source
fingerprint. Its metric record therefore preserves biological aggregation and
undefined-variance behavior without duplicating numerical definitions.

## Four separately recorded access modes

| Mode | Implemented observation/response interface | External runtime requirement |
| --- | --- | --- |
| `direct_observation` | Complete numeric packet, complete numeric response | Present all authorized calibration/query observations within an explicit context budget; disable tools and record actual exposure. No no-tools session was run. |
| `typed_viewer` | `render_trace` with typed session, split, case, neural/targets and channel selection; SVG includes every grid sample and numeric axes | Keep packet on the trusted renderer side; return only the rendered image. Enforce action/time budgets and record actions externally. |
| `tool_assisted` | Same packet plus `trace` numerical observation API; same complete response domain | Declare and enforce external tool/checkpoint/compute access. No case-adaptive investigator run was made. |
| `frozen_program` | Participant-only `reference_response` and bounded CLI; explicit frozen code identity in response | Freeze exact code/dependencies before evaluation; run with no private-data mount and record executed identity. The response's declared hash is not a process attestation. |

For every mode the response fields are `schema="calcium_response_v1"`,
`task_id="NEURAL-025"`, `packet_sha256`, `mode`, `target_field`, `target_units`,
`joint_names`, `time_ms`, and `predictions`. `predictions` maps public session ID
to public query case ID to a complete time-by-24 real numeric matrix. Frozen
program mode alone additionally requires `frozen_program_sha256`; the expected
mode and program identity come from the operator, not participant selection.

The viewer action has exactly `session_id`, `split` (`training`/`query`),
`case_id`, `signal` (`neural`/`targets`) and `channel` (a selected ROI ID or exact
joint name). Query `targets` requests always refuse. Traces retain the complete
time grid with no smoothing/downsampling/cropping, and SVG axes disclose each
trace's display scale. Neural units remain `source_processed_activity`: they are
not relabeled spikes or independent 100-Hz observations. Rasterization, display
precision, finite action budget and context limitations still make the viewing
condition distinct from numeric access; identical stored values do not prove
identical effective information or establish a paired capability result.

The frozen reference uses only participant training labels and query neural
data and invokes the predecessor PCA/ridge routines on the selected cells.
For equal selected variances its public ordinal ROI IDs retain native selection
order, preserving tie handling. Its CLI writes only a response to stdout:

```sh
python3 -B delivery.py --packet participant.json \
  --expected-packet-sha256 "$PACKET_DIGEST" \
  --frozen-program-sha256 "$PROGRAM_DIGEST" \
  --max-input-bytes 100000000 --max-output-bytes 100000000
```

Those byte budgets are operator-selected bounds, not measured authentic cohort
sizes. The CLI has no scorer or private index argument. It is not an OS sandbox.
Keep this implementation and its predecessor available for execution while
keeping operator data and index outside that environment.

## Evidence and remaining qualification

`test_delivery.py` uses explicitly generated arrays for all ten source-listed
sessions and all 51 time samples. Tests exercise hidden-target byte invariance,
training-only ROI selection under extreme query changes, context coverage,
independently known linear predictions, parity with the unchanged scorer,
complete-output errors, identity binding, modes, viewer target denial, velocity
units, and the actual participant CLI. These are software controls, not calcium
decoding performance.

Source derivation reuses pinned GSK26-public revision
`815b610b3beddfed5a3abf611d3a465ab9e4ce5c`, especially
`main/fig5/fig5_analysis.m` (M1/S1 dates and separate endpoint/input tracks) and
`main/fig3/plots/plotJointAnglesVertical.m` (LR 1/2 meaning), as recorded in the
predecessor [provenance](../train-only-decoding-v1/PROVENANCE.json). No source
fetch was made. Exact implementation/source hashes and actual test costs are
frozen in the external handoff.

Native MAT contents, eligibility/exclusions, neural/kinematic clock alignment,
upstream calcium exposure and temporal support, rights, real cohort resource
costs, competent authentic references, no-tools/viewer runtime enforcement,
program execution isolation, scientific qualification and paired participant
results remain unresolved. The optional new-mouse local-calibration comparator
still exists in the predecessor; this exporter explicitly refuses it because
its five outer cases require a separately scoped access design. No canonical
task, understanding contract or historical artifact is changed here.
