# Benchmark catalog and source packages

The programme has **234 registered task drafts: 116 paper and 118 neural**.
Registration, source implementation, historical local acceptance and current
scientific qualification are separate stages. Task conditions, folds, scorers
and components do not create additional independent benchmarks.

| Browse | Contents |
| --- | --- |
| [Paper tasks](catalog/paper.md) | Reproduction/improvement definitions and their source links. |
| [Neural tasks](catalog/neural.md) | Neural/behavioral interpretation and prediction definitions. |
| [Components](catalog/components.md) | Public source packages and their own instructions. |
| [Machine-readable catalog](catalog/catalog.json) | Deterministic metadata, specification identities and declared status. |
| [Catalog guide](catalog/README.md) | Coverage, aliases and regeneration. |

From the repository root:

```sh
python3 tools/neurobench.py list --track paper
python3 tools/neurobench.py show NEURAL-017
python3 tools/neurobench.py status
python3 tools/neurobench.py check
```

These public metadata operations do not require private receipts or scientific
input files. They do not certify task execution. The original private-ledger
`score` and `run` admission remains separate; follow each component's guide for
an executable route and its prerequisites.

## Source organization

- `manifests/paper/` and `manifests/neural/` contain the original 200 specifications.
- Expansion registries and their task definitions live under `neuroscience/`.
- `neuroscience/<package>/` contains task-specific source, manifests and guides.
- `scientific_components/` and the repository's `components/` contain reusable software.
- `catalog/` is generated navigation. Edit the underlying definitions before regenerating it.

The catalog enumerates registrations, including explicit specification aliases;
it is not a count of unique papers, data sources or completed evaluations.
Scoring software and runtime declarations alone do not establish current
scientific readiness.

For practical commands see [artifact grading](../docs/neuroscience-benchmarks/ARTIFACT_GRADING.md),
[source checks](../docs/neuroscience-benchmarks/SOURCE_INTEGRITY.md) and the
[dated construction record](../docs/neuroscience-benchmarks/CONSTRUCTION_STATUS.md).
The [main README](../README.md) explains the two research tracks and public scope.
