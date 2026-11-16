# PFC Full99 conditional reconstruction benchmark

This benchmark reconstructs conditional statistics from a supplied prefrontal-cortex map and measures sensitivity to whole-animal deletion. It has completed a full seven-stage compatibility run on the selected local host, including both information conditions and an incorrect-answer control.

The [four fixed input assets](https://github.com/Donglomur/brain-researcher-benchmark/releases/tag/pfc-full99-inputs-v1) total **5.57 MB**. Start with [input provisioning](PROVISIONING.md), then the [operator guide](OPERATOR_GUIDE.md). The admitted runtime image still needs a distribution route and fresh admission on another host. Separate [clean runtime build sources](../pfc-clean-runtime-source-v1/README.md) describe the newer 9aaf dependency stack; they do not replace this task’s validated 385454 image or establish arbitrary-host compatibility.

## Task and information conditions

Both conditions receive the same participant packet, paper, task and schema. Condition B additionally receives the selected official method and its BSD-2-Clause license. The evaluator enforces these mounts. Public discoverability and possible prior model exposure are separate from the controlled information condition.

The packet retains all 99 recordings, 19,186 fitting units and 68 fitting animals. The scored PFC population is separately 10,243 units from 65 animals. Evaluation includes the full cohort and all 68 fitting-animal deletions, for 69 cases. The supplied map and saved UUID mapping are fixed inputs; this endpoint does not refit a SOM, test held-animal prediction or reproduce the entire source paper.

## Validation and boundaries

[VALIDATION.md](VALIDATION.md) records the accepted local compatibility run and the later complete input-content audit. All 16 portability controls and all 19 provisioning controls have passing local evidence. CI checks both suites on invented fixtures without downloading neural data or launching the authentic benchmark.

The same analytical program was used in both compatibility arms. That validates delivery and scoring; it measures neither LLM performance nor the effect of code assistance. The public inputs contain no protected numerical answer tables, private execution authority or owner diagnostics.

## Source and provenance

- [PUBLIC_INPUTS.json](PUBLIC_INPUTS.json): exact public input identities and information roles.
- [SOURCE_LOCK.json](SOURCE_LOCK.json): unchanged 20-file benchmark implementation.
- [provisioning/SOURCE_LOCK.json](provisioning/SOURCE_LOCK.json): eight provisioning source/documentation files.
- [RELEASE_MANIFEST.json](RELEASE_MANIFEST.json): complete source/documentation inventory.
- [Attribution](provisioning/ATTRIBUTION.md) and [DANDI version notices](provisioning/DANDI_VERSION_NOTICES.md): upstream references and notices.

Keep execution receipts and evaluation outputs in the selected owner-private output directory. The provenance helper creates the metadata descriptor needed by deployment without distributing the original private preparation manifest.
