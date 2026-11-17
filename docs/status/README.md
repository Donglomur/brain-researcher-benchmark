# Current status

As of **November 16, 2026**, the repository organizes task definitions and source
under the paper and neural tracks. These counts describe the checked-in registry,
not a leaderboard of completed scientific evaluations.

| Inventory | Count | Interpretation |
| --- | ---: | --- |
| Original specifications | 200 | 100 paper and 100 neural |
| Expansion drafts | 34 | 16 paper and 18 neural |
| Registered task entries | 234 | 116 paper and 118 neural; explicit specification aliases remain visible |
| Implementation/source relationships | 286 | Ownership records for retained task and shared source, not runnable-task counts |
| Qualified across complete scientific contracts | Unknown | No complete verified total has been established |

The [registry](../../benchmarks/registry.json) is authoritative for current physical
locations and task relationships. Its source-base counters also retain 95 historical
runtime declarations and 73 component-lineage entries. Those are different,
overlapping inventories and must not be added to the task count or treated as
current execution qualification.

## What the reorganization establishes

Each task's authoritative definition is at `benchmarks/<track>/<ID>/task.json`.
Existing implementation packages now live with their owning task or under
[shared source](../../benchmarks/shared/README.md), which also retains related-only
sources and families without an assigned task owner. Generic framework code,
commands, guides and provenance have
separate locations. The [relocation ledger](../provenance/relocations/2026-11-16.json)
records the pure move of the original public files; later source repairs and
current manifests are separate changes.

Task ownership does not choose a new scientifically preferred implementation.
Retained predecessors, alternative scopes and unresolved source relationships keep
their stated roles. No dataset, model run, paper reproduction, frontier improvement
or qualification follows from a directory move.

## Evidence and limits

The [repository checker](../development/source-integrity.md) covers the declared
ownership and layout of 286 artifacts; the separate source-integrity checker
verifies 222 files against recorded pins in four enrolled bundles. These are software/source
coverage counts. They are not completed scientific evaluations.

Representative known gaps include unavailable dependencies. These include the
qualified-imports programme's DMFC dependency and private scorer inputs for
NEURAL-008, NEURAL-023, NEURAL-046 and NEURAL-096; NEURAL-035 also lacks its historical
manifest. The affected registry records preserve these limits. Public source
organization does not establish deployability. Campaign commands refuse execution
without explicit campaign authority and required private inputs.

Source checks establish the consistency and behavior they explicitly test. Generated
fixtures do not establish neural understanding or authentic-data agreement. A
scientifically qualified task needs its full input population, access conditions,
metric and comparator, functioning protected evaluation, and independent evidence
for the complete declared contract.

The [implementation guide](../usage/implementations.md) identifies usable source
routes and their requirements. The [provenance index](../provenance/README.md)
retains dated construction reports and historical execution projections, with their
original limits. Earlier counts describe those snapshots; they do not override
this registry or establish new results.
