# Restricted DMFC participant transport

This executable operator connects the existing count viewer to a separate
participant process. A participant receives the original instructions, public
case identities and permitted cue metadata, plus the existing PNG count tables.
It can browse training and query cases, submit immutable ordered predictions,
and finish. It receives no raw packet paths, evaluator files, reference reports,
source/runtime inventory or opposite-view history through the interface.

The companion `adaptive-owner-v2` is a different, numerical-tool condition. This
viewer transport does not turn an observation callback into a model or rename
historical frozen-program results as adaptive results.

## Original scientific contract

Both cue-only and neural views retain all 748 training and 258 query cases from
the original exposed Haydn 20161211 development session. All 40 units and four
strictly pre-Set 50 ms bins remain available. The exact renderer, source packet
admission, chronological IDs, training labels/folds, query cue fields and
released behavioral `tp_ms` endpoint remain unchanged. Counts are shown as the
existing exact integer tables; this is not a reconstructed spike raster.

State and arbitrary browsing/revisits persist within one view. Every query must
be viewed before its answer, and answers remain in original order. All training
cases are available, but viewing every training case is not mandatory. Action
and image limits must permit all offered observations and answers. Separate
byte/time caps can terminate an attempt; their full-session feasibility requires
operator admission.
Finite negative predictions remain valid. A new process, empty working
directory and unique episode serve the other view. Both views must have the
same captured participant source, limits, transport source and sandbox mode.

The existing complete authentic backend control already rendered 2,012 initial
observations and 2,012 collector replays, with fixed 800 ms responses. See the
[existing delivery report](../../../../../docs/science/neural095-count-viewer-delivery-20261117.md).
That evidence is reused as renderer evidence. It does not establish this new
participant boundary, a model result or neural understanding, and it is not
rerun as part of this construction.

## Participant and owner boundary

Each wire frame contains two network-order unsigned 32-bit lengths, then exact
UTF-8 JSON and optional PNG bytes. Participant requests have no image part and
are at most 16 KiB. Operator metadata is at most 32 KiB; the image cap is 4 MiB.
Images remain binary image content, not an automatically interpreted text
substitute. Requests are exactly the original typed actions:

```json
{"op":"show_train","index":0}
{"op":"show_query","index":0}
{"op":"answer","case_id":"dmfc-000748","prediction_ms":800.0}
{"op":"finish"}
```

The shown ID is illustrative. The exact original next query ID is required.
The ready header declares the full query roster, available actions and frozen
limits. Responses use `kind: observation`, `kind: accepted`, or the terminal
`kind: complete`. Only observation responses include a PNG frame part.

The operator owns packets, rendering, journals, deadlines, process termination
and collection. An answer event is flushed and fsynced before its acknowledgment.
A failed write, malformed request, exhausted budget or premature EOF ends the
attempt; there is no retry, resume or partial collection. Raw wire bytes and
linked journal records retain failed/partial communication.

`finish` first closes the participant interaction. The owner requires exit zero,
reaps its child, and checks/removes the original process group. Only after clean
closure does it append the original viewer's final completion record. A terminal
response followed by a crash or hang therefore leaves an incomplete original
history. `ACTIVE_CHILD.json` and `CLOSED_CHILD.json` bind the exact owned process
and episode. Forced supervisor termination still requires operator recovery;
recorded group closure is not proof of whole-system descendant absence.

The default macOS profile denies network, process creation, access to other
processes, file writes and data reads outside the captured participant and
declared system runtime roots. The child receives only `LANG` and `LC_ALL` and
runs with `-I -S -B`. Use the existing framework interpreter, not Apple's
`/usr/bin/python3` launcher. The explicit `protocol_only` option exists for
portable generated controls and supplies no operating-system isolation.

This boundary restricts local inputs and operating-system operations. It does
not prove that arbitrary participant Python performed no in-process analysis,
that a remote provider reset its context, or that an LLM used no tools. No model
or provider connector is supplied or qualified here. Those claims remain false.

## Collection and protected evaluation

`collect` first audits both complete transport histories, source/participant
identities, limits, every request/image/response and clean process closure. It
then invokes the unchanged viewer collector and original prediction validator,
producing the original `case_id` / `prediction_ms` NPZ for each view. The added
`TRANSPORT_COMPLETE.json` binds both closed sessions to that collection.

`grade` performs both transport audits and full collection validation before
calling the original evaluator. Reference and private-target loaders are not
invoked until both views have closed and their complete outputs pass admission.
It preserves all five fixed references, trial MAE, RMSE, eight-context macro
MAE, all 40 condition/eight context reports, and the accepted
`paired-arithmetic-v2` exact calculation of cue MAE minus neural MAE. Zero or
negative gain is valid. No new reference, tolerance or success threshold is
introduced. Evaluator reports stay outside participant access.

The complete cost includes rendering during admission. Per originally viewed
case, execution renders once; transport collection renders twice (wire audit
and original collector); grading renders three more times (wire audit and the
original public validations). These are actual call-graph costs, not additional
model trials. A future authentic run must budget all phases explicitly. The
source only enforces wall, action, image and wire limits; CPU/RAM/provider budgets
need the external operator's reviewed resource control.

## Operator use

The commands below describe an independently admitted future operation. They
are not an authorization to run authentic data or models. Input JSON is the
existing view-to-five-file operator locator used by `count-viewer-v1`. Give each
`view` operation only its selected view. Each output path must be new.

```sh
python -I -B benchmarks/neural/NEURAL-095/implementations/participant-transport-v1/transport.py view \
  --inputs cue-inputs.json --view cue_only --output cue-session \
  --client participant.py \
  --python /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 \
  --sandbox macos --max-actions 2000 --max-images 1500 \
  --max-output-bytes 134217728 --wall-seconds 300

python -I -B benchmarks/neural/NEURAL-095/implementations/participant-transport-v1/transport.py view \
  --inputs neural-inputs.json --view neural --output neural-session \
  --client participant.py \
  --python /Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11 \
  --sandbox macos --max-actions 2000 --max-images 1500 \
  --max-output-bytes 134217728 --wall-seconds 300

python -I -B benchmarks/neural/NEURAL-095/implementations/participant-transport-v1/transport.py collect \
  --inputs paired-inputs.json --cue-session cue-session --neural-session neural-session \
  --output collection

python -I -B benchmarks/neural/NEURAL-095/implementations/participant-transport-v1/transport.py grade \
  --inputs paired-inputs.json --cue-session cue-session --neural-session neural-session \
  --collection collection --evaluator-inputs evaluator-paths.json --output grade.json
```

The shipped `scripted_client.py` exercises every offered training/query image
and returns 800 ms. It is a software-control client, not an AI or a fitted
baseline. Its future use does not establish benchmark difficulty or scientific
performance. Generated tests use invented complete packets and explicitly
substitute tiny PNGs for bulk transport; original PNG handling and the actual
macOS boundary are tested separately. No new authentic processing is implied.

The first independent local run passed all 21 methods without failures or skips:
18 transport/collection controls and three boundary controls. The actual macOS
denial control is explicitly skipped on other operating systems; hosted Linux
success must not be reported as macOS containment evidence. The existing NumPy
environment and framework child interpreter were used without installation.
The complete scope, source pins and measured/unknown costs are recorded in
`TEST_RESULTS.json`. This test result is separate from the older authentic
renderer proof and from any future participant study.

One historically exposed animal/session cannot establish unseen-animal,
causal-neural or SOTA claims. Fresh local processes and correct typed delivery
do not change that population or certify a matched scientific method.
