# NEURAL-010 held-person event campaign

This additive route tests whether a participant can produce seizure event
intervals from permitted observations. It preserves all686 recordings and23
biological people, including the chb01/chb21 merge. The participant owns its
predictions. An explicit empty interval list is a valid submitted decision;
missing records, timeouts and provider failures never become empty predictions.

The source drives a real interaction loop and calls the unchanged phase12
`freeze_candidate` and `grade_frozen` implementations. Generated controls exercise
the loop, signal delivery, complete freezing and protected scorer join. There is
no authentic full-cohort run, trained reference set or qualified execution here.
The historical programme and its status/target-mismatch fields are unchanged.

## Actual entry and services

`entry.py` is the closed-source command entry. It accepts `run` and `score`:

```text
python3 -I -B /selected/event-campaign-v1/entry.py run
  --source-bytes EXACT_BYTES --source-sha256 EXACT_SHA256
  --request /operator/campaign-request.json --request-bytes N --request-sha256 SHA
  --authority /operator/authority.json --authority-bytes N --authority-sha256 SHA
  --output /operator/new-campaign
  --reservation-root /operator/invocation-ledger
  --read-root /operator --read-root /prepared --read-root /selected-exchanges
```

Arguments are one command; line breaks illustrate fields. `score` has the same
flags with its own independently selected request/authority and fresh output.
The invocation ledger must already exist and be protected. Every request digest
gets one create-only reservation, so repeating it cannot reset its costs. All
required input roots must be explicitly selected. Physical namespace custody
remains an independent requirement.

An independently selected custody service watches its configured exchange. It
receives actual launch, state-freeze and close requests and owns the participant's
process, runtime, restricted input mounts, state and retirement. A participant
service implements `initialize`, `held_person_query` and `observation` messages.
It responds with exact `observe`, `ready` or `submit` actions. A viewer also needs
a separate renderer service. These service implementations are deployment
prerequisites; the controller does not launch arbitrary participant code inside
its protected Python process or pretend those services exist.

`exchange.py` supplies the concrete file transport: a fresh role/context namespace,
create-only numbered request files, bounded numbered responses, exact sequence and
request-digest joins, one original deadline and cumulative counters. The external
services must share a qualified interpretation of the controller's monotonic
clock. Remote clock translation is not implemented. Custody must terminate and
retire active contexts on controller loss/deadline; a controller timeout itself
is not proof that a remote process stopped. Partial evidence remains incomplete.

The independent service may create only responses in its permitted exchange.
Participant, custody and renderer namespaces must be mutually disjoint and
separate from operator output, preparation, source and evaluation namespaces.
No source path guard or digest is a sandbox: without actual external isolation,
a separate process could still inspect accessible protected files, sibling-fold
training labels or shared chat history. Hash-bound JSON receipts alone do not
prove independent custody, process execution, immutable model state or competence.

## Source-owned chronology and access

The selected request binds its source manifest, original/streaming preparation,
mode, method/learning/training/tool/tuning/resource contract, limits,23 fresh
context identities and a separately selected evaluation specification. Reference
stream descriptors and original assessment identity are selected before the
participant is launched. They are never participant inputs.

For every biological person, `campaign.run`:

1. Starts one fresh externally isolated context. Only this fold's inputs and
   capability surface may reach that participant.
2. Optionally projects the exact final-fold training document for the other22
   people in `frozen_program/other22`. Source filenames/digests and private
   preparation fields are removed by the preserved phase12 projection. Training
   observations are restricted to those other people. No global training folder
   is shared across participants.
3. Receives `ready`, then requires a separate custody acknowledgment of the exact
   method/contract and immutable state before delivering any held-person query.
   A participant's claimed state digest is insufficient by itself. The controller
   durably retains both request and acknowledgment.
4. Creates the exact phase12 held-person query, then serves observations only for
   that person. No training access remains through this surface after the query.
5. Accepts a structured submission containing every held-person recording and its
   interval list. It requires independent closure binding that exact submission
   and state, retaining all request/response bytes.
6. Only after all23 contexts complete, calls the preserved full686 freeze and
   writes `CANDIDATE.json`, `FREEZE.json` and `CAMPAIGN.json`.

`score` replays the exact request, whole-run reservation, source-owned custody
request envelopes and acknowledgments, queries, submissions and complete freeze.
It binds the selected reference provenance, complete run evidence and all three
reference streams, then calls `grade_frozen`. The protected assessment descriptor
is accessed only inside that function's post-freeze/reference callback. General
metadata reads reject assessment/TRAIN/VALIDATION names, including case variants.
Training and assessment bodies have separate source-owned capture methods.

## Programme and visual conditions

`frozen_program` permits calibrated numerical windows through opaque signal
handles. Training policy is explicitly `none` or `other22`. `provider.H5Signals`
authenticates the whole selected projection before each window, then imports
h5py inside that admitted operation. It checks the original five-dataset schema,
256Hz integer duration, shape/dtypes/chunks, hard internal links, no external
storage/VDS/filter pipeline, ordered channel indices, duplicate labels and finite
positive calibration. Values use the original `digital * scale + offset` rule.
The actual native H5 path has not been executed or qualified by these controls.

`typed_viewer` is a zero-shot visual condition with no training annotations. Its
selected external capabilities must additionally forbid code execution, raw
array/SVG export and task-specific detector tools. The source constructs a fixed
unfiltered SVG frame, sends it only to the separate pixel-rendering service, and
returns an opaque PNG handle plus fixed geometry to the participant. No raw
samples, SVG source or SVG-content digest appears in that response. The raw
render request is operator/provider-private. A tool runner allowed to inspect
SVG source or run custom Python is not established as the native/viewer condition.

Display gain is a required positive finite `display_half_range_microvolts` frozen
in the operator policy. There is no clinical default, autoscaling or exported
signal-derived maximum. Samples outside the fixed range saturate at the display
boundary; no clipping counts are returned. Every requested sample maps to a
polyline point, with an explicit marker for a one-sample window. Calibration is
40pixels per fixed half-range around each row baseline. Time/channel indices and
sample rate are explicit. Up to4096 samples occupy1000 horizontal pixels; absence
of numerical downsampling does not guarantee every sample is visually resolvable
after rasterization. This restricted fixed-display condition is not parity with
an interactive clinical EEG viewer.

Both modes preserve complete record exposure and can request bounded successive
windows. Individual requests select at most4096 samples and16 ordered channels;
prospective output/render allocation and signal-sample reservations occur before
the provider read. The frame and whole-run limits can impose tighter bounds.
No window-level success stands in for complete cohort predictions.

## Independently supplied references and interpretation

The original scorer's three comparator keys remain `matched_no_eeg`,
`signal_reference` and `montage_only`. Their names do not establish matching.
The evaluation selection and independent provenance bind all stream bytes,
full held-person support, source/training/tuning/resource descriptions and retained
external run/closure evidence. Generated reference doubles are explicitly
`generated_control` and cannot be relabelled as an authentic run at score.

`fixed_reference_comparison` makes no matched-ablation claim. If the operator
requests `matched_ablation_requested`, additional independent evidence must bind
the actual candidate contract, no-EEG stream, learner/training/tuning/metadata/
tools/compute/signal-access comparison and exact per-held-person training
membership: empty for no-training, the other22 people for `other22`. The old fixed
learner is not relabelled as an arbitrary participant's matched control. Reading
these bindings does not itself qualify the underlying independent research.

The preserved scorer retains its signed across-person candidate-minus-no-EEG
statistics, event matching, observed-hours false alarms and montage uncertainty
limitations. A signed difference is not automatically an improvement, significance,
SOTA result or clinical finding. The preserved false provider/isolation/matching/
competence qualification flags remain false. This route adds factual source
transcript/freeze provenance; it does not promote those flags.

## Resources, failures and validation

All source/data reads, writes, actions and sample deliveries use one selected
invocation budget. The request's limits must equal the active budget. Entry
preflight has a separately retained12MiB read/16KiB write allowance; strict
manifest/row validation occurs before source bodies. Whole-operation allowances
are reserved durably before data/provider effects and remain charged on failure.
`CAMPAIGN.costs` is a **pre-receipt** logical-counter snapshot: the live budget also
charges the final `CAMPAIGN.json` write. Neither counter set measures physical
RSS, filesystem allocation, native-library work or external service compute.

Each H5 observation currently authenticates the entire selected H5, then charges
native file reads. It is not a window-only I/O optimization. Native libraries,
HDF5 plugins/runtime, operator storage, service lifetime/clock, provider credentials
and process isolation require separate deployment qualification. There is no
retry, automatic cleanup claim, default prediction, reduced cohort or storage
reclamation in this route. Detailed operator artifacts stay private; CLI failure
output contains a typed error only.

`test_campaign.py` uses a full686/23 in-memory generated fixture and explicit
simulated external services. The programme peer actually requests observations
and derives intervals from delivered values, while the viewer peer exercises
image delivery and explicit empty submissions. The tests call the actual frozen
projection, freezing and scoring code; no authentic H5, models or fits run.
Independent reviewers separately exercise file transport, source preflight,
late-fold failure, altered frozen artifacts/references and the target barrier.

The runtime manifest closes nine source files, including exact phase12 detector,
scientific scorer/event policy and phase15 compatibility copies. Default
production dependencies are inside `vendor`; preparation and service inputs are
explicit operator selections. Generated controls additionally need the existing
phase15 test fixture and frozen original-v1/phase12/phase14 source paths documented
in `CONSTRUCTION_EVIDENCE.json`. The owner-authored
`PLATFORM_AND_STORAGE_PROPOSAL.md` is a separate proposal, not an installed cache,
clock backend, storage admission or runtime capability.
