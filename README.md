# Neuroscience Research Benchmarks

Can AI agents surpass published neuroscience methods on their original tasks and
understand neural data?

Use this repository to inspect task definitions, prepare supported inputs, and
compare submissions under explicit scientific and information-access rules.
The [recorded difficulty pilot](docs/science/difficulty-pilot-20261117.md) contains
eight scored agent attempts on four authentic-data endpoints. These are scoped
development results: four historical paper-reconstruction attempts and four neural
prediction-programme attempts. Complete scientific qualification remains unestablished.

**[Paper research](benchmarks/paper/README.md) · [Neural-data understanding](benchmarks/neural/README.md) · [Implementation guide](docs/usage/implementations.md) · [Evidence and status](docs/status/README.md)**

## Start from a task and its evidence

```sh
git clone --branch publish/neuroscience-200 --single-branch https://github.com/Donglomur/brain-researcher-benchmark.git
cd brain-researcher-benchmark
python3 -I -S -B scripts/neurobench.py status
python3 -I -S -B scripts/neurobench.py show NEURAL-077
python3 -I -S -B scripts/neurobench.py implementations NEURAL-077
python3 -I -S -B scripts/neurobench.py evidence NEURAL-077
python3 -I -S -B scripts/neurobench.py paper-contract PAPER-FIND-050
python3 -I -S -B scripts/neurobench.py operator routes
```

These commands use Python 3.11 or later and the standard library; they require no
installation, dataset or model call. `evidence` reports each selected public
record's condition, endpoint, metrics, source hash and limitations. It keeps older
execution reports separate from current runtime qualification. Use `list --track
paper` or `list --track neural` to browse the registered tasks.

The [EEG and sleep operator guide](docs/operator-routes.md) provides a common path
to inspect provisioned inputs, prepare packets and grade completed submissions for
NEURAL-077 (400 EEG trials) and NEURAL-007 (5,450 sleep epochs). Each route uses its
own two exposed development people. `operator routes` verifies the delivered source;
it does not inspect local data or execute a grader. Follow the guide for the exact
external inputs, fresh output directories and native dependencies.

[Native operator controls](docs/status/operator-controls-20261116.json) exercised
both complete development panels, including incomplete-submission rejection and
target-pin failure. These are software checks using fixed outputs, with no new
solver attempt or model call.

The [implementation guide](docs/usage/implementations.md) connects other task
definitions to their available preparation and grading routes.

## What each track measures

| Track | Success and comparison |
| --- | --- |
| **Paper improvement** | Surpass the source paper on the same original endpoint or complete panel. Match the dataset, cohort, split, permitted observations, metric, aggregation and required controls; compare paper + data with paper + data + official code under matched budgets. Candidates may change architecture, inference or optimization within that observation and budget boundary. Reproduction supplies calibration evidence. |
| **Neural-data understanding** | Infer specified targets from permitted neural or behavioral observations. Direct observation, typed-viewer interpretation, tool-assisted investigation and frozen prediction programmes are separate conditions, each with its own delivered inputs, controls and competent comparators. |

A programme score does not establish direct or viewer interpretation. The existing
neural pilot uses exposed development people and prepared feature inputs. Separate
[waveform preparation](benchmarks/neural/NEURAL-077/implementations/complete-direct-condition-v1/EVIDENCE.json)
and [viewer rendering](benchmarks/neural/NEURAL-077/implementations/visual-viewer-v1/EVIDENCE.json)
reports establish authentic-input software behavior; they contain no model evaluation.

Every current paper definition binds a source-grounded
[improvement contract](docs/science/paper-improvement/README.md). The
[paper catalog](benchmarks/catalog/paper.md) distinguishes designs, unresolved source
comparisons, ineligible papers and improvement-ready tasks. The current contracts
establish no empirical paper improvement. A changed split, easier subset or different
metric is an extension; current SOTA requires its own verified comparison.

## Find source and understand the counts

The [live catalog](benchmarks/catalog/README.md) and `status` command derive task
counts from the [current registry](benchmarks/registry.json). The original roster
contains 100 specifications per track, with later expansion registrations reported
separately. Registrations, implementation artifacts, conditions, participants and
folds are different quantities. Source ownership alone does not establish a complete,
runnable scientific benchmark.

```text
benchmarks/
  paper/<task-id>/          # current paper definitions and implementations
  neural/<task-id>/         # current neural definitions and implementations
  shared/                  # shared and related scientific source
  registry.json            # explicit task, source and ownership relationships
  catalog/                 # generated browsing views
src/neurobench/             # common commands, validation and evidence reporting
scripts/                   # public commands and maintenance entry points
tests/                     # framework and source checks
docs/                      # usage, scientific design, status and provenance
examples/original-three/    # inherited scientific-judgment examples
archive/                   # explicitly inactive retained material
```

| Next step | Guide |
| --- | --- |
| Inspect EEG/sleep inputs or grade an existing submission | [Operator routes](docs/operator-routes.md), [artifact grading](docs/usage/artifact-grading.md) |
| Find other task implementations and their limits | [Implementations](docs/usage/implementations.md) |
| Design a controlled comparison | [Scientific design](docs/science/README.md), [study templates](docs/science/study-design/README.md) |
| Verify source or contribute | [Source integrity](docs/development/source-integrity.md), [contributing](CONTRIBUTING.md) |
| Interpret reported results and earlier releases | [Evidence and status](docs/status/README.md), [provenance](docs/provenance/README.md) |

## Development and upstream

The default and integration branch of [this fork](https://github.com/Donglomur/brain-researcher-benchmark)
is `publish/neuroscience-200`. Use a feature branch and a reviewed PR into it;
see the [development guide](docs/DEVELOPMENT.md).

The original [brain-researcher/brain-researcher-benchmark](https://github.com/brain-researcher/brain-researcher-benchmark)
examples—GRADIENT-001, SOCIALBRAIN-001 and DEVCONN-001—are preserved under
[examples/original-three](examples/original-three/README.md), separately from the
newer task inventory and its scientific claims.
