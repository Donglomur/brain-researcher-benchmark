# Repository ownership and source integrity

The repository uses two complementary checks. Neither runs an agent or establishes
scientific qualification.

## Repository ownership and layout

```sh
python3 -I -S -B scripts/check_repository.py
```

This checker validates the declared ownership and current layout of all 286
implementation/source records against
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
job's commands define its tested scope.

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
