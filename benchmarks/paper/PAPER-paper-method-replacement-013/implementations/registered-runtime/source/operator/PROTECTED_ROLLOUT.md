# Protected generated-history component

`ReleasedCalls.protected_generation(fitted, request, queries)` now calls the
actual `protected_rollout.produce` implementation. It constructs current tokens,
calls the selected model with `targets=None`, samples the two output heads and
feeds generated events into later history windows. This is a source-amended
component. It is not an original Figure 6 ablation, a completed benchmark run or
an independently qualified execution boundary.

The [ICLR paper](https://proceedings.iclr.cc/paper_files/paper/2024/file/b16e55ac49f93d33a4b87747d5121b64-Paper-Conference.pdf)
describes this feedback mechanism in section 3 and Figure 8. The pinned release
passes generated events to `get_interval`, which replaces that argument with
original data. Its DataFrame branch also returns no token packet. The historical
generator, loader, training and metric paths remain unchanged. Repairing only
the overridden argument would not provide a working protected producer.

The paper reports comparative architectures but does not supply a complete
recoverable recipe in the captured text release. Appendix E's five-layer,
tapered bidirectional GRU with dropout .01 differs from `ImprovedGRU`, whose
constructor defaults to three constant-width layers and dropout .1. `mlp_only`
constructs an MLP but bypasses it in forward. The selected text/config roster
does not bind original Lasso/behavior-GLM fitting, 25-class edges, medial or
few-shot runs. These gaps remain; the component does not invent a substitute.
The unselected notebooks were not inspected in this phase, so this is not a
claim that no other repository artifact could contain useful information.

## Exact native call path

The operator attaches exact configuration, run and selected-checkpoint identity
descriptors to `fitted['rollout_identities']`. The request must match those
descriptors and its explicit seed must match the fitted seed. The actual model
must retain the identical configuration and tokenizer objects. Descriptor
equality is a consistency check; capturing/authenticating the checkpoint and
runtime remains an external obligation. No weights are loaded by this source
phase or by the producer itself.

All train, validation and evaluation rows are declared before use. The existing
full-context support admission checks their neural/video separation. Episodes
partition the entire ordered evaluation roster. Each episode contains contiguous
50 ms windows from one recording and declares an empty generated buffer. A new
episode is an explicit reset, never a hidden skipped window. Endpoints below
50 ms refuse rather than silently wrapping a negative source interval. The
complete native Trial 0 output packet is restricted to one recording, preventing
ambiguous cross-recording joins in the existing metric ABI.

Each query contains only its row ID and source-declared exogenous features.
Current IDs, current times, observed neural history, targets and extra fields
are refused. Inputs may include frames and only modality variables declared as
inputs by the selected configuration. Their dimensions are bounded before
transfer. Model access to external process state is not ruled out by this API;
physical data/target isolation is still unqualified.

The current block starts with SOS and padding, with time start index zero as in
the released loader. At step n, only the previously generated prefix is present.
`NativeStep` creates native tensors, calls `model(x, None)`, checks the actual
full logits shape, selects position n, applies the exact captured filtering
definition, divides by the explicit temperature, then calls softmax and
multinomial or top-k. Device, seed, sampling flag, top-k, both top-p values and
both temperatures are required; none is asserted to be the paper's run recipe.

## Disclosed protocol amendments

* Every episode starts with empty generated history. This is not the existing
  prospective 5 ms bridge's observed seed-history condition or the historical
  loader's observed past. Its biological effect has not been evaluated.
* Neural history contains only prior generated events inside the half-open past
  window. Events are sorted by native time and neuron ID, matching the released
  rate-array branch's ordering. Repeated events remain repeated. A common
  retained suffix supplies paired IDs and times; the original independent
  truncation defect is not copied. Source SOS/EOS/padding layout is retained.
* Decoded times must be numerical offsets on the native 10 ms grid within the
  current 50 ms window. They are not newly resampled 5 ms events. ID and time
  tokens are retained as pairs, and absolute generated-event time is computed
  from the current window's start. Counts/rate/Hertz equivalence remains unknown.
* EOS terminates a window. Other special ID tokens and invalid time tokens
  refuse the whole result; they are not silently treated as EOS or repaired.
  An EOS time-head draw is ignored because EOS is not a neural event.
* Each current block has at most block_width minus one model calls, as in the
  release. Exhaustion without EOS is explicitly recorded as truncation. A
  partial resource-limited result is never returned as a complete packet.
* Time filtering is controlled independently by its own explicit top-p value.
  The release guards both filters using the ID top-p flag. Filter-before-
  temperature ordering is retained. No sampling-distribution parity is claimed.

The component records every window, including empty and truncated windows, plus
aligned ID/dt/Trial/Interval predictions. Those predictions satisfy the existing
`run_metrics.freeze_generation` boundary. Interval identities use the exact
released float32 representation read by `window_truth`; distinct windows that
collide in that representation refuse before model access. There is no tolerance
join or silent window merging. Private target access is absent from
this API. The existing two interval metric definitions remain available to the
separate evaluator; no Figure 6 formula, dense-bin conversion or paper result is
selected here. Truncation is not hidden by metric aggregation.

## Remaining scope and validation

All 71 predecessor roles and every original source body remain. There are still
46 case slots, 85 condition cells and seven wider families. The ten protected
neural cells now report that a component is available, while their original
ablation/configuration/run mapping and scientific gates remain open. The normal
`dispatch_native` still refuses those cells before provider access: this
component is not a license to label a convenient configuration as an ablation.

Actual normal-import controls exercise `ReleasedCalls`, the producer,
`NativeStep`, the exact original filtering function and metric admission with
explicit inert leaves. They test generated feedback, pairing, resets, empty
windows, termination, invalid tokens, support and effect-site limits, and
current/target/history-field rejection. These controls establish source
mechanics only. There were no authentic observations, models, weights, training,
scientific metrics or numerical-library imports. Native numerical parity,
physical containment, authentic execution and whole-paper coverage remain open.
