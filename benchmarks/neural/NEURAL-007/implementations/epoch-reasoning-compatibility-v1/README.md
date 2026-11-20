# Optional reasoning compatibility for isolated sleep epochs

This source adapter connects the existing bounded current-turn reasoning parser
to the existing `epoch_isolated_raw_viewer_zero_shot_v1` per-target sender and
custody replay. It selects no model and changes no default provider route. It
adds no task, renderer, training asset, programme or scorer. A small explicit
selection hook in the existing admission source retains its collector loops.

The original condition still requires all 5,450 thirty-second targets across
two already exposed development people: 2,780 from development-001 and 2,670
from development-002. Each target retains all three original 100 Hz channels
and its three clock features. Every request contains the immutable complete
epoch PNG overview and at most one current same-target detail. No prior image,
action, target answer or opaque reasoning item is replayed. Allowed viewer
actions, epoch isolation and the irreversible first accepted five-class answer
are unchanged. Epochs are not independent biological subjects.

## Explicit operator interface

The caller supplies already-loaded **trusted** `epoch_provider` and the original
`epoch_visual.load_runtime(...)` result. Loading those existing modules and
admitting their source/dependency/runtime closure remain the caller's job.
The preferred complete-arm route uses an explicit operator-owned selection:

```python
selection = {
    "execution_policy": "current_turn_reasoning_v1",
    "reasoning_effort": explicit_effort,
    "adapter": pinned_adapter_descriptor,
    "bindings": pinned_adjacent_bindings_descriptor,
    "reasoning_provider": pinned_existing_reasoning_source_descriptor,
}
adapter = epoch_reasoning.load_selected(selection, epoch_provider, runtime)
adapter.run_epoch(packet, knowledge, budget, fresh_private_custody,
                  credential, complete_input_token_bound,
                  session_id=fresh_target_session)
adapter.audit_session(fresh_private_custody, packet, knowledge)
```

Each descriptor contains an absolute `path`, exact `bytes` and `sha256`.
Policy and effort are required; a wrong policy or unsupported listed
effort fails. The list of efforts comes from the pinned existing parser and
does not establish any selected provider/model's support. No automatic fallback,
retry, provider call or data load occurs at binding. `adapter.policy` returns
a copy of the frozen selection and source identity. The lower-level
`bind(epoch_provider, reasoning_provider, runtime, *, execution_policy,
reasoning_effort)` interface also accepts an already-loaded trusted parser;
its distinct parser-binding provenance is frozen, so those sessions cannot be
silently relabelled as sessions from the selected private loader.

The adapter authenticates the seven named donor source/binding files in
`SOURCE_BINDINGS.json`, captures its own source and binding pins, copies the
runtime's source descriptor, and binds policy/effort/parser/adapter identities
into private configuration. Already-loaded code objects and runtime modules
remain trusted operands: matching file bytes do not prove hostile-host execution
or package-binary identity. The unchanged original loader still owns its full
transitive source and renderer closure. The selected loader authenticates the
exact pinned reasoning source, requires exactly the known
`previous = load_previous()` startup assignment, removes only that assignment
from its AST, and injects the authenticated original provider already present
in the runtime. The original parser class and method bodies remain unchanged.
This trusted transformation is recorded as
`pinned_previous_initializer_removed_v1`; a different source/shape fails.
The private module is never registered in `sys.modules`, and the donor's fixed
module-name loader is never called. No donor module registration is overwritten.

Original `run_epoch` and `audit_session` code objects are rebound to a private
globals dictionary. Only request construction, response parsing and private
configuration/event/end helpers are supplied in that private dictionary. No
donor function, class, dictionary, global module registration or caller runtime
is modified. A proper private subclass context invokes the existing reasoning
parser with its original `super()` behavior; no large sender or replay loop is
copied.

## Requests, responses and private evidence

The original request is retained with explicit
`reasoning={context: "current_turn", effort: selected_effort}` added. Its complete
byte length is checked again against the original request/sender ceilings.
The caller's existing complete-input bound callback must cover this exact final
request, including images and reasoning configuration. It remains unqualified
until separately supported; this source invents no token estimator.

The pinned parser requires an exact matching effective reasoning policy, at most
eight bounded opaque reasoning items and one final visible action message. Its
262,144-byte opaque allowance and original response/token/action rules remain.
The original exact response is durably retained privately before an action is
applied. Successful parser metadata preserves full usage and opaque item hashes;
opaque content itself remains only in the private original response. Failed
responses retain their raw bytes even if no structured projection is possible.
A separately bounded private status/usage/policy projection may be retained;
it never authorizes an action and contains no copied output items. Existing
receipt byte limits still refuse oversized metadata. Public results contain
neither opaque contents nor a reasoning transcript.

Per-target replay reconstructs the same final request, uses the same selected
parser/effort, verifies exact custody and returns the original first answer.
Wrong effort, altered request/source/configuration, other-target answers,
incomplete responses and malformed or over-bound reasoning cannot become an
accepted answer. `prior_turn_opaque_replay` is always false. Neither that field
nor stateless requests prove a remote context reset or image consumption.

## Complete collection and scientific limits

The staged `epoch_admission.py` extends `collect_visual` with the optional
`reasoning_compatibility=selection` keyword. Its original default is unchanged.
The protected pair request accepts the same optional selection field, and both
the coordinator and fresh grader independently authenticate the selected source
operands before loading this adapter. Only the trusted copied runtime chooses
the per-target auditor; participant records cannot choose an implementation.

The complete visual collection freezes the selected policy, effort and source
identities. Paired admission requires that exact policy to match the selected
runtime before original waveform replay or private truth. Per-target replay
also checks exact original CONFIG/request/response/source custody. Consequently,
an ordinary collection, a different effort/adapter or an ordinary target session
cannot be promoted by merely adding a pointer. The programme collection remains
separate and receives no reasoning field. The existing eight-member epoch source
freeze is unchanged in shape; its selected admission-file pin must reflect this
revision, and the optional adapter has its own explicit authenticated chain.

Do not substitute a partial roster or describe a successful per-target generated
control as a complete arm. The original complete 5,450-row submission contract,
protected scoring order and equal-person fixed W,N1,N2,N3,R macro-F1 are unchanged.

## Portable generated-control staging

Publication places `epoch_reasoning.py`, this README and `SOURCE_BINDINGS.json`
in `benchmarks/neural/NEURAL-007/implementations/epoch-reasoning-compatibility-v1/`.
The revised `epoch_admission.py` replaces the file of that name in the existing
`epoch-isolated-pair-v1/` directory. These are four authored source/documentation
files; unchanged donor runtime members are not duplicated into the new component.

The generated control script `test_epoch_reasoning.py` takes exactly three
positional arguments: `WORKSPACE`, `SOURCE`, and fresh `CONTROL`. `WORKSPACE` is
the checkout containing the pinned original runtime dependencies. `SOURCE` is
an operator staging directory containing exactly the four files named above
together: copy the three new-component files and the revised admission file
from their separate publication destinations. This staging bundle is an explicit
test arrangement, not an alternate package or runtime-selection change.

```text
ADMITTED_PYTHON -I -B /path/to/test_epoch_reasoning.py /path/to/checkout /path/to/four-file-source-bundle /path/to/fresh-control
```

Use the separately admitted existing runtime and finite generated-only campaign;
the command is an interface illustration, not permission to allocate a new run.
It requires no private path embedded in source, no source rewrite, and no
authentic data/model/provider operation. The complete numerical/biological
limitations above still apply to every generated control.

No authentic signal/label/result, original waveform, live provider, model,
scoring, native image or complete-cohort execution is established by this source.
Provider capacity/behavior, token bounds, actual runtime and scientific
qualification remain false or unknown. Current-turn reasoning is internal
model computation, not an external signal-analysis tool. Visual/numeric
representations are not proven information-equivalent; the exposure and
matched-agent limitations of the original paired condition remain. The two
development people provide no untouched-test or population-generalization claim.
