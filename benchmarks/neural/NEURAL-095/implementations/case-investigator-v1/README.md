# Stateful case investigator for NEURAL-095

This alternate executable actor makes decisions from successive numerical-tool
observations. The existing `offline_actor.py` calls one frozen full-query batch
and replays its predictions in all four cells. This component instead invokes a
source-pinned `decide(context)` callback at every decision, including after each
tool observation. It collects all 258 predictions in the original order.

This is delivered actor software with generated controls. It has not executed on
authentic data, called a model, entered the existing owner, or qualified a provider.
It is not a direct-observation or waveform viewer condition. No benchmark is added.

## Preserve the existing scientific task

The named scope remains Haydn session 20161211: 748 TRAIN trials, 258 query trials,
four 50 ms strictly pre-Set bins across 40 held-in units, and released behavioral
`tp` in milliseconds. The cue-only and neural views, all five fixed references,
trial MAE, and cue MAE minus neural MAE comparison remain unchanged. Finite negative
predictions remain valid. Zero or negative neural gain is a valid outcome.

One fresh actor and callback namespace serves an entire cell. State persists
across all 258 cases; the full unlabeled query batch remains available to admitted
numerical tools. This is not a fresh per-case experiment. The callback sees the
current case, previous committed scalar decisions, previous tool arguments and
observations, and the TRAIN artifact commitment. It receives no scientific input
file mounts or targets through this interface. Tool output is the only numerical
observation path. The tool can expose the full permitted batch; the actor does not
silently restrict that original information access.

TRAIN-only fitting and method selection finish before queries open. Fitted
artifacts stay frozen; query-driven fitting and private feedback remain forbidden.
A callback may decide which declared analysis to request, inspect its result and
choose its next action. This does not authorize fitting or modifying tools after
query exposure. Source/procedure review and the external owner must enforce those
rules; a Python callback cannot establish its own scientific compliance.

## One assembled source and the original actor wire

`assemble.py` captures the exact template and callback bytes using independently
supplied SHA-256 expectations, parses their syntax, and embeds the callback in one
Python source file. It never imports or executes callback code. The final source
and its JSON freeze envelope must each fit the original 65,536-byte limit.
An existing output is refused. A failed output write may leave partial bytes;
preserve them and select a new destination after review.

```sh
python3 -I -B assemble.py \
  --template actor.py --template-sha256 REVIEWED_TEMPLATE_SHA256 \
  --callback decision.py --callback-sha256 REVIEWED_CALLBACK_SHA256 \
  --output investigator_program.py
```

The callback is ordinary candidate Python defining one top-level
`def decide(context): ...`. Its module globals persist within the cell. Callback
initialization is deferred until the first query decision, after the source freeze
and TRAIN preparation. It returns exactly one of:

```python
{"action": "tool", "tool_id": context["tool_id"], "arguments": {...}}
{"action": "predict", "case_id": context["current"]["case_id"], "prediction_ms": 700.0}
```

The single tool identity is the original source-pinned candidate numerical
programme. Different argument dictionaries can request different predeclared
analyses from its frozen fits. This component does not introduce arbitrary host
execution, new tool imports or additional scientific input mounts.

The assembled actor reads one four-string configuration on stdin:

```json
{"schema":"dmfc-case-investigator/v1","mode":"case_adaptive__neural","tool_id":"dmfc_predict@<64 lowercase hex source hash>","policy":"stateful_case_decisions/v1"}
```

The other supported mode is `case_adaptive__cue_only`. Frozen-program modes and
the old `single_frozen_fit_batch/v1` policy are refused. Run the assembled file
only inside an explicitly reviewed actor owner; its CLI is not a host sandbox.
The embedded callback needs no additional filesystem mount. The existing
`freeze` message commits the entire assembled file, so that source hash includes
both the actor and callback. Future adoption must bind this exact file and its
method declaration consistently across both views.

It then speaks the existing `freeze`, `public(prepare)`, `public(next)`,
`public(action)`, `public(tool)` and terminal `finish` JSON-line envelopes. A tool
must not advance the current case. Every prediction requires an affirmative host
acknowledgment. Duplicate cases, malformed replies, nonfinite predictions, foreign
tools, changed current-case identity, truncation and exhausted budgets stop the
actor. There is no retry, fallback batch or partial finish. The relay sends no
terminal reply; `finish` is not itself proof of host export or scientific grading.

## Bounds and external responsibilities

The actor preserves at most 16 numerical tool calls and 274 decision calls per
cell. Including TRAIN preparation and export, that is at most 292 reserved
operations. It retains the original 65,536-byte actor request cap, 262,144-byte
host response cap and 65,536-byte tool observation cap. Up to sixteen complete
bounded argument/observation pairs and 258 committed scalar responses fit the
explicit 3 MiB callback-context cap; no earlier observations are silently dropped.

The current owner declares 900 seconds per cell, 120 seconds of preparation,
4 GiB aggregate memory, fixed conservative CPU reservations and zero provider
token/cost reservations. This actor does not replace those limits or measure
actual CPU, memory, provider usage or filesystem isolation. Deadline preemption,
source and input authentication, subprocess ownership, trusted costs, network
denial and removal of each cell remain the external owner's responsibilities.
Its small stdin/stdout guard catches accidental callback protocol access; it is
not a security boundary against arbitrary Python, threads or OS calls.

The current `configuration.py` and `candidate_admission.py` require the old
offline policy and actor. They deliberately remain unchanged and reject this
alternate component. The existing actor backend also requires zero model/provider
reservations. Explicit later owner/configuration adoption and runtime qualification
are necessary before use. No live model connector or metered provider transport
is supplied here, and no existing status is promoted to qualified.

All four original cell producers must still stop and commit before either pair
is publicly validated; both validations precede private scoring. Host-owned full
roster validation, export, five-reference scoring, protected feedback and cleanup
are not duplicated in this actor. A callback's internal algorithm may violate its
declared method; source hashes and correct wire behavior do not prove matchedness.

## Generated evidence and limitations

`test_actor.py` exercises the complete 258-case loop and the actual assembled
single-file CLI. Its adaptivity counterexample changes a tool observation and
checks that a later tool request and prediction change. Additional controls cover
the exact 292-operation boundary, cross-cell callback reset, current-case support,
immutable captured history, malformed outputs, source identity, request caps and
failure without retry. Run it only through the shared bounded source-test pool.
The fixtures contain invented scalar observations and no authentic arrays or
labels. They demonstrate software behavior, not an AI capability or task score.

The target is one historically exposed public development session. No secret-test,
cross-animal, causal-neural, native-signal-understanding or SOTA claim follows.
The original evaluator references include information derived from public labels
and must remain outside candidate access. Source and budget bindings are recorded
in `SOURCE_BINDINGS.json`; they describe the preserved contract, not an execution
grant or a complete dependency/runtime attestation.
