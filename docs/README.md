# Documentation

## Use the repository

- [Browse the paper and neural tracks](../benchmarks/README.md).
- [Inspect recorded evidence and current status](status/README.md).
- [Inspect EEG/sleep inputs, prepare packets and grade submissions](operator-routes.md).
- [Prepare the original REVE and DeepCaImX endpoints](usage/implementations.md#prepare-original-paper-endpoints).
- [Use the restricted EEG image transport](../benchmarks/neural/NEURAL-077/implementations/visual-transport-v1/README.md).
- [Find implementation routes](usage/implementations.md) or [grade a finished artifact](usage/artifact-grading.md).
- [Use task-specific preparation, estimation and evaluation components](usage/construction-components.md).

Run `python3 -I -S -B scripts/neurobench.py evidence TASK_ID` from the repository
root to inspect selected public reports for a task, including the condition,
metrics and limits. This reads reported evidence without rerunning it or promoting
current runtime qualification.

Use `python3 -I -S -B scripts/neurobench.py neural-contract NEURAL-077` to inspect a
current neural target, permitted observations, comparators and separate access
conditions. All 118 neural definitions have versioned contracts; their source
delivery dispositions do not establish scientific qualification.

## Design a comparison

- [Scientific design overview](science/README.md).
- [Same-task paper improvement](science/paper-improvement/README.md).
- [Task scope and qualification](science/task-scope.md).
- [Paper scope assessment](science/paper-scope/SCIENTIFIC_SCOPE.md).
- [Paired study templates](science/study-design/README.md) and [reporting](science/paired-study-reporting.md).
- [Difficulty pilot: eight scored development attempts](science/difficulty-pilot-20261117.md).
- [Authentic EEG/sleep operator controls](status/operator-controls-20261116.json).
- [Fresh-checkout validation of the operator repair](status/operator-controls-rename-20261116.json).

Paper reconstruction is calibration evidence. Neural programme, investigation and
interpretation conditions need separate access rules and controls; success in one
does not establish success in the others.

## Develop and verify source

- [Contribution and PR workflow](DEVELOPMENT.md).
- [Source organization and checks](development/README.md).
- [Source-integrity coverage](development/source-integrity.md).
- [Curation contracts and worker instructions](curation/README.md).

## Evidence and history

[Provenance](provenance/README.md) explains earlier release manifests, status
snapshots, reported execution evidence and the physical relocation ledger.
Historical records retain their original scope and source identities; the current
registry describes today's task-to-source relationships.

The inherited examples have their own [guide](../examples/original-three/README.md),
[results](../examples/original-three/results/README.md) and
[history](../examples/original-three/upstream-history/README.md).
