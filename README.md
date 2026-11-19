# Neuroscience Research Benchmarks

Can AI agents reproduce and improve published neuroscience results, interpret
neural observations directly, and build effective tools or models for those observations?

Use this repository to inspect scientific task definitions, find available
preparation and grading routes, and design controlled comparisons.

**[Paper research](benchmarks/paper/README.md) · [Neural-data understanding](benchmarks/neural/README.md) · [Implementation guide](docs/usage/implementations.md) · [Evidence and status](docs/status/README.md)**

## What is available today

There are **235 registrations: 117 paper and 118 neural tasks**, not 235 finished
benchmarks. The last whole-suite paper audit recorded **zero improvement-ready
tasks**; see the [retained audit dispositions](benchmarks/catalog/paper.md).
Current task pages describe supported and unsupported conditions, available
source and remaining requirements.

The [recorded difficulty pilot](docs/science/difficulty-pilot-20261117.md) contains
**eight scored AI-agent attempts on four authentic-data endpoints**: four historical
paper-calibration attempts and four neural prediction-programme attempts. There
are **no direct/viewer AI predictions** in that evidence. The neural attempts use
previously exposed development people and prepared features. Direct/viewer AI
interpretation, provider delivery and complete scientific qualification remain
unestablished. Preparation, author calibration and software controls retain their
separate scopes in [evidence and status](docs/status/README.md).

## Four outcomes across two tracks

| Track | Outcome | What is assessed |
| --- | --- | --- |
| Paper research | **Reproduction** | Faithful recovery of the complete declared original result, including required companion findings, under its source, data and evaluation conditions. Report original metrics and discrepancies. |
| Paper research | **Improvement** | Better performance on the same original task, preserving observations, cohort, split, evaluation and required controls. Candidates may change methods within the declared access and resource budget. |
| Neural-data understanding | **Native interpretation** | Infer the target without arbitrary analysis tools, directly from permitted observations or through a separately declared restricted viewer. Representations, demonstrations and allowed actions are explicit. |
| Neural-data understanding | **Tool/model building** | Create or adapt tools, models, investigation procedures or frozen programmes for the target, with attributable participant contributions. |

Paper **+ data** and paper **+ data + author code** are separate access conditions;
reproduction and improvement are assessed independently in each. Task-specific
assistance, including released models, must be declared. Neural comparisons must
match information, cases and budgets before attributing a difference to tool
access. A programme score does not establish direct or viewer interpretation.
See the [four-outcome design](docs/design/four-outcomes.md) for the full rules.

## Inspect a task without data or installation

With Python 3.11 or later:

```sh
git clone --branch publish/neuroscience-200 --single-branch https://github.com/Donglomur/brain-researcher-benchmark.git
cd brain-researcher-benchmark
python3 -I -S -B scripts/neurobench.py status
python3 -I -S -B scripts/neurobench.py show NEURAL-077
python3 -I -S -B scripts/neurobench.py implementations NEURAL-077
python3 -I -S -B scripts/neurobench.py evidence NEURAL-077
python3 -I -S -B scripts/neurobench.py neural-contract NEURAL-077
python3 -I -S -B scripts/neurobench.py paper-contract PAPER-FIND-050 --outcome reproduction
python3 -I -S -B scripts/neurobench.py paper-outcomes PAPER-FIND-050
python3 -I -S -B scripts/neurobench.py operator routes
```

These standard-library commands inspect public metadata and reports; they do not
open datasets, call models or run experiments. Use `list --track paper` or
`list --track neural` to browse tasks. `paper-contract` defaults to improvement;
the examples also expose unavailable outcomes. `evidence` keeps historical results
separate from current runtime qualification.

## Prepare inputs or grade a submission

The [implementation guide](docs/usage/implementations.md) lists available routes,
required inputs and unresolved limits. Start with:

| Route | Available scope and requirements |
| --- | --- |
| [EEG and sleep operator guide](docs/operator-routes.md) | Inspect provisioned inputs, prepare packets, and validate or grade completed submissions for NEURAL-077's 400 EEG trials and NEURAL-007's 5,450 sleep epochs. Each uses two already exposed development people. Exact external assets and native dependencies are required; `operator routes` verifies source only. |
| [ABR observations release](https://github.com/Donglomur/brain-researcher-benchmark/releases/tag/abr-observations-v1-20261118) · [tagged operator guide](https://github.com/Donglomur/brain-researcher-benchmark/blob/abr-observations-v1-20261118/benchmarks/neural/NEURAL-SCOPE-20261114-ABR-TRANSFER/implementations/native-delivery-v1/OPERATOR_GUIDE.md) | 936 complete case packets from 104 mice, preserving 16,226 traces on native sample-index/raw-amplitude axes. Supports viewing and manual submissions through sealing; scoring requires protected inputs. Physical calibration and AI performance remain unestablished. |
| [Original paper endpoints](docs/usage/implementations.md#prepare-original-paper-endpoints) | Preparation and assessment interfaces for REVE, DeepCaImX and SMC-RNN, with task-specific prerequisites. Preparation and author-reference calibration do not establish participant reproduction or improvement. |

Read the selected task contract before running an implementation. A component may
cover only one endpoint within a larger task; a changed split, easier subset or
different metric does not demonstrate improvement on the original task.

## Find source and evidence

Task definitions and implementations live in `benchmarks/paper/<task-id>/` and
`benchmarks/neural/<task-id>/`; shared source is in `benchmarks/shared/`.
The [registry](benchmarks/registry.json) records ownership and source relationships.
Common commands live in `src/neurobench/`, with entry points in `scripts/`.

| Next step | Guide |
| --- | --- |
| Browse tasks and source coverage | [Live catalog](benchmarks/catalog/README.md) |
| Design a controlled comparison | [Scientific design](docs/science/README.md), [study templates](docs/science/study-design/README.md) |
| Understand grading and execution requirements | [Artifact grading](docs/usage/artifact-grading.md), [implementations](docs/usage/implementations.md) |
| Read component results, failures and earlier releases | [Evidence and status](docs/status/README.md), task implementation pages, [provenance](docs/provenance/README.md) |
| Verify source or contribute | [Source integrity](docs/development/source-integrity.md), [contributing](CONTRIBUTING.md), [development guide](docs/DEVELOPMENT.md) |

## This fork and upstream

This is [Donglomur/brain-researcher-benchmark](https://github.com/Donglomur/brain-researcher-benchmark).
Its default and integration branch is `publish/neuroscience-200`; contributions use
feature branches and reviewed PRs into that branch.

The original [brain-researcher/brain-researcher-benchmark](https://github.com/brain-researcher/brain-researcher-benchmark)
examples—GRADIENT-001, SOCIALBRAIN-001 and DEVCONN-001—remain in
[examples/original-three](examples/original-three/README.md), with their own results
and upstream history, separately from the newer task inventory.
