# Neuroscience Research Benchmarks

Evaluating whether AI agents can reproduce neuroscience findings, improve methods,
and understand neural data.

**Under construction.** The catalogs describe task drafts and supporting source.
Qualification across complete scientific contracts has not been established.

**[Paper track](benchmarks/catalog/paper.md) · [Neural-data track](benchmarks/catalog/neural.md) · [Source packages](docs/neuroscience-benchmarks/PORTABLE_COMPONENTS.md) · [Evidence and status](docs/neuroscience-benchmarks/REPO_QUALITY_20261116.md)**

## Two research tracks

| Track | What we ask | Controlled comparison |
| --- | --- | --- |
| **Paper reproduction and improvement** | Given a neuroscience paper and its data, can an agent reproduce a defined result and improve it? | Paper + data versus paper + data + official code. Reproduction and prospective improvement have separate endpoints and matched budgets. |
| **Neural-data understanding** | Can a general model infer useful structure or predictions from neural and behavioral observations? | A prediction program written in advance versus case-by-case investigation, with explicit tool, specialist-model and scientific-context access. |

## What is available

| Measure | Current coverage |
| --- | --- |
| Registered task drafts | **234** — 116 paper and 118 neural |
| Linked runtime manifests | **95** |
| Portable programme source packages | **6** — NEURAL-029/030/061/078, CBraMod and PAPER-FIND-050 |
| Supporting source component collections | **73** |
| Qualified across complete scientific contracts | **Not established** |

These counts overlap and measure different kinds of source coverage. Some drafts
share papers, datasets or specification aliases. Generated software checks and
historical finite acceptances do not establish a finished-benchmark count or new
agent results. See the [construction record](docs/neuroscience-benchmarks/CONSTRUCTION_STATUS.md)
and [historical execution evidence](docs/neuroscience-benchmarks/historical-evidence-v1/README.md).

## Start here

```sh
git clone --branch publish/neuroscience-200 --single-branch https://github.com/Donglomur/brain-researcher-benchmark.git
cd brain-researcher-benchmark
python3 tools/neurobench.py list --track paper
python3 tools/neurobench.py list --track neural
python3 tools/neurobench.py show NEURAL-017
python3 tools/neurobench.py status
python3 tools/neurobench.py check
```

These commands use Python's standard library to inspect the public catalog.
They do not download data or run scientific evaluations.

| Next step | Guide |
| --- | --- |
| Find a task and its sources | [Paper catalog](benchmarks/catalog/paper.md), [neural catalog](benchmarks/catalog/neural.md), [catalog format](benchmarks/catalog/README.md) |
| Use a published implementation | [Portable source packages](docs/neuroscience-benchmarks/PORTABLE_COMPONENTS.md) and [component index](benchmarks/catalog/components.md) |
| Check source or grade an artifact | [Source integrity](docs/neuroscience-benchmarks/SOURCE_INTEGRITY.md) and [artifact grading](docs/neuroscience-benchmarks/ARTIFACT_GRADING.md) |
| Design a matched comparison | [Paired-study reporting](docs/neuroscience-benchmarks/PAIRED_STUDY_REPORTING.md) and [study-description validator](components/study_binding_validator_v1/README.md) |

Each package documents its inputs, dependencies and commands. Authentic recordings,
protected references and qualified runtimes are separate requirements; the generic
`run` and `score` interfaces retain their own admission rules.

## Repository structure

| Directory | Contents |
| --- | --- |
| [`benchmarks/`](benchmarks/README.md) | Task definitions, expansion registries, task packages and generated catalog |
| [`components/`](components/) · [`benchmarks/scientific_components/`](benchmarks/scientific_components/) | Reusable preparation, scoring and execution source |
| [`contracts/curation/`](contracts/curation/README.md) | Paper intake and evaluation-design contracts |
| [`docs/`](docs/README.md) | Scientific scope, operator guides, evidence and development workflow |
| [`tools/`](tools/) · [`tests/`](tests/) | Public catalog tools and software checks |
| [`examples/original-three/`](examples/original-three/README.md) | Inherited worked examples and their archived planning/results documents |

Task IDs and scientific package paths remain stable because manifests, hashes and
operator commands refer to them. The catalog supplies a common way to browse them.
The root `TOPIC_TRIAGE_CONTROLLER_PROMPT.md` remains the active curation worker
contract used by its validator.

## Development

The default and integration branch of **this fork** is **`publish/neuroscience-200`**.
Open a short-lived feature branch and a PR into it. See [contributing](CONTRIBUTING.md)
and the [fork workflow](docs/DEVELOPMENT.md) for review, CI and branch cleanup.

## Upstream examples

This programme builds on [brain-researcher/brain-researcher-benchmark](https://github.com/brain-researcher/brain-researcher-benchmark).
Its **GRADIENT-001**, **SOCIALBRAIN-001** and **DEVCONN-001** are preserved as
[exposed worked examples](examples/original-three/README.md), separate from the
234 neuroscience task drafts. Their original planning and reported results live
in [upstream history](examples/original-three/upstream-history/README.md).
The [legacy recovery audit](docs/neuroscience-benchmarks/LEGACY_TASK_RECOVERY_20261116.md)
explains reuse limits for the other preserved task branches.
