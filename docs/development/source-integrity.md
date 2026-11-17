# Repository ownership and source integrity

The repository uses two complementary checks. Neither runs an agent or establishes
scientific qualification.

## Repository ownership and layout

```sh
python3 -I -S -B scripts/check_repository.py
```

This checker validates the declared ownership and current layout of all 651
implementation artifact records against
[benchmarks/integrity/source-ownership.json](../../benchmarks/integrity/source-ownership.json)
and the task registry. It checks the published source organization; it does not
make external dependencies available or turn historical source into a deployable
runtime.

## Enrolled source bundles

```sh
python3 -I -S -B scripts/check_source_integrity.py
```

This checker validates only the packages explicitly enrolled in
[benchmarks/integrity/current.json](../../benchmarks/integrity/current.json).
The current enrollment comprises four registered-runtime source packages, with
222 source files in the November 16 inventory:

| Task | Enrolled implementation |
| --- | --- |
| NEURAL-002 | [Registered runtime](../../benchmarks/neural/NEURAL-002/implementations/registered-runtime/) |
| NEURAL-030 | [Registered runtime](../../benchmarks/neural/NEURAL-030/implementations/registered-runtime/) |
| PAPER-paper-method-replacement-013 | [Registered runtime](../../benchmarks/paper/PAPER-paper-method-replacement-013/implementations/registered-runtime/) |
| PAPER-ROOT-ADD-018 | [Registered runtime](../../benchmarks/paper/PAPER-ROOT-ADD-018/implementations/registered-runtime/) |

This is not coverage of all implementation/source relationships in the task registry.
Other [source CI jobs](../../.github/workflows/neuroscience-source-integrity.yml)
run separate package-specific controls, including generated-input checks. Each
job's commands define its tested scope. The additive
[construction workflow](../../.github/workflows/construction-benchmark-components.yml)
checks eight reviewed components and 95 unique source pins, then runs their 266
generated test cases. These source and engineering checks preserve the stated
authentic-data and scientific qualification limits. Four expansion workflows
([A](../../.github/workflows/construction-expansion-a.yml),
[B](../../.github/workflows/construction-expansion-b.yml),
[C](../../.github/workflows/construction-expansion-c.yml),
[D](../../.github/workflows/construction-expansion-d.yml)) add 69 jobs covering
66 further scoped packages and 1,161 generated test cases. Their commands and
source pins define coverage; these checks do not run authentic-data campaigns. The
[NEURAL-047 clock workflow](../../.github/workflows/neural047-clock-arithmetic.yml)
adds 22 generated arithmetic and source-authentication controls while preserving
the task's external native-clock and deployment requirements.

The [parallel source workflow](../../.github/workflows/parallel-source-controls.yml)
uses a [reviewed command manifest](../../benchmarks/integrity/parallel-source-controls.v1.json)
to run generated software controls in explicit, pinned Python and dependency
environments. Required public source fixtures have exact byte and hash identities;
their acquisition has fixed byte and time limits and writes outside the checkout.
The launcher requires each declared test count, rejects skipped controls, and
checks the complete expected result for structured JSON controls. These checks
establish software behavior within their declared scope and do not promote
authentic-data, native-execution or scientific readiness. Use Python 3.11 for the
historical four-programme exact-AST controls, whose recorded structure depends on
that interpreter version.

Run both commands from the repository root using Python 3.11 or later.

The checker verifies the current enrolled source inventory and declared
bindings. It checks bounded ordinary files, exact bytes and hashes, closed member
sets, canonical task identities and the selected specialized source profiles.
The Neuroformer profile retains its API/function, mode and scope checks. Python
source is inspected without executing the benchmark's scientific pipeline.

Current task definitions and package-local canonical snapshots are separate
identities where the package declares both. Historical inventories, API records
and source freezes retain their original bytes and paths as predecessor evidence;
they are not silently rewritten to certify the new layout. Current inventories
bind the relocated files and separately identify their predecessors.

A passing check establishes source consistency within that explicit scope. It does
not establish complete dependencies, authentic-data equivalence, native execution,
a successful agent run or scientific/submission readiness. It is also not a
filesystem sandbox or protection against coordinated edits to source and pins.
Update current inventories with reviewed source changes, preserve original evidence,
and run the affected checks. See [development](../DEVELOPMENT.md) and
[provenance](../provenance/README.md).

## Workflow pin preflight and bounded maintenance

Before pushing source or task-definition changes, run:

```sh
python3 -I -S -B scripts/maintenance/workflow_source_pins.py --output /tmp/workflow-source-audit.json
python3 -I -S -B scripts/check_source_integrity.py
python3 -I -S -B scripts/check_repository.py
python3 -I -S -B -m unittest discover -s tests/maintenance -p 'test_workflow_source_pins.py' -v
```

The first command is the same source-only preflight used by the shared
[CI gate](../../.github/workflows/source-maintenance-preflight.yml). Every existing
workflow job depends on that gate, directly or through its existing source job;
package jobs retain their parallelism after it passes. The gate also runs the
focused rejection controls and the repository ownership verifier. The latter
authenticates every registered artifact's complete current file namespace,
ownership, modes, sizes and hashes against the reviewed source ownership
inventory, including newly admitted packages without legacy predecessors. Its
existing per-file, total-read and link constraints apply unchanged. The gate
installs no benchmark dependencies and executes no benchmark pipeline.
The controls also inspect imports inside the DeepCaImX source-panel and SMC test
methods, including SMC's unchanged vendored original evaluator, and require each
enrolled CI job to declare those dependencies as pinned wheels. This catches a
missing dependency even when the local interpreter already has it. SMC's 44
generated controls run in the existing MEG environment with authenticated h5py;
the newer CI dependencies establish generated compatibility, not source-native
calibration. The OpenMIIR support controls use only the standard library. The
existing numerical job requires all 34 NEURAL096 controls on Linux, including
the wider-floating-point rejection that is unavailable on some macOS builds.

The [reviewed occurrence ledger](../../scripts/maintenance/workflow_source_pins.json)
binds every literal SHA256 occurrence to a repository source path or an explicit
pip wheel hash. Expectations are read from the actual workflow text, including
shell arguments, Python scalar/tuple pins, dictionary rows, and semantic hash
assertions. Exact workflow snapshots and occurrence positions make changed,
missing, or new forms fail closed. The initial audit covers 978 occurrences:
839 local source occurrences over 702 files and 139 wheel occurrences. It also
checks 42 literal package groups, their complete member sets and aggregate byte
totals, preserved task predecessors, and the numerical launcher's parent/child
CPU limits. The JSON report lists every local occurrence with its path, line,
size, and hash. Wheel hashes are classified, not downloaded or authenticated.

These checks retain all existing package-specific source validators and
scientific tests. The ledger is reviewed repository metadata, not an external
trust root: coordinated changes to source, workflows, and the ledger require
code review. Its baseline commit identifies the reviewed migration; subsequent
bounded updates retain explicit old/new identities and their review reasons.
No source path is inferred by searching for matching file content at runtime.

For a reviewed source change, provide an explicit JSON request:

```json
{
  "schema": "workflow-pin-changes/v1",
  "reason": "Describe the reviewed source correction and its evidence",
  "updates": [
    {
      "previous": {"path": "path/to/source.py", "bytes": 100, "sha256": "<old SHA256>"},
      "current": {"path": "path/to/source.py", "bytes": 110, "sha256": "<reviewed new SHA256>"}
    }
  ]
}
```

```sh
python3 -I -S -B scripts/maintenance/workflow_source_pins.py --plan changes.json --output reviewed-plan.json
# Review the request, plan, source diff, and resulting workflow diff.
python3 -I -S -B scripts/maintenance/workflow_source_pins.py --apply reviewed-plan.json
```

Planning is read-only; applying checks the complete plan again before writing.
It changes only bound pin tokens and the corresponding literal-array byte
aggregates, preserves all other workflow code, and updates the occurrence ledger.
A stale plan fails. There is no recompute-all-pins option. Scalar pins support
same-size hash corrections. The reviewed digest-only `--expected-sha256` CLI
form also permits a changed descriptor size because it has no inline size token.
Other size-changing or redirected computed/scalar paths
fail for explicit manual review rather than guessing which integer or expression
to rewrite. New workflow syntax or unrelated workflow edits require review of
both the changed workflow and its exact ledger snapshot and occurrence bindings.

Canonical task changes use a historical redirect, preserving the original size
and hash. Only the same task's registered `previous_specification` at the exact
`historical/task.pre-improvement.v1.json` or
`historical/task.pre-understanding.v1.json` path is accepted. A current task may
not be rehashed in place to satisfy a legacy source validator. Unrelated current
task readers are not redirected by the pin updater.

The task integrity refresher supports both revision types. Use
`python3 -I -S -B scripts/maintenance/refresh_paper_integrity.py --metadata-only`
for its read-only current-inventory and closure plan, or add `--write` to apply
those authenticated metadata changes. Feed its explicit old/new closure pins and
the registered task predecessor redirects into the workflow plan above. Run both
preflight commands and the affected package validators after integration. A
passing source audit still does not establish authentic-data execution or
scientific qualification.
