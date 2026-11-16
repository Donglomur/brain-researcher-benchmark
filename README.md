# Neuroscience research benchmarks

A neuroscience benchmark programme in the public fork
[Donglomur/brain-researcher-benchmark](https://github.com/Donglomur/brain-researcher-benchmark),
based on [brain-researcher/brain-researcher-benchmark](https://github.com/brain-researcher/brain-researcher-benchmark).
Our work is integrated on **`publish/neuroscience-200`**. The fork's default branch
is still `master`; upstream has not been changed by this programme.

We are building two complementary evaluations:

| Track | Research question | Comparison |
| --- | --- | --- |
| **Paper reproduction and improvement** | Can an agent reproduce a defined neuroscience result, then improve it under a fixed evaluation? | Paper + data versus paper + data + official code, with matched budgets and separate reproduction/improvement scores. |
| **Neural data understanding** | What can a general model infer from neural or behavioral observations? | Fixed prediction programs versus case-by-case investigation, with explicit tool, model and scientific-context access. |

**234 registered task drafts: 116 paper and 118 neural.** This is a source catalog,
not a claim of 234 finished benchmarks or independent studies. Some tasks share
studies, datasets or specification aliases. The programme records 42 historical
finite acceptances; the current number qualified across their complete registered
contracts is **not established**. No new LLM performance or code-assistance effect
is established by these source releases. See the [dated evidence and scope record](docs/neuroscience-benchmarks/CONSTRUCTION_STATUS.md).
The [repository quality review](docs/neuroscience-benchmarks/REPO_QUALITY_20261116.md)
identifies the remaining delivery, scientific-scope and evaluation gaps.
The [historical execution evidence](docs/neuroscience-benchmarks/historical-evidence-v1/README.md)
explains what three inspected program/control profiles actually established and what remains unqualified.

## Start here

```sh
git clone --branch publish/neuroscience-200 --single-branch https://github.com/Donglomur/brain-researcher-benchmark.git
cd brain-researcher-benchmark
python3 tools/neurobench.py list
python3 tools/neurobench.py list --track neural
python3 tools/neurobench.py show NEURAL-017
python3 tools/neurobench.py status
python3 tools/neurobench.py check
```

These metadata commands work from the public checkout with Python's standard
library. They inspect definitions and source availability; they do not download
neural data or establish scientific readiness. There is no single installation
command that makes every draft runnable.

- [Paper catalog](benchmarks/catalog/paper.md): task IDs and source specifications.
- [Neural catalog](benchmarks/catalog/neural.md): task IDs and source specifications.
- [Component index](benchmarks/catalog/components.md): published code packages and guides.
- [Catalog format and regeneration](benchmarks/catalog/README.md): deterministic metadata and declared scope.

## Use the neuroscience construction source

Choose a component's guide for its dependencies, data requirements and exact
commands. The checkout supplies source and selected generated-data checks;
original recordings, protected references and deployment bindings are separate.

| Starting point | What it supplies |
| --- | --- |
| [Portable source packages](docs/neuroscience-benchmarks/PORTABLE_COMPONENTS.md) | NEURAL-029, NEURAL-061, CBraMod and PAPER-FIND-050 source checks, commands and external prerequisites. |
| [Paired-study description checks](components/study_binding_validator_v1/README.md) | Validate declared assignments, budgets, endpoint denominators, exposure and stopping policies for both tracks. |
| [Source integrity](docs/neuroscience-benchmarks/SOURCE_INTEGRITY.md) | Verification instructions for explicitly enrolled source bundles. Passing checks establishes software consistency. |
| [Direct artifact grading routes](docs/neuroscience-benchmarks/ARTIFACT_GRADING.md) | TMS, motor decoding, Purkinje, optogenetics and NEURAL-022 scorers for finished submissions, with their external-asset requirements. |
| [DMFC provisioning](benchmarks/neuroscience/neural-095-four-cell/PROVISIONING.md) | Original-NWB acquisition/conversion and the four-output scoring contract. |
| [PFC provisioning](benchmarks/neuroscience/pfc-conditional-portable-profile-v1/PROVISIONING.md) | Separate participant, article, official-method and license assets; runtime admission remains external. |
| [Findlay complete preparation](components/findlay-complete-preparation/README.md) | Full 13-table / 98-family preparation source with operator-supplied original archives and audit metadata. |

The generic `score` and `run` interfaces retain their existing private-ledger and
runtime admission requirements. They are not universal public evaluators. Use
each published component's documented command and required assets.

## Repository layout

| Path | Purpose |
| --- | --- |
| [`benchmarks/catalog/`](benchmarks/catalog/README.md) | Generated navigation for all registered drafts and public components. |
| [`benchmarks/manifests/`](benchmarks/manifests/) | The original 100 paper and 100 neural source specifications. |
| [`benchmarks/neuroscience/`](benchmarks/neuroscience/) | Task packages, expansion definitions and operator guides. |
| [`benchmarks/scientific_components/`](benchmarks/scientific_components/) · [`components/`](components/) | Reusable scoring, preparation and execution source. Components are not additional task IDs. |
| [`tools/`](tools/) · [`tests/`](tests/) | Catalog/CLI utilities and their checks. |
| [`docs/`](docs/README.md) | Scientific scope, status, source verification and development guides. |
| [`contracts/curation/`](contracts/curation/) | Shared paper-intake and evaluation-design contracts. |
| [`examples/original-three/`](examples/original-three/README.md) | The three original Harbor tasks, preserved separately from the neuroscience construction suite. |

Canonical task IDs and source-package paths are retained because manifests,
scorers and verification records refer to them. The catalog provides a common
entry point across those packages.

## Original examples

The upstream **GRADIENT-001**, **SOCIALBRAIN-001** and **DEVCONN-001** tasks are
worked examples of uncued scientific judgment. Their [inherited results](RESULTS.md)
and [authoring guide](INTERN_GUIDE.md) are separate from the new suite. Their
published solutions make them examples rather than fresh held-out evaluations.
See [the examples guide](examples/original-three/README.md) for commands.

## Contribute

Use a short-lived branch and open a PR into **`publish/neuroscience-200` in this
fork**. Review and CI precede merging; completed PR branches are automatically
deleted. A fork, a branch and a PR serve different purposes—see the
[development workflow](docs/DEVELOPMENT.md) and [contribution guide](CONTRIBUTING.md).

Component release details are retained in the [dated source notes](docs/history/SOURCE_COMPONENTS_20261116.md).
