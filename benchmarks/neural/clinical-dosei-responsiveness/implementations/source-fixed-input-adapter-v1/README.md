# Fixed DoSEI inputs for the paired runner

`FixedInputLoader` fills the remaining metadata I/O connection to the accepted
paired-runner source. It returns `blobs` (nine exact roles) and `member_blobs`
(all 171 recording receipts), the two positional data arguments of the existing
`assembler.build_runner`. It does not render observations, read arrays, start a
participant, build a new supervisor, or score predictions.

The caller supplies the authenticated bytes of the existing
`verify_saved_eeg_projections.py`, SHA256
`bc2891b56bf4640586949137f95d80050d255e70c1314ac08aa2eca28503b228`.
The adapter uses that source's unchanged `Meter` and `Reader`. Explicit
`Reader.finish()` is necessary for exact extent, EOF, hash and closed identity;
the reader context manager alone only closes. No `Context` or `GuardContext` is
constructed. The existing `read_bytes` helper is not used because this path
also needs the authenticated declared extent and closed-file signature.

The nine path/hash/cap roles are fixed in `ROLES`. Cohort, success and public
source-verification bodies bootstrap from a bounded current file extent plus
their fixed hash. Other exact extents come from those authenticated bodies.
Before opening any recording receipt, the complete 171-member map must agree
between the observation cohort, numeric cohort and case-index manifest. Every
member path must be the corresponding `recording-{id}.success.json` under the
one fixed numeric root. Recording IDs are source roles, not biological people.

One 32 MiB meter covers all 180 bodies and all EOF probes. A successful empty
probe releases its provisional byte; an interrupted read preserves its unknown
grant. Every read retains EOF headroom. Private roots and opened files have
explicit owner, mode, single-link and no-follow checks, and the checked pre-open
identity must match the descriptor before the first body read. Each body is read
once. A failure poisons the complete loader; there is no retry or partial result.
Closing an established reader is attempted once, while preserving an original
interruption. A constructor or close failure remains conservatively uncertain.

The output and `report()` are trusted-host objects. They include private key and
index material and must never become participant messages. The 32 MiB counter
does not include caller source bootstrap, filesystem metadata calls, runtime
qualification proof, or later array reads. This is a host adapter, not an
isolation boundary against code already running in the trusted host.

The future caller connection is:

```python
loader = input_adapter.FixedInputLoader(authenticated_reader_source_bytes)
inputs = loader.load()  # Requires separate admission for authentic application.
runner = assembler.build_runner(
    **inputs,
    admission_module=release_admission,
    factory_module=delivery_factory,
    modules=modules,
    data=data,
    **existing_declared_runtime_and_participant_options,
)
```

`modules` and `data` remain outputs of the existing authenticated
`dependencies.load_dependencies`. The unchanged assembler admits the full
release and binds `host_projection.project_case` to `release.array_root`, the
accepted secret and its separate `ReadBudget`. No participant-selected root or
new array reader is introduced. The qualification proof, declared execution
budget, participant factory and evidence sink remain distinct operational
inputs. Constructing a runner does not authorize `.run()`, `.seal()` or `.score()`.

`generated_loader` is explicitly fictional. The five focused test groups use
the actual authenticated Reader/Meter behind fake file operations and one
three-byte real generated file. This checks complete input wiring and refusal
paths; it does not establish authentic application or provider readiness. The
previous accepted generated 7,345-case paired-runner check and six container
engineering controls remain separate evidence. This source makes no new
scientific performance claim.
