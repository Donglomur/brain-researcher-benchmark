# Complete numerical-waveform transport

This runner supplies the per-query execution path missing from
`complete-direct-condition-v1`. It authenticates the original public packet,
recomputes all 400 prompts, starts a fresh participant process for each query,
captures its first response, and delegates complete submission assembly to the
unchanged delivery collector and registered validator. It never opens private
targets, fits a model, calls a provider, or computes a scientific score itself.

The two conditions retain their existing names and information:

| Condition | Delivered input | Permitted participant behavior |
| --- | --- | --- |
| `legacy_waveform_no_tools` | Four original demonstrations and one complete numerical Cz/Pz query | Direct model response; no analysis tools, retrieval or other-query memory |
| `matched_waveform_programme` | Identical observations; only the existing permission sentence differs | Numerical analysis or participant-written code on the current query |

Both retain 400 queries from the two previously exposed development people. The
1,200-label feature programme and visual viewer conditions are separate routes.
No cross-person generalization, P3-specific mechanism, human comparison, native
understanding, SOTA, or complete task qualification follows from this source.

## Commands and input contract

Use an existing operator Python with NumPy; the pinned original validator needs
NumPy. The client is a standalone standard-library Python script run with
`-I -S -B`; it must not depend on imports from its working directory. The operator
supplies an existing delivery root whose `public/` contains the five original
packet files. Editable exported context files or `COMPLETE.json` are not trusted.
No input pin overrides, dataset downloads or dependency installation are supplied.

```sh
OPERATOR_PYTHON transport.py campaign \
  --delivery-root /private/operator/authenticated-delivery \
  --condition matched_waveform_programme \
  --client /private/operator/frozen-participant.py \
  --python /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 \
  --sandbox macos --wall-seconds 300 --campaign-seconds 86400 \
  --output /private/operator/new-campaign

OPERATOR_PYTHON transport.py collect \
  --delivery-root /private/operator/authenticated-delivery \
  --condition matched_waveform_programme \
  --campaign /private/operator/new-campaign \
  --output /private/operator/new-admission
```

The example limits are explicit operator choices, not a qualified scientific
compute allocation. Before an authentic run, budget the complete 400-query study
including failed attempts, source capture and cleanup. Each prompt must fit the
chosen byte limit (default 1 MiB, maximum 2 MiB) without truncation. Original
prompts were estimated at roughly 72,024–77,878 text tokens each; a byte bound is
not a model context guarantee. Provider framing, schema and output tokens also
consume capacity. Source preparation alone does not admit such a study.

The receiver gets exactly four big-endian bytes declaring a positive UTF-8 byte
length, then the complete original prompt. No packet path, context hash, ordinal,
source record, other query, labels beyond the four demonstrations, configuration
or operator metadata is added to that payload. It returns the same framing around
the original two-field JSON response, with at most 4,096 response bytes:

```json
{"trial_id":"the-current-query-identity","target_probability":0.25}
```

`scripted_client.py` is a fixed-0.5 framing example. Executing it is an engineering
control, never a model trial. A numerical programme can compute its answer inside
that standalone process. The first complete response frame is final even when its
JSON is invalid; additional frames cannot replace it. The exact first frame is
retained. Bytes queued after the first response are not read or claimed captured.
The process must then exit successfully within two seconds and the episode
deadline. Nonzero exit, invalid response, partial framing, capacity failure,
timeout or failed cleanup makes the episode unscoreable.

## Complete evidence and admission

The campaign freezes the client once as `CLIENT.py`, records its hash/interpreter,
sandbox and limits, and checks that same client before every dispatch. Each query
has a distinct episode ID, fresh process, empty temporary working directory and
minimal locale-only environment. Operator files stay outside the client cwd;
only stdin/stdout pipes are inherited. `INPUT.bin` contains the exact bytes written
to the pipe; `OUTPUT.bin` contains the first complete response or exact observed
partial bytes. `MANIFEST.json`, `ATTEMPT.json` and `END.json` bind request identity,
context hash, bytes, process exit and cleanup. The full ledger keeps successes and
failures. There is no resume, retry, replacement or best-of selection.

A campaign deadline may prevent later queries from starting. Those rows are
explicit errors with `launched: false`, not invented participant attempts. The
complete inventory reports actual launches and failures separately. A filesystem
or source error can leave an incomplete directory with `FAILED.json`; it must not
be reinterpreted as a complete campaign.

Collection reconstructs all original prompts and replays all 400 transport records,
configuration, exact first-response bytes and receipt commitments. Mixed conditions,
missing/failed episodes, altered clients, changed source, extra members, repeated
episode IDs and modified ledgers are refused. The existing collector validates the
complete NPZ and produces `submission.npz` plus its unchanged `COMPLETE.json`.
The new `TRANSPORT_COMPLETE.json` records full **unscored local collection**.
Use the existing `portable-grading/score.py` under a separately admitted private
operator protocol to grade that NPZ. The existing paired comparator supports
descriptive same-query comparisons; condition and provider provenance still need
their own operator review.

## Isolation and limits

`macos` uses a deny-default `sandbox-exec` profile based on the existing viewer
transport: network, process fork, other-process inspection and operator-file data
access are denied. It allows the selected frozen client file and standard runtime
locations `/System`, `/usr`, `/Library/Frameworks` plus specified system identity
and device access. Those runtime locations must not contain private operator data.
The standard-library client can perform numerical computation; this is not a
general package-installation or external-tool environment. Runtime capability and
wall budgets must be reported when comparing methods.

`protocol_only` is a trusted bridge mode without an OS filesystem/network sandbox.
Fresh processes and empty working directories cannot prove a remote model's
fresh context or prevent privileged access, external state, tools or escaped
descendants. The runner attempts to kill its own process group and reaps its direct
child; it explicitly does **not** certify descendant absence. It enforces wall and
wire bounds, not CPU or memory limits. A study needs its own complete resource and
isolation admission; this mode must not be credited as no-tools enforcement.
The recorded `private_target_reads: 0` describes the trusted runner/collector's
own code path; it does not audit arbitrary file activity by an unrestricted
`protocol_only` participant.

The macOS profile denies network, so it cannot directly call a remote model API.
A trusted provider bridge must enforce and record fresh requests, no history,
no tools/retrieval, full untruncated prompt delivery and exact output. A new local
process alone establishes none of those provider properties. Hashes bind recorded
bytes, not proof against a privileged operator coherently rewriting all records.
Input/output parents must be trusted, ordinary, unlinked paths without concurrent
hostile writers. Prior failed attempts and already exposed targets remain exposed.

## A concrete no-tools provider connection

`provider_bridge.py` connects this runner's binary stdin/stdout protocol to one
OpenAI Responses exchange. The operator injects `send_json(request_bytes)` and
`record(receipt)`; no HTTP client, credential lookup, SDK, network call or model
selection is bundled. Its request uses one exact user prompt, an explicit model
and output-token allocation, no tools, no retained conversation, disabled
truncation and a strict scalar-response schema. It rejects incomplete/error/refusal,
tool-call, history, policy, model and output-budget mismatches. The original task
parser remains authoritative. These fields follow the official
[Responses create reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
and [structured-output guide](https://developers.openai.com/api/docs/guides/structured-outputs),
checked on 2026-11-17.

An operator-owned client wrapper supplies the authenticated sender and a private
receipt sink, then invokes the adapter exactly once:

```python
# The wrapper first authenticates and loads the exact reviewed provider_bridge.py
# bytes from its operator-provisioned source, using the SOURCE_FREEZE.json pin.
# It supplies a sender and sink whose complete source and configuration are also
# frozen in the study protocol. The runner captures this wrapper as CLIENT.py.
bridge.serve(
    sys.stdin.buffer, sys.stdout.buffer,
    model=explicit_resolved_model_identifier,
    max_output_tokens=declared_output_allocation,
    send_json=authenticated_single_request_sender,
    record=private_exclusive_receipt_sink,
)
```

The sender accepts immutable JSON-body bytes and returns only bounded raw JSON
response-body bytes. It must set its own endpoint/timeout/authentication, enforce
the response size during HTTP reads, retain exact request/response bodies and
all failed requests, and perform **no automatic retries**. Credentials or HTTP
headers must never enter the adapter, participant prompt, logs or receipt sink.
The adapter records hashes plus a bounded response ID, model, token counts and
outcome, never exception strings. If recording fails, no answer is emitted.
`sender_calls_attempted` counts the injected callable's invocation; a generated
sender is not a model call. Output text is returned unchanged in the original
scalar frame, and every failed exchange makes the runner's query fail.

Use a concrete resolved model ID: the adapter refuses a response reporting a
different ID, including silent alias resolution. Supported structured-output
options, full input-token capacity, output/reasoning-token budget, and provider
policy must be qualified for that selected model before an authentic campaign.
The record hashes do not independently establish that a sender used the intended
provider. The operator must authenticate its actual transport and provider
receipts. No live bridge or paid API has been exercised by these source controls.

This adapter accepts only `legacy_waveform_no_tools` prompts. It is not a viewer,
tool-using agent or matched-programme solver. A live remote bridge requires the
separately reviewed `protocol_only` path because the local macOS profile denies
network; that fact does not remove the provider-isolation requirements above.
Its sender/sink and adapter dependency must be immutable for the complete study;
the runner's wrapper-file hash alone does not freeze arbitrary imported modules.

## Verification

`test_transport.py` exercises invented inputs through real child processes and
the existing scalar parser/complete collector. Its complete generated 400-query
case uses actual NumPy serialization and the unchanged validator. It is software
evidence, not authentic EEG preparation or a participant study. Run through the
shared lightweight pool with one thread and at most 1 GiB/180 seconds:

```sh
EXISTING_NUMPY_PYTHON -I -B -m unittest discover \
  -s benchmarks/neural/NEURAL-077/implementations/waveform-transport-v1 \
  -p test_transport.py -v
python3 -I -S -B -m unittest discover \
  -s benchmarks/neural/NEURAL-077/implementations/waveform-transport-v1 \
  -p test_provider.py -v
```

The provider controls use an injected generated sender, including one real local
child that connects `serve()` to the runner and one fixed scripted-client smoke
control. They exercise request policy and failure handling without a model,
network access, authentication material or provider capacity measurement.
