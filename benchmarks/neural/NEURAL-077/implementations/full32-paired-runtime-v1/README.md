# Full32 two-episode runtime boundary

This additive sibling supplies a portable, fixed-canary delivery boundary for
the existing NEURAL-077 full32 condition. It runs two consecutive program-canary
episodes from sorted opaque roster positions 0 and 1 and saves their matched
direct-request projections. It makes no direct-model call, computes no score,
and is not a 6,400-case arm producer. The unchanged evaluator requires complete
6,400-case arms; this runtime's `RESULT.json` cannot satisfy that contract.
Infrastructure here is not an additional benchmark ID.

The supported native substrate is the macOS `sandbox-exec` recipe actually used
by the preceding implementation. The caller supplies local repository, packet,
output and interpreter paths and exact hashes. This is source portability, not
a Linux sandbox implementation. Platform-neutral generated checks do not replay
the native macOS canaries. Prior native success does not automatically qualify
this newly extracted public dependency/activation path.

`SOURCE_BINDINGS.json` uses only repository-relative locators. It binds the public
`full32-paired-benchmark-v1` evaluator, consumer and bundle; the immutable legacy
wire module; the shared owned-process helper; and the adjacent profile, episode
and canary sources. The public evaluator supplies `context_frame`, `PREFIX`,
`write`, `pin`, `encode`, `need` and `ordinary_path` with the interfaces required
by `diagnostic_episode.episode`. The runtime checks the evaluator's own source
bindings against its selected public consumer/bundle bytes. It imports no private
worker, controller, ledger, packet or target key.

The profile and bounded-stderr adapter are unchanged copies of the reviewed
producers. Metadata permission includes only the existing runtime scopes,
literal client and the literal `/Library` ancestor. Data permissions and
network/fork/sysctl restrictions are unchanged. The canary source is unchanged;
its configuration is generated from the caller's fresh output root and contains
only four generated non-neural witness paths. No private answer, person or global
manifest path is passed to the candidate.

The complete fixed canary bundle is captured before the first packet read. Each
fresh child receives only the same four demonstrations and one query. The direct
projection retains its no-tools policy; the program prompt retains its tool
permission. Their hashes differ, and matching requires equality after exactly
the one declared permission-sentence replacement. There is no cross-query
training or feedback. The fixed 0.5 response is a probe value, never a baseline.

Every selected position remains in the result inventory. The second episode is
not attempted after the first fails. The owned helper closes and reaps each
candidate group and records stdout EOF. Concurrent stderr capture retains at
most 16 KiB and reads at most 64 KiB per episode. Overflow refuses delivery
success. A known bounded truncation can still have closed resources; capture
completeness and resource custody are reported separately. Missing, unjoined or
unclosed custody must not be interpreted as safe completion or retried silently.

Success is limited to these two fixed canaries, their fresh module state, denied
writes and protected metadata/data/network probes. It does not qualify arbitrary
candidates, all clocks/shared OS side channels, escaped descendants or a model
provider's no-tools policy. The runtime sends no messages and calls no provider.

## Operator use

Copy `CONFIG.template.json` outside the participant's allowed runtime-data
roots. Fill every local path and byte/hash descriptor, retain the exact limits
and positions, and set `selected` to true only after external resource admission.
The repository root must contain this sibling and every pinned dependency. Keep
the packet, output and operator configuration outside `/System`, `/usr` and
`/Library/Frameworks`; the child runtime itself must be inside the existing allowed
roots. Executable capture is bounded at 1 MiB per selected file. There is no host
fallback or automatic permission widening.

Invoke the standalone stdlib Python 3.11 operator process with the selected
configuration digest:

```text
python3 -I -B /absolute/repository/benchmarks/neural/NEURAL-077/implementations/full32-paired-runtime-v1/runtime.py \
  --config /absolute/operator-config.json --config-sha256 SHA256_OF_CONFIG
```

The `run(config)` API requires the main thread and refuses any active real-time
interval timer before I/O. It cannot replace an in-process caller's watchdog.
Its own 300-second deadline remains active through input authentication, work,
cleanup and receipt finalization; prior handlers are restored afterward. External
admission, memory control and outer-process supervision remain the caller's
responsibility. Uninterruptible host I/O and a missing final receipt are not
qualified as successful closure.

Limits are fixed at 210 seconds work, 30 seconds plus 5 seconds cleanup per
episode, 32 MiB conservatively charged reads and 16 MiB cumulative artifacts.
The read counter includes an 8 MiB PacketSession precharge and 69,637 bytes per
dispatch for stderr/stdout pipes; it is not measured physical I/O. The CLI reads
at most 64 KiB of selected configuration separately. RAM is not OS-limited by
this module; provision at least the separately admitted envelope. The prior
qualification used a 512 MiB declared envelope.

The fresh output contains the frozen client, generated witnesses, matched
operator projections, episode INPUT/OUTPUT/STDERR/ATTEMPT/END files and
`RESULT.json`. These may contain query information and diagnostic text; keep them
operator-private. No output is a full condition submission or evidence of a
model's scientific performance.

## Source controls

`python3 -I -B test_runtime_portable.py` selects six affected portable-binding,
projection, callback-only orchestration, profile/framing integration and mocked
timer controls. These require only the stdlib. They launch no sandbox, canary,
packet reader or subprocess, and write no generated fixture files. For a staged
proposal, `ERP_RUNTIME_TEST_SOURCE` may identify the proposed `runtime.py` and
`ERP_RUNTIME_TEST_REPOSITORY` the repository containing its existing dependencies.
The default is the adjacent published source and repository root. Generated
returns are test fixtures, not native execution evidence.
