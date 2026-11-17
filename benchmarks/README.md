# Neuroscience benchmark tasks

| Track | Original specifications | Expansion drafts | Registered total |
| --- | ---: | ---: | ---: |
| [Paper improvement](paper/README.md) | 100 | 16 | 116 |
| [Neural-data understanding](neural/README.md) | 100 | 18 | 118 |

Task folders contain the authoritative `task.json` and their available
implementation packages. Each task page links its sources, implementation roles,
shared scientific code and documented limits. Some tasks remain specifications or
construction drafts; a folder is not evidence of a complete runnable benchmark.

```text
benchmarks/
  paper/<task-ID>/
    task.json
    implementations/
    docs/                  # when task-specific guidance is available
  neural/<task-ID>/
    task.json
    implementations/
    docs/
  shared/<family>/         # multi-task, related-only and unassigned source
  registry.json            # authoritative task/source relationships
  catalog/                 # generated browsing views
  integrity/               # current explicitly enrolled source checks
```

An `implementations/` or `docs/` directory exists only where source or guidance is
present. Shared packages, conditions, folds and alternative implementations do not
add independent benchmarks. Explicit registration aliases remain visible.

## Browse and use

- [Paper tasks](paper/README.md), [neural tasks](neural/README.md).
- [Implementation guide](../docs/usage/implementations.md).
- [Machine-readable registry](registry.json) and [catalog](catalog/README.md).
- [Current status](../docs/status/README.md) and [scientific design](../docs/science/README.md).

```sh
python3 -I -S -B scripts/neurobench.py list --track paper
python3 -I -S -B scripts/neurobench.py list --track neural
python3 -I -S -B scripts/neurobench.py show PAPER-FIND-050
```

Run commands from the repository root. These commands inspect metadata. Follow a
selected implementation's guide for its environment, inputs, access conditions
and admission requirements.

## Editing

Edit task definitions and registry relationships before regenerating the catalog
with `python3 -I -S -B scripts/catalog.py`. Keep implementation packages intact
when their source inventory is closed. Historical registration and source records
live in [provenance](../docs/provenance/README.md), bound to their original commits.

The [shared-source index](shared/README.md) identifies multi-task programmes,
related-only sources and families without an assigned task owner. Their roles and
limits remain explicit in the registry; shared location alone does not establish a
scientific task relationship.
