# Restricted whole-person sleep image transport

This component connects the existing sleep waveform viewer to a fresh participant
process for each complete development person, then verifies the captured exchange
before invoking the unchanged 5,450-epoch collector and submission validator.
It supplies source for the missing participant connection. It does not run a model,
read private targets, fit a detector, score responses or qualify a scientific result.

The task is unchanged: development-001 contains 2,780 epochs and development-002
contains 2,670; all five class probabilities are required for every epoch, including
privately unscored movement/unknown intervals. Both people were previously exposed.
The condition remains `whole_person_raw_viewer_zero_shot`: EEG/EOG images and
permitted clocks, no training examples or evaluator feedback, with past and future
navigation inside the current person. Every target must first receive a complete
three-channel view. Each epoch accepts its first valid response only. An invalid
request fails the person session, preserving the existing sleep viewer behavior.
`finish` is terminal only after all epochs have responses.

The separate feature programme receives engineered features, six labeled training
people and saved YASA outputs. This transport does not change that programme or
make its information budget equal to the zero-shot viewer. Shared target IDs do
not isolate the effect of tools. Programme success and native/viewer interpretation
remain distinct outcomes.

## Operator commands

Use an existing Python 3.11+ environment with NumPy for the operator. A client
uses the standard library and the declared binary protocol. No installation,
network request, image pull or provider call is performed. Exact original packets
must already be available; source bindings pin the unchanged viewer, renderer,
source facts, raster and original candidate validator.

Select a direct installed client interpreter inside the sandbox's allowed runtime
roots and supply it as `CLIENT_PYTHON`. On macOS, the system Python launcher may
require developer-tool files outside those roots. The recorded control used a
version-specific Python framework executable. Freeze and verify the chosen
interpreter before a full run.

Run each person separately with fresh output and fresh participant state. The
example limits below illustrate syntax; they are not an approved or executed
model-study budget:

```sh
OPERATOR_PYTHON -I -B transport.py person \
  --case development-001 --packet /operator/person1/packet \
  --client /operator/trusted-provider-bridge.py --python CLIENT_PYTHON \
  --sandbox macos --max-actions 20000 --max-images 6000 \
  --max-output-bytes 1073741824 --wall-seconds 9000 \
  --output /operator/evidence/person1-transport
```

Run development-002 with its own packet and output, the same client and frozen
limits, and a genuinely fresh provider context. `scripted_client.py` is an executable
framing example that consumes every image and returns uniform probabilities. Its
outputs are software controls, not an interpretation attempt.

```sh
OPERATOR_PYTHON -I -B transport.py collect \
  --packets /operator/person1/packet /operator/person2/packet \
  --sessions /operator/evidence/person1-transport /operator/evidence/person2-transport \
  --output /operator/evidence/new-sleep-collection
```

Collection requires both people, canonical ordering, matching client/source/limits/
sandbox conditions, distinct episode identities, successful child exit, and complete
unaltered wire and viewer histories. It replays the unchanged viewer, authenticates
both original packets again, and invokes its existing collector. The resulting
`predictions.npz` retains the original complete IDs, fixed W/N1/N2/N3/R order,
float64 probabilities and strict 4,000,000-byte submission cap. Nothing is filled,
clipped or normalized. `TRANSPORT_COMPLETE.json` means complete unscored local
collection. The separate portable grader may evaluate that frozen submission under
its own original target/reference and operator requirements.

## Protocol and enforced limits

Frames have two unsigned network-order 32-bit lengths, then JSON bytes and optional
PNG bytes. Client frames contain 1–8,192 JSON bytes and no image. Operator JSON is
at most 32,768 bytes; each PNG is at most 4 MiB. The first frame contains instructions,
the action schema, current person, epoch count, opaque episode ID and frozen limits.
It contains no image; the participant explicitly requests each view. Subsequent
images are raw PNG frame parts, not base64 prose. A real bridge must deliver them
as actual provider image content. It must not expose the operator filesystem,
numerical arrays, targets, detector caches or arbitrary analysis tools to the model.

Only existing sleep actions are accepted: inspect, epoch, window, gain, channels,
respond and finish. Projections contain only existing viewer metadata and images
or response acknowledgments. Operator paths, raw packet hashes, exceptions,
private labels and scientific scores are not participant response fields.

Operators must freeze explicit action, image, outbound-byte and wall limits.
At least `2 * epochs + 1` actions and `epochs` images must be budgeted. Implementation
ceilings are 100,000 actions, 4 GiB outbound bytes and one day wall time; these
ceilings are bounds, not automatic study allocations or feasibility claims. Before
rendering, the runner conservatively reserves room for a maximum next image frame
plus a terminal allowance. Capacity failure aborts; there is no downsampling,
truncation, retry, resume or replacement answer. An already accepted epoch response
remains recorded even if the person session subsequently fails.

Every consumed inbound frame and every successfully written outbound frame is
recorded in `transport/wire.bin`, with direction, offset, byte count, hash and a
sequence chain in `journal.jsonl`. Truncated reads and partial writes retain only
the exact bytes actually handled, marked incomplete. Oversized lengths are refused
from the prefix before allocating or reading their claimed payload. Bytes queued
after terminal closure are not read or claimed captured. The child must exit zero
within two seconds and within its person deadline after `finish`; otherwise the
transport fails. Cleanup signals the still-owned process group before reaping
its leader, then checks group absence. A successful group signal can refer to a
zombie leader alone; it does not establish whether descendants existed before
cleanup. Failure to verify cleanup fails and retains its result. The viewer
completion marker is written only after successful leader exit and cleanup.
Escaped-descendant containment remains unqualified in `protocol_only` mode.

The original viewer session formats are retained in `viewer/`. `BOUNDARY.json`
binds source, client bytes, declared interpreter path, sandbox profile and limits;
`RESULT.json` records successful or failed local execution. A failure marker also
blocks direct use of the underlying viewer collector. Keep the entire output in
operator custody: receipts and the captured client are not participant materials.
Each inbound wire request and its exact response digest must correspond to the
same original viewer action row; equal final answers cannot hide a different
observation history.
Collection currently renders each action during both the original replay and the
transport audit, then the original collector replays it again. This extra checking
has a real cost; no authentic runtime or provider capacity is inferred from tests.

## Isolation and limitations

`--sandbox macos` uses system `sandbox-exec` with the same deny-default pattern as
the separately published EEG transport. It denies network, child-process creation,
other-process inspection and general sysctl reads; it supplies empty temporary
working state, sanitized locale-only environment and anonymous pipes. Read access
is restricted to the captured client and broad system Python runtime roots. Those
roots must contain no operator secrets. The selected interpreter must reside in
those roots. Source reuse does not transfer the EEG transport's earlier sandbox
execution evidence to this new component.

`--sandbox protocol_only` provides only process and message separation. The client
retains its host privileges; it is appropriate only for a trusted bridge with an
independently enforced participant boundary. Neither mode proves remote context
freshness, disables remote model tools, authenticates that a provider consumed an
image, nor distinguishes a model response from a programmed image detector.
The operator must establish those conditions independently before claiming native
interpretation. Successful pipe writes prove local OS delivery, not model viewing.
There is no hard child-memory/CPU accounting here beyond the declared wall timeout;
whole-study resource admission remains an operator requirement.

The trusted source tree, operating system, operator and client/provider bridge are
part of the trust boundary. Hashes detect changed saved artifacts, not a privileged
operator forging a transcript. Exact source and runtime version checks do not
prove binary environment identity or hostile-code containment. No untouched test
population, generalization inference, competent reference, model accuracy or full
canonical 153-night scientific qualification follows from this component.

[SCRIPTED_CONTROL.json](SCRIPTED_CONTROL.json) records a separately reviewed full
5,450-epoch software control at the stated source commit: two fresh scripted
clients, six sandbox checks and the complete collector path passed. It preserves
the earlier interpreter-startup failure and records the required 21,800 rendered
views, measured costs and evidence hashes. The receipt publishes metadata only.
Fixed uniform responses establish no model interpretation, provider capacity,
scientific accuracy or full 153-night qualification. Earlier renderer evidence
is not substituted for this source-specific execution.

Tests use explicitly invented packets and lightweight generated images for protocol
controls, plus the original complete submission validator. They are independent
of authentic waveform/model results. Run the suite in the existing NumPy environment:

```sh
OPERATOR_PYTHON -I -B -m unittest discover -s . -p test_transport.py -v
```

## Participant process cleanup

The current transport observes child exit without reaping, using Darwin kqueue or
Linux pidfd. It keeps the session leader owned until its process group has been
signalled, then reaps that exact child. Later group-presence probes use signal 0;
they cannot terminate a reused process ID. Missing observer APIs or a nondefault SIGCHLD handler refuse the launch.
Kernel registration can still fail afterward; that failed session enters owned
cleanup and cannot be admitted. The trusted operator must retain exclusive
wait ownership and must not install native automatic child reaping.

The shared [process ownership helper](../../../../shared/viewer-process-ownership-v1/README.md)
records this cleanup order separately from group absence. A group signal does not
contain descendants that escaped the group; `protocol_only` remains a trusted
operator bridge, not a hostile-code sandbox. The macOS participant policy is
unchanged. Historical execution receipts remain evidence for their original
source identities and do not qualify this lifecycle revision.
