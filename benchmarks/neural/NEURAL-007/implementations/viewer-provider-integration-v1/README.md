# Whole-person viewer provider integration

This additive NEURAL-007 source package supplies the existing viewer Bridge's
trusted HTTPS and durable recording callbacks, a descriptor-based client, and a
small trusted-launcher addition to the existing whole-person transport. It reuses
the exact NEURAL-077 `waveform-provider-v1/client.py` Sender, Custody, Alarm and
pipe reader. It does not replace the original viewer, probability validator,
whole-person collector, protected scorer or scientific condition.

Both original people remain mandatory: 2,780 and 2,670 epochs, 5,450 total. Every
complete three-channel target view precedes its first accepted answer; accepted
answers cannot be replaced, and finish requires the entire person. The unchanged
Bridge repeats the exact original PNG bytes and complete visible conversation in
each request. No image transformation, omitted history, chunking, summaries or
alternate condition is introduced.

## Current capacity hold

The unchanged canonical Bridge permits at most 1,500 images. It rejects either
original person after the original ready frame and before the token-bound or
sender callbacks. The reused Sender adds its existing 8 MiB request ceiling; its
524,288-byte response ceiling, one-call policy, TLS checks, no redirects and no
retries remain intact. This source cannot currently produce a complete canonical
provider arm. The prospective last32 condition is not accepted here.

There is no invented token estimator. `run_session` requires an explicit external
complete-input bound callback. The executable client optionally loads the exact
operator-supplied source identified by `token_bound_source`; a null source refuses
the callback if reached. Source identity alone is not proof that an estimator is
conservative. Token/context/image capacity, remote isolation and actual provider
behavior remain unqualified. All generated and actual client records retain
false qualification fields. Neither the callback nor a generated fixture can
award scientific readiness or provider qualification.

## Interfaces and custody

`client.load_runtime(workspace_root, integration_root=None)` authenticates the
existing Bridge/policy/bindings and unchanged HTTPS Sender, then loads the local
transport derivative with an explicit trusted dependency root. It returns
`provider`, `sender`, `transport`, `source` and `integration_root`.

`client.checked_config(config, runtime)` validates exact canonical case, model,
budget, roots, source identities and optional external token-bound source pin.
`run_session(runtime, config, credential, custody_fd, binary_in, binary_out,
input_token_bound)` connects the original Bridge to the trusted callbacks. The
client CLI accepts only inherited credential, configuration and custody descriptor
numbers; it exposes no fake transport or qualification option.

`operator.run_person_provider` uses the original binary transport and an explicit
trusted descriptor launcher. Its `protocol_only` process is an operator process,
not the network-denying participant sandbox. The transport's default launcher and
macOS sandbox are unchanged. `operator.run_complete` requires both complete
people and matching model/configuration/budget, stops on failure without retry,
and calls the original collector only after both complete. It must receive
already admitted runtime, packet and credential operands; it is not an authority
to acquire data or execute a provider.

The trusted launcher deliberately uses the selected existing venv entrypoint with
`-I -B` so the original probability validator can import that runtime's NumPy.
Only the trusted branch preserves that entrypoint rather than resolving away its
venv path; the participant launcher's original `-I -S -B` behavior is unchanged.

The fresh private custody directory has exactly `CONFIG.json`, `events/`,
`turns/` and `CLIENT_END.json`. Numbered event JSON files bind each exact original
Bridge metadata record and its hash chain to the configuration and original
deadline. Each attempted Sender turn uses its original four files:
`REQUEST.bin`, `RESPONSE.bin`, `HTTP.json` and `BRIDGE.json`. The exchange event
and `BRIDGE.json` decode to the same wrapper; the latter intentionally uses the
original Sender's JSON encoder, including its newline. Request and response
bodies are not rewritten by the recorder. The existing transport retains exact
viewer frames and PNGs independently for reconstruction and first-answer audit.
The companion fresh-admission implementation must replay and compare these
bytes; completion and qualification flags alone are insufficient evidence.

The Sender reserves response space before a request. On a failed send, the client
charges the full bounded response extent, including the possible overflow byte,
when retained safe bytes could understate consumption. Successful decoded
credential echoes are rejected before action/metadata emission; the unchanged
Sender guards literal raw echoes. This does not assert that arbitrary escaped
credential text is absent from private raw failed responses.

## Resource accounting

Every session declares the original Bridge's turn, image, history, request,
response, cumulative provider-byte, context/output token and wall bounds. The
callback adds the unchanged 8 MiB sender ceiling and reserves response overflow
custody. Per-person transmitted bytes are bounded by `max_total_provider_bytes`;
the complete two-person maximum is twice that allocation. Stored Sender bodies
are bounded separately by those exchanges. Event/HTTP metadata and original
viewer journals/images are additional retained artifacts, not API bytes. No
future provider campaign or artifact allocation has been selected here.

The positive generated fixture uses five fake HTTPS exchanges, two synthetic one-pixel RGB
images and the actual Bridge/Sender/Custody code. A scoped in-memory two-epoch
test roster is restored after the component fixture. It is marked
`GENERATED_COMPONENT_ONLY`, never passed through public admission as a genuine
completed arm, and cannot be selected through production configuration. Separate
controls require both original people to fail before any sender/token callback.
An additional one-turn generated fixture forces receipt-sink failure and requires
the prepared action to be withheld; a mock process-launch control checks inherited
descriptors and exact argv without launching a child.
Actual existing NumPy validates the generated probability vectors; no substitute
scorer is supplied.

Tests are `tests/test_sender.py`; they require explicit
`N007_SENDER_SOURCE_ROOT`, `N007_DEPENDENCY_ROOT` and `N007_CONTROL_ROOT`.
The admission controls import the same `generated_session` fixture. No fixture is
deleted automatically. `fixture_accounting()` reports created extents, including
partial failures; admission mutations require separate cumulative-write charges.
The conservative sender fixture allocation is 2 MiB, with at most 256 KiB of
additional admission mutation writes. Original waveform rendering, dataset reads,
real HTTP/model requests and imports during source preparation are excluded.

## Source and publication map

Publish this directory as
`benchmarks/neural/NEURAL-007/implementations/viewer-provider-integration-v1/`
only after the parent accepts the exact source map and controls. No workspace
file was changed during preparation.

| New file | Existing mechanism reused | Change |
| --- | --- | --- |
| `client.py` | N007 `viewer-provider-v1` Bridge; N077 `waveform-provider-v1/client.py` | Typed callback adapter and ordered durable event bindings |
| `operator.py` | N077 visual provider descriptor-launch pattern | Trusted N007 binary-session launcher and complete two-person wrapper |
| `transport.py` | N007 `viewer-transport-v1/transport.py` | Explicit dependency root, optional trusted launcher and preservation of its selected venv entrypoint |
| `SOURCE_BINDINGS.json` | N007 viewer transport bindings | Byte-identical dependency map |
| `tests/test_sender.py` | Existing N007 generated small-roster control convention | Capacity refusal and shared real-code custody fixture; fake HTTP only |

The base identities are embedded in `client.SOURCES`; the two transport identities
are in `client.TRANSPORT_SOURCES`. The companion finite-workflow change owns the
fresh-evidence admission branch and preserves historical admission and both
checks before private targets.
