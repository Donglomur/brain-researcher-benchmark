# Local model host for one offline F authoring lifetime

`model_job.py` supplies an actual operator-only model-job host for the selected
local Transformers provider. It is designed for the owner's captured S8 runtime
namespace and its original objects. It does not instantiate an I cell or
`BrokerLease`, run the scientific task, issue an approval, or select a model.

The constructor is:

```python
host = ModelJobHost(source, profile, operator_root, authority, runner,
                    journal, budget, carrier,
                    runtime=captured_runtime, provider_id=selected_provider_id)
reply = host.generate(label, messages, max_new_tokens)
summary = host.finish(result=source_package_pin, error=None)
```

The actual source owner is S8 `Sources`, with an actual `Authority`, `Budget`,
`Journal`, `ProcessRunner` and `FailureCarrier` from the same captured namespace.
Source and authority capture, all turns, control processes, model-subtree
observations and publication share that budget's original origin/deadline.
Construction requires an unused token ledger and no active cell. The runtime
bundle must contain common, budget, journal, process, cgroup, native_providers,
native, seals, registry, broker, resource_policy, source and authority. The owner
authenticates and loads these modules; this host checks one consistent module
namespace and retains its own copy of the mapping. This is not protection
against arbitrary mutation by a trusted Python caller.

The explicit profile contains exactly the selected local model provider, its
config, complete local model manifest, genuine external qualification, original
native image/daemon/cgroup settings, resource policy and token/call ceilings.
It uses the existing CPU float32, one-thread, greedy-generation provider. The
caller supplies messages and output-token cap; only user/assistant messages are
accepted. No F data view, reference bank, model default or hosted API is added.
The original provider's fixed system prompt remains configuration-bound.

`generate` captures the request before dispatch, revalidates the complete model
and source, reserves tokens, increments the original attempt counter once, and
uses real `NativeProviders`, `DockerHost` admission, `ProcessRunner` and `Cgroup`
implementations. Its cgroup parent enables controllers and Docker creates its
own descendant; this code never inserts a Python worker directly into that
parent. The exact request, config, runtime and model mounts are read-only.
No network or writable output volume is introduced. Attached stdout is the
provider transport and stderr is retained by the original process observer.

Container identity, natural exit, wait/removal/absence and final cgroup
CPU/memory/descendant closure are observed before usable success. Lost create
acknowledgments, failure, unknown token usage and unresolved cleanup remain
unavailable. There is no automatic retry or fallback. The raw first error and
all original objects remain in the supplied carrier/host. Invalid model text is
returned as text for the owner's declared static repair policy; the host never
executes it.

The unchanged native provider uses the field names `lease` and
`original_phase`, and role `investigator_decision`. The unchanged external
token ledger uses scope `current_postscore_operation`. Those original strings
are retained as explicit transport/bookkeeping compatibility. The outer
receipt states the actual scope `offline_f_authoring`. No cell or post-score
operation is fabricated. `reserve_external` itself does not increment the model
call counter, so this host does so exactly once. The existing ledger settles
known token usage once and retains the full reservation for unknown usage.

The return value is `{text, usage, operation}`. `usage` contains actual input and
output token counts. `operation` is a concise status/identity/receipt descriptor;
its receipt uses ordinary `{path,bytes,sha256,mode,role}` fields relative to the
same journal. Full command/provider objects stay in `host.originals`. Complete
cgroup event histories are published in ordered chunks of at most 64 KiB on the
same budget/deadline, rather than being silently dropped from a receipt. The
raw event list remains on the original scope object. `finish` writes actual
accounting and finish records and returns concise descriptors/counts/costs.
The caller's subsequent package and terminal publication must use this same
budget and remains additional incurred work.

The observed memory peak covers the owned model container subtree. It does not
include controller or Docker-daemon memory and does not satisfy the future
post-score whole-operation memory contract. Complete native logical I/O and
file churn remain explicitly unobserved. Model/runtime/isolation qualification
must come from the selected actual environment and genuine independent
evidence. These engineering controls cannot supply it.

## Retained construction evidence

`CONTROL_SELECTION.json` prospectively reserved the first 4 MiB transfer,
512 KiB fixture and 15-second tranche. Nine composition groups passed on the
preserved pre-join source: two complete turns with shared accounting, call-cap
refusal, unknown usage, incorrect mounts, nonzero exit, unresolved retirement,
system-message refusal, receipt-publication failure, and constructor failure.
Source-current, external qualification, Docker transport and kernel cgroup
operations were explicitly inert; actual registry capture, tokens, native
provider orchestration, admission, host, budget and journal paths ran.

A source review then added explicit source/authority budget identity checks and
copied the runtime mapping. The preimage is retained. The separately selected
remaining 2 MiB/512 KiB/15-second tranche ran only three focused constructor
checks on the operative source; it did not replay the full composition suite.
The independent whole review must assess this final source and the complete
parent integration.

Original natural tool results are in `ORIGINAL_RESULTS.json`. First controls:
3,223,331 transfer bytes including the stated import reserve, 439,346 fixture
bytes, 0.160217 seconds and 1,098,839 bytes post-import traced peak. Targeted
checks: 1,260,445 transfer bytes with reserve, 4,052 fixture bytes, 0.122431
seconds and 4,157,752 traced peak bytes. All 443,398 fixture bytes are retained;
no retirement or cost refund occurred. The full 6 MiB/30-second control
reservation is charged. Traced Python memory is not physical RSS. Source
reading/authoring remains inside its separate 32 MiB/8 MiB reservation.

No native container, kernel cgroup, scientific computation, authentic dataset,
checkpoint, API or model generation was executed. These files add no benchmark
registration or scientific result. Root alone installs, commits and publishes.
