# Provenance and historical records

This directory preserves source identities, earlier status reports, publication
scopes and recorded evidence. It is separate from the [current status](../status/README.md)
and the [current task/source registry](../../benchmarks/registry.json).

## Relocated source and old paths

The [November 16 relocation ledger](relocations/2026-11-16.json) maps every original
public path to its new location, with the original Git blob, mode and byte length.
It records a pure physical move from commit
[`8a07b93da68e8b9cf193cdba7d09faa17bf56a43`](https://github.com/Donglomur/brain-researcher-benchmark/tree/8a07b93da68e8b9cf193cdba7d09faa17bf56a43).
Later functional repairs and current source manifests are separate changes.

Historical JSON manifests, declared hashes, status snapshots and retained source
records keep their original bodies. Their paths describe the recorded source tree;
they are not rewritten to claim that a later layout had always existed. Some
historical Markdown links likewise belong to the old tree. Use the immutable
origin links below or the ledger when interpreting them. If a record names an
earlier `source_commit`, that record's own commit and scope remain authoritative.

A historical hash authenticates the recorded bytes. It does not authenticate a
modified current file merely because the task ID or filename is the same. Current
operators use separately reviewed current bindings and inventories. Referenced
private data and receipts are not supplied by moving their metadata.

## Find a record

| Collection | Scope |
| --- | --- |
| [Source publication manifests](source-manifests/README.md) | Exact historical source selections, pins and declared publication limits |
| [Registration history](registrations/) | Original expansion registries and shared interpretation records |
| [Dated status snapshots](status-snapshots/) | Earlier construction counts and their definitions |
| [Publication scope records](publication/) | Earlier source snapshot and component-notice boundaries |
| [Repository and recovery assessments](assessments/) | Dated source-quality and legacy-reuse assessments |
| [Execution projections](execution/historical-evidence-v1/) | Earlier finite execution evidence and explicit limits |
| [Public Git recovery index](git/BRANCH_ARCHIVE_20261116.md) | Preserved branch tips and recovery commands |
| [Source release index](releases/SOURCE_COMPONENTS_20261116.md) | Earlier source releases and their stated scope |
| [Declared overlap graph](overlap/exposure_audit.json) | A metadata-derived historical relationship graph, not a leakage experiment |

Task-specific current rights notices remain with their task documentation and must
still be observed. Moving a notice into a task folder does not expand data or code
redistribution permissions.

## Read historical prose in its original context

- [Construction snapshot](https://github.com/Donglomur/brain-researcher-benchmark/blob/8a07b93da68e8b9cf193cdba7d09faa17bf56a43/docs/neuroscience-benchmarks/CONSTRUCTION_STATUS.md).
- [Repository quality assessment](https://github.com/Donglomur/brain-researcher-benchmark/blob/8a07b93da68e8b9cf193cdba7d09faa17bf56a43/docs/neuroscience-benchmarks/REPO_QUALITY_20261116.md).
- [Legacy task recovery](https://github.com/Donglomur/brain-researcher-benchmark/blob/8a07b93da68e8b9cf193cdba7d09faa17bf56a43/docs/neuroscience-benchmarks/LEGACY_TASK_RECOVERY_20261116.md).
- [Historical execution guide](https://github.com/Donglomur/brain-researcher-benchmark/blob/8a07b93da68e8b9cf193cdba7d09faa17bf56a43/docs/neuroscience-benchmarks/historical-evidence-v1/README.md).
- [Earlier source snapshot](https://github.com/Donglomur/brain-researcher-benchmark/blob/8a07b93da68e8b9cf193cdba7d09faa17bf56a43/docs/neuroscience-benchmarks/SOURCE_SNAPSHOT.md).

The [original three examples](../../examples/original-three/README.md) retain their
own results and upstream history. Those outcomes are not results for the newer
neuroscience task inventory.
