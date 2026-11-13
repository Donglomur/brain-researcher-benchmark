# NEURAL083 portable preparation and study setup

This checkout contains the actual full preparation, numerical tool, model
transport, adaptive/frozen scheduler and protected scorer source. `setup.py`
composes their real metadata interfaces without importing that code, opening
recordings, contacting a model, starting Docker, or issuing positive authority.
The supplied environment recipe constructs numerical dependencies; it does not
provide a model server or weights. Source publication alone is not a completed
scientific benchmark.

The complete support is **54 people, two sessions and 108 source records**.
Each record has 100 offline and 100 online trials. Four training settings and
three signal arms give 1,296 conditions per panel; candidate plus original
reference give **2,592 conditions**. The candidate investigates 129,600 queries,
but these are repeated condition-specific uses of 10,800 unique source online
trials, not 129,600 independent biological samples. Biological n remains 54.

## What each comparison means

| Choice | Actual behavior |
| --- | --- |
| `case_adaptive_equal_inputs_tools_compute` | Fresh conversation, workspace and pointwise investigation for each query; model chooses analyses and its own probability or abstention. |
| `frozen_program` | One Python body selected before the study; the same single-query native interface and prospective tool allowance; no model request. |
| `decoder_alone` | Fixed supplied decoder, with no model request or arbitrary participant programme. |
| `generic_numerical` | Permitted training bank and current query are available, but no supplied fitted task decoder. |
| `agent_plus_decoder` | The same permitted interface plus the original fitted decoder probability; the actor may disagree with it. |

The generic mode withholds the **fitted decoder**, not knowledge of its algorithm.
Fixed tool/reference source is inspectable in the container. Do not describe this
as a hidden-algorithm experiment. The numerical tool cannot retrieve external
sources or other online queries, but filesystem isolation alone cannot prove
that arbitrary submitted Python obeys the scientific nonadaptation rule.

EEG, CONTEXT and PERMUTED_EEG are the signal arms inside each comparison. They
are not model/tool modes. The four settings are `target20`, `transfer0`,
`target100`, and `other_session20`: all use offline donor records from other
people; the permitted target calibration is respectively 20 current-session,
zero, 100 current-session, or 20 other-session offline labels. No online query
label or score is an actor input. Cross-query conversation, fitting on online
queries, accumulated online state and replacement of the frozen training bank
are prohibited by the existing method contract.

The preserved older batch frozen programme and this pointwise frozen comparator
have different input exposure. Do not merge their results under one access-mode
label. One explicit query abstention makes its entire 100-query condition
abstain under the unchanged original endpoint; it does not remove that condition
or authorize skipping the remaining roster.

## Software and storage prerequisites

Use `environment/README.md` for the concrete hash-locked numerical image build
and fresh host venv commands. The prospective versions are CPython 3.11.11,
NumPy 1.23.5, SciPy 1.10.1 and scikit-learn 1.2.1, with their exact five runtime
and three bootstrap wheel artifacts. No numerical parity with the original
paper is asserted. The actual preparation parent must run with the venv's
interpreter: it owns a child that intentionally enables site discovery for
NumPy/SciPy. The adaptive host and metadata helper otherwise need stdlib only.

Supply an existing compatible Docker binary and Unix socket, the **actual built
image Id**, and an admitted Linux/container/cgroup/resource deployment. The
native source is implemented, but the image, Docker service and actual process
and descendant closure have not been qualified by source inspection. Container
receipt checks are not a substitute for platform evidence. Inherited raw native
failure-stream limitations remain as documented in the runtime source.

The public inventory's 108 original MAT objects total **64,847,432,285 bytes**.
This is the complete raw cohort, not a download caused by setup. The projected
float32 numeric payload is 433,728,000 bytes before metadata and processing
intermediates. Full-study cumulative read/write reservations can be much larger
because training views and model captures repeat across conditions. For example,
the original model-capture maximum is 512 MiB per condition; multiplying this
source ceiling is not a claim that every fitted model actually has that size.
Choose real storage, runtime, model and native resource envelopes before a run.
The helper never silently reduces the cohort to fit available storage.

## Source admission and helper behavior

The public layout is:

```text
setup.py
SETUP.md
templates/
environment/
package/SOURCE.json
package/entry.py
package/inherited/SOURCE.json
package/inherited/entry.py
package/inherited/preparation/prepare_entry.py
package/inherited/preparation/source-inventory.json
package/inherited/scientific-source/
package/inherited/program/
```

Supply the exact published `package/SOURCE.json` byte/SHA256 pin as the JSON
operand `SOURCE_PIN_JSON`. The helper authenticates that manifest, every selected
adaptive member and the entire inherited source table **before writing**. It
derives the current provider/source pins from those captured files, so relocation
does not depend on a private author's directory or old commit path. It imports
none of the task modules. The selected entry/interpreter/public source revision
remain external trust roots; a script cannot grant itself that authority.

Every helper invocation has an 8 MiB ordinary metadata/source read ceiling, a
2 MiB output ceiling and a cooperative 30-second interval. This is a small setup
operation, not the scientific resource budget. Output directories must be fresh,
unlinked and separate from task sources, programme outputs and protected
preparation roots. Files are create-only. A failed composition leaves its exact
partial output in place and does not retry or clean up unrelated files.

Maintain exclusive writer or read-only custody over selected source/configuration
files while composing and invoking the actual operator. The helper's stable FD
captures authenticate their own reads; they do not prove that later consumers'
pathname reads cannot be changed by another writer. Do not move generated
bundles: absolute descriptor paths participate in configuration hashes.

## 1. Bind the full original recordings and observed MAT schemas

The source is [OpenBMI / GigaDB 100542](https://gigadb.org/dataset/100542), associated
with [the original publication](https://doi.org/10.1093/gigascience/giz002).
The public inventory preserves only exact person/session/filename/extent fields
and public provenance. It contains no private acquisition URLs, neural content,
labels or verified content hashes. The old private inventory is not required.

Obtain the legitimate original objects separately. Fill
`templates/verified-source-manifest.UNSELECTED.json` with their independently
observed SHA256 values; keep every original filename and extent. Setup checks
the complete 108-row identity/extent join and distinct digest declarations but
does not open or authenticate the recordings. Authentic acquisition and support
remain separate evidence.

There are 108 individual templates in `templates/bindings/`. For each actual
record, supply the observed ordered 62 channel names, the actual `class` or
`y_class` field name, and observed distinct integer left/right codes. Nulls are
deliberate unresolved inputs; no channel or label mapping is guessed. The actual
mapper later checks both native phases, 1,000 Hz, 62 channels, 100 onsets and
balanced class/one-hot/name agreement. It performs the unchanged selected
resample/filter/window operation and writes 200 × 251 × 20 float32 epochs.

Fill `preparation-project.UNSELECTED.json`, retaining all 108 ordered binding
descriptors, and `preparation-owner.UNSELECTED.json`. Select real cumulative
read/write/retained limits and the actual original monotonic deadline on the
execution host. The deadline must fall inside the selected enclosing owner's
work interval; a stale request is not reusable by renewing its timestamp after
failure. The helper constructs the real preparation request and its real parent
operation request:

The helper refuses null, Boolean or out-of-range scalar placeholders: each
preparation read/write/retained limit is 65,536..1,000,000,000,000 bytes; each
owner metadata limit is 65,536..67,108,864 bytes. The project serialization
ceiling must exceed 4,116,000 bytes and be at most 8,000,000 bytes per record.
The selected preparation owner interval is more than 30 and at most 604,800
seconds, with its existing 15-second work cutoff retained. An emitted request
still needs to reach that owner before its original monotonic deadline.

```text
/SELECTED/venv/bin/python3.11 -I -S -B setup.py prepare-project \
  --source-pin SOURCE_PIN_JSON \
  --configuration /absolute/filled-project.json \
  --owner-selection /absolute/filled-preparation-owner.json \
  --evidence-output /FRESH/project-owner-evidence \
  --output /FRESH/project-command-bundle
```

It automatically supplies the exact public source-inventory descriptor from the
authenticated inherited source table, captures the supplied source-manifest and
all observed binding documents, and emits `PREPARATION_REQUEST.json`,
`OWNER_REQUEST.json`, `AUTHORITY.DISABLED.json` and `COMMAND.NOT_EXECUTED.json`.
The command invokes the **actual** `package/inherited/entry.py prepare-project`
owner, which runs the captured original preparation source. Nothing is launched
by setup. Root must separately issue the exact request/source-bound authority;
changing a generated false flag is not independent scientific admission.

After the genuine project operation returns, populate
`preparation-finalize.UNSELECTED.json` with its actual `PROJECTION.json` and
select a separate protected product root. Supply the descriptor of a separately
selected private 32-byte identity key. Setup never reads, creates, hashes, copies
or prints the key body. Run the analogous helper command `prepare-finalize`.
The actual finalizer authenticates every record, creates the canonical index,
panel and protected targets, seals its outputs and produces `COMPLETE.json`.
Its parent produces `PREPARATION_CLOSURE.json` from the actual child closure.
Neither file grants independent authentic-input admission.

## 2. Select a comparison and a model service, if needed

Five complete configuration templates cover the permitted pairings: adaptive or
frozen programme with generic or decoder-assisted tools, and decoder alone.
Select one template per actual comparison. Set real image, paths, native/query
limits and full worker budgets. Keep `preparation_costs` and `method_review`
null for the initial composition. Point preparation descriptors to the actual
completion, closure and separately issued input review. Adaptive mode supplies
an exact prompt descriptor; frozen mode supplies the exact committed Python
programme; decoder alone supplies neither. Frozen code assigns either
`result={"p_right":...}` or `result={"abstain":"..."}` through the same fixed
single-query tool. No default predictor is manufactured by setup.

For adaptive mode, fill `provider-study.UNSELECTED.json`. The two full
`provider-configuration.*.UNSELECTED.json` files document every actual provider
field and action schema; setup derives actions, provider-source SHA256 and the
frozen study hash rather than trusting manually copied bindings. Runtime adds
`owner={condition_id,query_id}` and `request_id` per call; they are not study
configuration fields.

Setup's draft step checks the outer study shape and computes bindings and token
reservation floors; it does not replace the runtime provider's full nested
configuration validator. An incorrectly filled study can still be rejected by
that validator. In particular, request bytes must be 256..1,048,576; response
bytes 256..4,194,304; header bytes 64..min(32,768,response bytes); message count
1..512; aggregate message content bytes 1..request bytes; action content bytes
1..min(65,536,response bytes) for this caller; and reported prompt-token cap
1..1,048,576. The five-file capture allowance must be at least
589,824 + request bytes + response bytes and at most 16,777,216 bytes. Generation
maximum output tokens is 1..32,768, temperature is finite 0..2, and seed is an
integer 0..2,147,483,647. These are interface ranges, not selected study defaults
or evidence that a server supports them.

The implemented transport requires a canonical **loopback IP literal**, an
explicit port and path, and a synchronous HTTP/1.1 service. It sends a nonstreaming
OpenAI-compatible chat-completions request with `n=1`, fixed temperature, seed,
maximum output tokens, and a strict JSON-schema response format for the actor
action. The server response must have the exact selected model identity, one
assistant choice with `finish_reason="stop"`, a JSON action in `message.content`,
and reconciled prompt/completion/total usage. Supported actions are `python`,
`predict`, `abstain` and, only for decoder-assisted mode, `decoder`. Standard
`tool_calls` responses, streaming, chunked/compressed bodies, redirects, DNS,
authentication and proxy routing are not accepted. The numerical Docker image
does not supply this service.

Model-server software/version, weight identity, hardware allocation, context
reset/statelessness, ownership, timeout/cancellation behavior and final closure
are **unsupplied deployment inputs**. No particular server is assumed compatible
merely because it advertises an OpenAI-style endpoint. Independent evidence must
establish the actual supported protocol and absence of cross-query hidden state.
The transport uses a fresh socket and transcript, but that alone does not prove
server isolation. The current source phase selected no model service and made
no model request. Frozen and decoder-alone modes need no model service.

## 3. Compose costs and method review without hash cycles

Use the selected venv interpreter and explicit fresh output directories for each
stage. For adaptive mode only, include `--provider-study`; omit it for the other
two entrants:

```text
python3.11 -I -S -B setup.py draft --source-pin SOURCE_PIN_JSON \
  --configuration /absolute/filled-configuration.json \
  --provider-study /absolute/filled-provider-study.json \
  --output /FRESH/configuration-stage1
```

This freezes `PROVIDER.json`, emits `CONFIGURATION_BASE.json` and the exact
`PREPARATION_COST_BINDING.json` for a separate actual cost record. That binding
uses the runtime's canonical JSON: sorted keys, compact separators, ASCII escaping
and a trailing newline, excluding `method_review` and setting
`preparation_costs=null`. The provider study hash instead uses UTF-8 JSON without
ASCII escaping or a trailing newline. These encodings are deliberately distinct.

After actual preparation/construction costs are recorded externally:

```text
python3.11 -I -S -B setup.py bind-costs --source-pin SOURCE_PIN_JSON \
  --configuration /absolute/stage1/CONFIGURATION_BASE.json \
  --costs /absolute/actual-preparation-costs.json --output /FRESH/configuration-stage2
```

This emits `CONFIGURATION_WITH_COSTS.json` and `METHOD_BINDING.json`. A separate
review must assess the complete science, source, exposure, immutable training,
provider identity/state, native resource profile and matched costs against those
bindings. Once that genuine document exists:

```text
python3.11 -I -S -B setup.py bind-method --source-pin SOURCE_PIN_JSON \
  --configuration /absolute/stage2/CONFIGURATION_WITH_COSTS.json \
  --method /absolute/independent-method-review.json --output /FRESH/configuration-stage3
```

The helper verifies the document's identity joins and emits the final
`CONFIGURATION.json`. It does not judge the scientific truth of the review,
issue that review or authorize execution. Runtime still enforces every required
admission field. `*.UNISSUED.json` and `*.UNRECORDED.json` are interface
templates, never passing evidence.

## 4. Produce an actual invocation, then grade separately

Generate the source-bound request and literal argv for inspection or a separately
authorized run:

```text
python3.11 -I -S -B setup.py request --source-pin SOURCE_PIN_JSON \
  --configuration /absolute/stage3/CONFIGURATION.json --operation run \
  --evidence-output /FRESH/run-owner-evidence --output /FRESH/run-command-bundle
```

`COMMAND.NOT_EXECUTED.json` references a disabled authority for `run`/`grade`.
A root operator supplies a separate exact request/source/operation-bound
authority descriptor before invoking that command. The `inspect` operation
requires no authority and uses no preparation data. Setup never runs any emitted
command. Positive flags in a completion JSON are not independent permission or
qualification.

The actual run owns the worker and writes `OUTER.json` after its original child
closure. For a later separate grade operation, `extract-terminal` accepts that
actual outer file through `--outer-run`, the same final configuration and a new
output directory. It extracts the actual `RUN_WORKER_TERMINAL.json`; it does not
create an outer proof. `EXTRACTION.json` records the canonical pin of the
terminal's **result object**, which the existing protected replay binds. The
independent outer proof's configuration is the runtime's expanded selection
(including canonical/index roots and the captured scientific-source repository),
not the earlier method-binding hash. Use the actual run commitment/closure for
that evidence; do not fabricate it from a setup template.

Generate the grade request with `--operation grade --terminal` pointing to the
actual extracted wrapper and `--outer-proof` pointing to the independently issued
complete execution admission. The grade command authenticates/replays the full
actor/native/cost history and both panels before its one protected target read.
Run requests accept no target or grade operands. The helper never opens targets
or emits a scientific score.

## Full cost and information budgets

For M model calls permitted per query, adaptive reservation requires at least
129,600 × M requests, that quantity × the provider prompt-token cap, and that
quantity × maximum output tokens. Setup emits these floors and refuses a smaller
declared model allowance. They are not a complete resource estimate. At M=2,
the prospective reservation is 259,200 model calls. Native work additionally
includes 2,592 training constructions and 1,296 reference inference calls, plus
the selected candidate's full pointwise calls. No reduced diagnostic cohort can
claim the complete result.

All adaptive tool rounds share one selected native-seconds total per query and
one original query wall deadline; failed grants receive no refund. The frozen
programme receives the same native opportunity in its sole pointwise call.
Actual consumed model/tool/preparation costs are recorded separately. Independent
comparison review must match the real input, tool and prospective compute
policies rather than equating the number of HTTP requests with compute.

Worker `reads`, `writes` and `retained` are logical reservations, not filesystem
quotas or physical I/O/RSS measurements. The source-selected full operation adds
32 MiB owner-preflight reads and two 16 MiB read/write/retained evidence reserves:
worker reads +64 MiB, writes +32 MiB, retained +32 MiB. The corresponding native
container/model-server resources need their own real owners. A successful setup
or invented engineering control does not provide that deployment evidence.

The Linux process owners also precharge 65,536 bytes of `/proc` identity metadata
per invocation through the existing selected read allowance. A native phase
with its full 64-command allowance therefore needs up to an additional 4 MiB
of such read reservations, beyond the unchanged stdout/response allowance.
Include the actual selected number of phases and owner invocations in the
prospective full-study envelope. Setup does not enlarge any budget automatically.
The adaptive whole-operation interval must be more than 60 and at most 604,800
seconds, including the fixed 30-second observer reserve.

No imports, tests, source helper invocation, environment construction, Docker
operation, model request, authentic data/header access or scientific execution
was performed when authoring these setup additions. Existing engineering evidence
is version-specific; it does not qualify this new setup or a future deployment.
