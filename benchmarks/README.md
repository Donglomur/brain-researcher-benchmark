# Two benchmark tracks

Start with the track you want. Each contains one folder per registered task,
with a task guide, source references and links to its existing implementation
when one is registered.

| Track folder | Original specifications | Expansion drafts | Total registered |
| --- | --- | --- | --- |
| [Paper reproduction and improvement](paper/README.md) | 100 | 16 | 116 |
| [Neural-data understanding](neural/README.md) | 100 | 18 | 118 |

The track indexes separate the original 100 from later expansion drafts. A task
folder is a navigation home, not a newly packaged runnable benchmark. Registration,
source implementation and scientific qualification remain separate stages.
Conditions, folds, scorers and components do not create additional benchmarks.

```text
benchmarks/
  paper/
    README.md
    PAPER-FIND-050/
      README.md
    ...
  neural/
    README.md
    NEURAL-029/
      README.md
    ...
  catalog/                   # shared generated inventory
  manifests/paper/           # original paper specifications
  manifests/neural/          # original neural specifications
  neuroscience/              # existing implementations and expansion registries
  scientific_components/     # reusable scientific source
  scientific_contracts/      # shared scientific contracts
```

## Browse and inspect

- [Paper task folders](paper/README.md) and [neural task folders](neural/README.md).
- [Portable source packages](../docs/neuroscience-benchmarks/PORTABLE_COMPONENTS.md).
- [Supporting components](catalog/components.md).
- [Machine-readable catalog](catalog/catalog.json) and [catalog guide](catalog/README.md).

From the repository root:

```sh
python3 tools/neurobench.py list --track paper
python3 tools/neurobench.py list --track neural
python3 tools/neurobench.py show NEURAL-017
python3 tools/neurobench.py status
python3 tools/neurobench.py check
```

These commands inspect public metadata. They do not require private receipts or
scientific input files, and do not certify execution. Follow the linked
implementation's guide for its commands and prerequisites.

## Definitions and source

The original 200 specifications remain in `manifests/paper/` and
`manifests/neural/`. Expansion registries and task implementations retain their
existing locations under `neuroscience/`. Scientific manifests and saved source
verification refer to those paths. Shared software also lives in
`scientific_components/` and the repository's `components/` directory.

The track guides and `catalog/` are generated from those authoritative definitions.
Edit the definitions, then run `python3 tools/build_public_catalog.py` and
`python3 tools/build_public_catalog.py --check`. Do not edit generated task guides
by hand. Registration aliases are preserved and do not represent independent
papers or datasets.

For commands and evidence see [artifact grading](../docs/neuroscience-benchmarks/ARTIFACT_GRADING.md),
[source checks](../docs/neuroscience-benchmarks/SOURCE_INTEGRITY.md), the
[construction record](../docs/neuroscience-benchmarks/CONSTRUCTION_STATUS.md),
and the [main README](../README.md).
