# Neuroscience Research Benchmarks

Can AI agents reproduce neuroscience findings, improve research methods, and
understand neural data?

This repository develops two benchmark tracks. **The tasks are under construction:**
source code and software checks are available, while complete scientific and
submission qualification remain unestablished.

**[Paper research](benchmarks/paper/README.md) · [Neural-data understanding](benchmarks/neural/README.md) · [Implementations](docs/usage/implementations.md) · [Current status](docs/status/README.md)**

## Two research tracks

| Track | Scientific question | Controlled comparison |
| --- | --- | --- |
| **Paper reproduction and improvement** | Can an agent reproduce a defined result from a neuroscience paper and then improve it? | Paper + data versus paper + data + official code. Historical reproduction and prospective improvement have separate endpoints. |
| **Neural-data understanding** | Can an agent interpret neural or behavioral observations and make useful predictions? | A prediction program written in advance versus case-by-case investigation, with explicit tool and scientific-context access. |

Each track contains **100 original specifications**. Later expansion drafts bring
the registered inventory to **116 paper and 118 neural tasks**. These are task
registrations; conditions, participants, folds and implementation variants are not
additional benchmarks.

## Explore a task

Open a task folder to find its question, authoritative `task.json`, available
implementations, source citations and documented limits. The
[shared-source index](benchmarks/shared/README.md) distinguishes multi-task
programmes, related-only sources and families without an assigned task owner.

```sh
git clone --branch publish/neuroscience-200 --single-branch https://github.com/Donglomur/brain-researcher-benchmark.git
cd brain-researcher-benchmark
python3 -I -S -B scripts/neurobench.py list --track paper
python3 -I -S -B scripts/neurobench.py list --track neural
python3 -I -S -B scripts/neurobench.py show PAPER-FIND-050
python3 -I -S -B scripts/neurobench.py status
```

These commands inspect public metadata using Python 3.11 or later and the standard
library. Running an implementation requires its own environment, inputs and
admission checks; consult the [implementation guide](docs/usage/implementations.md).

## Repository layout

```text
benchmarks/
  paper/<task-id>/          # paper task definitions and implementations
  neural/<task-id>/         # neural task definitions and implementations
  shared/                  # multi-task, related-only and unassigned source
  registry.json            # task, source and ownership relationships
  catalog/                 # generated browsing views
src/neurobench/             # common framework
scripts/                   # public commands and maintenance entry points
tests/                     # framework and maintenance checks
docs/                      # usage, scientific design, development and provenance
examples/original-three/    # inherited scientific-judgment examples
archive/                   # explicitly inactive retained material
```

| Next step | Guide |
| --- | --- |
| Use available source and understand its limits | [Implementations](docs/usage/implementations.md), [artifact grading](docs/usage/artifact-grading.md) |
| Design a comparison | [Scientific design](docs/science/README.md), [study templates](docs/science/study-design/README.md) |
| Check the source or contribute | [Source integrity](docs/development/source-integrity.md), [contributing](CONTRIBUTING.md) |
| Interpret earlier reports and releases | [Provenance](docs/provenance/README.md), [current status](docs/status/README.md) |

## Development and upstream

The default and integration branch of [this fork](https://github.com/Donglomur/brain-researcher-benchmark)
is `publish/neuroscience-200`. Use a feature branch and a reviewed PR into it;
see the [development guide](docs/DEVELOPMENT.md).

The original [brain-researcher/brain-researcher-benchmark](https://github.com/brain-researcher/brain-researcher-benchmark)
examples—GRADIENT-001, SOCIALBRAIN-001 and DEVCONN-001—are preserved under
[examples/original-three](examples/original-three/README.md), separately from the
newer task inventory and its scientific claims.
