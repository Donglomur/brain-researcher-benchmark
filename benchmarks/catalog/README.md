# Neuroscience task catalog

This is a public source inventory, not a list of qualified benchmarks. Scientific and submission readiness are **unknown here**. Runtime manifests and source components do not establish successful execution. Registered IDs may alias earlier contract identifiers; they do not count independent studies or datasets.

Browse **234 registered questions**: [116 paper tasks](paper.md) and [118 neural/behavioral tasks](neural.md). The roster combines 200 canonical specifications with 34 expansion drafts.

Browse the task folders in [paper research](../paper/README.md) and [neural-data understanding](../neural/README.md). Each track separates its original 100 from expansion drafts.

The checkout also contains 95 one-level runtime manifests and 73 historical [source component collections](components.md). The current registry assigns 370 implementation artifacts, including 5 with unresolved ownership. Participants, conditions, folds, seeds and controls are nested task units, not additional benchmarks.

The [machine-readable catalog](catalog.json) includes exact specification pins and links to existing public files. External citations are copied from public specifications; their availability was not rechecked.

The authoritative [registry](../registry.json) assigns implementations explicitly. Ownership does not establish equivalence to the full registered scientific contract.

Regenerate with `python3 scripts/catalog.py`; verify with `python3 scripts/catalog.py --check`, from the repository root.

Preserved historical registration snapshots (their old task locators are not current discovery inputs):

- [expansion-20261113](../../docs/provenance/registrations/expansion-20261113/registry.json)
- [expansion-20261114](../../docs/provenance/registrations/expansion-20261114/registry.json)
- [expansion-20261114-v11](../../docs/provenance/registrations/expansion-20261114-v11/registry.json)
- [expansion-20261114-v12](../../docs/provenance/registrations/expansion-20261114-v12/registry.json)

Shared scope and interpretation documents:

- [mandatory_shared_contract](../../docs/provenance/registrations/expansion-20261114-v11/tasks/COMMON_TASK_AND_COUNT_CONTRACT.json)
- [mandatory_interpretation](../../docs/provenance/registrations/expansion-20261114-v11/tasks/REGISTRATION_INTERPRETATION.json)
