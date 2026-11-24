# Paired Purkinje final-program execution

Experimental source component for `PAPER-FIND-REP-013`. It connects two committed programs and the current [A16/B18 packets](../paired-access/README.md) to the existing protected producer, then to the unchanged paired numerical grader. It adds no benchmark ID, numerical method or scientific result.

The full declared endpoint remains ten trees, 13 components, 21,116 branches, 12,603 author sections, five numerical products, 31 table fields and 58 summary errors. The primary metric remains equal-cell branch-length RMSE in micrometres.

## What this component connects

Both exact program bodies are committed before either packet payload or candidate execution. Each current packet is copied through its pinned manifest into a separate read-only input tree. A has 16 files; B has 18, adding only the official Rmd and marked source excerpt. The 622,639-byte article is admitted through its exact current descriptor; the legacy 15-file/600,000-byte route is unchanged.

The unchanged [program producer](../registered-runtime/program-v1/) renders the exact committed code with its trusted bridge. The bridge runs `program.py --input /input --out /work/output`, collects its five numerical outputs and returns a bounded wire envelope. The protected owner validates effective mounts, natural completion and exact owned closure.

This API accepts outputs only from that owner's in-process closed-run token. It has no caller-supplied numerical-output directory. Failure in B preserves A's evidence but issues no pair token. There is no private-reference argument in the execution call.

Only after both programs close can `grade_closed_pair` call the existing paired grader. That grader still requires independent authoring/runtime/closure authority, validates both sealed outputs and authenticates the common fixed reference before scoring. Process-local tokens are a trusted-operator boundary, not a sandbox against malicious host Python.

## Portable use inside a selected owner

Python 3.11 source roots are explicit arguments. The production bootstrap reads source and small descriptors only; it does not open original data or private numerical references. The repository contains all 22 source/metadata dependencies needed by the constructor; none are duplicated here. [SOURCE.json](SOURCE.json) records inherited release provenance. Current source loading uses the maintained pins in `paired_execution.py` and the paired component.

```python
from importlib.util import spec_from_file_location, module_from_spec
from pathlib import Path

repo = Path("/path/to/checkout")
component = repo / "benchmarks/paper/PAPER-FIND-REP-013/implementations/paired-execution"
spec = spec_from_file_location("paired_execution", component / "paired_execution.py")
module = module_from_spec(spec)
spec.loader.exec_module(module)

# Source-only construction: supply an independently reviewed current adapter pin.
executor = module.PairExecutor(
    repo=repo,
    paired_root=repo / "benchmarks/paper/PAPER-FIND-REP-013/implementations/paired-access",
    producer_root=repo / "benchmarks/paper/PAPER-FIND-REP-013/implementations/registered-runtime/program-v1",
    expected_source=accepted_adapter_pin,
)
```

Within an independently selected external owner, the execution and grading calls are:

```python
closed = executor.execute_pair(
    requests=selected_A_B_requests,
    request_pins=canonical_request_pins,
    programs=exact_program_locators,
    packet_roots=materialized_public_contract_packet_directories,
    packet_receipts=exact_public_contract_receipt_locators,
    runtime=original_runtime_selection,
    owner_authorization=independent_selected_owner_authorization,
    owner_authorization_pin=canonical_owner_authorization_pin,
    root=fresh_private_pair_directory,
    budget=original_owner_budget,
    active_deadline=original_active_deadline,
)
result = executor.grade_closed_pair(
    closed,
    authority=independent_paired_authoring_runtime_authority,
    authority_pin=canonical_paired_authority_pin,
    reference_reader=existing_fixed_private_reference_reader,
    budget=original_owner_budget,
)
```

These are inert examples with unresolved operator variables. `accepted_adapter_pin` must identify the independently reviewed current `paired_execution.py` bytes; [SOURCE.json](SOURCE.json) preserves historical release identities and is not a current source-selection receipt. Every arm mapping requires exactly A and B. Locators have exactly `path`, integer `bytes` and lowercase `sha256`; paths are absolute ordinary files. Run-request and paired-authority pins use the paired module's indented canonical encoding; owner authorization uses the producer common module's compact encoding.

The [authorization template](OWNER_AUTHORIZATION.template.json) is disabled. It must not be enabled merely because these tests pass. The external owner must select current capacity/storage, prior-cost and once-only history, both complete 60-second candidate opportunities, capture/closure/cleanup reserves and hard aggregate host/descendant limits. The original runtime image is:

```text
sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156
```

No image pull or 9aaf substitution is implemented. Exact live image contents, current mount behavior and the complete owner/runtime composition remain unqualified. The component has no standalone Docker-launch CLI or model/provider integration. Its cooperative budget counts its own common-helper reads/writes; it does not measure all paired-library or OS I/O or enforce aggregate memory/CPU.

Public packet source/contract pins differ from workstation-private source pins. Consequently their request and receipt identities also differ. This API requires the public contract's receipts and rejects private-contract ones; do not relabel a historical authentic receipt or assume that a path relocation creates new runtime evidence. A future operator must explicitly review the public binding while preserving any accepted physical input evidence.

A program captured by a chosen-agent owner may be supplied as an exact committed locator. That upstream owner must bind the capture to the pair, condition and independent context and prove authoring closure. This component authenticates the selected bytes and their executed outputs; it does not establish which model authored them.

## Source checks and limits

From the repository root:

```sh
python -I -S -B benchmarks/paper/PAPER-FIND-REP-013/implementations/paired-execution/test_paired_execution.py --relocation-only
```

Three focused relocation methods passed with two explicitly invented host Python programs through the unchanged bridge and collector. Docker/daemon transport was simulated. These checks cover relocated source/dependency pins, global import isolation, the current A/B packet shapes, exact program-to-output capture and both-closed-before-reference ordering.

Twelve earlier generated integration methods are retained in this test file and were accepted for the original source component. The relocation run reuses that evidence and runs only the affected interface checks. Running the file without the flag selects all 13 generated methods; CI uses the focused selection. The fixture has ten cells/13 components/15 invented branches, not authentic 21,116-branch qualification. No original article/Rmd/SWC, private answer data, model or live Docker action is included or executed by these checks.

Scientific acceptance remains separate. Shared Sholl totals and a source-informed common specification are exposed; article HTML does not close the complete visual paper or supplements. Same-input execution cannot exclude hardcoded numbers. A computation-method review, independent authoring histories, equal enforced budgets and no cross-arm feedback are required before claiming an official-code benefit. No pass threshold, scientific reproduction, improvement, readiness or broad qualification is inferred from source tests.

[Notices](NOTICES.md) describe the original-asset and licensing boundary.
