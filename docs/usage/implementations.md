# Using implementation source

Current paper success requires surpassing the source paper on the same original
task. Historical reproduction and prospective new-split components below are
calibration or extensions. Read each task's `improvement.v1.json` for the current
comparison, disposition and blockers; source presence cannot promote them to
paper success. See the [improvement guide](../science/paper-improvement/README.md).

Start with a task page in the [paper](../../benchmarks/paper/README.md) or
[neural](../../benchmarks/neural/README.md) track. Its definition and source bindings
identify available implementations, shared programmes, current guidance and
remaining limits. The [registry](../../benchmarks/registry.json) records these
relationships; it is not a claim that every registered source package is ready to run.

```sh
python3 -I -S -B scripts/neurobench.py show NEURAL-077
python3 -I -S -B scripts/neurobench.py evidence NEURAL-077
python3 -I -S -B scripts/neurobench.py show PAPER-FIND-050
python3 -I -S -B scripts/neurobench.py implementations PAPER-FIND-050
```

Run these metadata commands from the repository root. A task may have retained
predecessors, alternate scientific scopes or several implementation components.
The compact `implementations` view resolves current package paths, roles and scope
limits, including programmes without a legacy runtime registration. Assigned
implementations and related scientific sources are listed separately. `show`
includes the same view alongside the task definition. These commands inspect
metadata without importing implementation code or opening datasets or raw runtime receipts.
The selected public reports shown by `evidence` retain their reported conditions,
metrics and limits; they do not qualify the currently checked-out runtime.
Use the package matching the selected task contract and access condition; ownership
alone does not select a new scientifically preferred route. The
[shared-source index](../../benchmarks/shared/README.md) distinguishes multi-task
programmes, related-only sources and families without an assigned task owner;
location in that directory does not create a task binding.

## Inspect EEG and sleep inputs

The [common operator route](../operator-routes.md) supports NEURAL-077's complete
400-trial EEG development panel and NEURAL-007's complete 5,450-epoch sleep
development panel, each from two previously exposed people. Start with source
discovery:

```sh
python3 -I -S -B scripts/neurobench.py operator routes
```

For input inspection, set `EXTERNAL_DATA_ROOT` to the provisioned asset root and
`EXTERNAL_EVIDENCE_ROOT` to an existing operator-controlled directory outside the
checkout. The example creates a new `inspect-eeg` directory:

```sh
python3 -I -S -B scripts/neurobench.py operator inspect NEURAL-077 \
  --data-root "$EXTERNAL_DATA_ROOT" \
  --output "$EXTERNAL_EVIDENCE_ROOT/inspect-eeg"
```

Use `NEURAL-007` and a fresh output directory for sleep. For an existing lifecycle
packet, point the data root at its `inputs/` directory and add `--layout prepared`.
Inspection authenticates the complete public allowlist against the packaged pins;
it does not open development targets or run a model. It does not download missing
data or accept arbitrary recordings from the same study.

The operator guide gives the preparation, frozen-programme and Docker grading
commands. Grading requires explicit artifact locations, the preinstalled native
image and a mandatory purpose (`development-control` or `model-evaluation`). A
purpose label does not replace method provenance, protected evaluation or scientific
qualification. Preserve both successful and failed outputs outside the checkout.

## Separate the question from the access condition

For paper tasks, inspect `paper-contract TASK_ID` before selecting a scorer.
Historical `score` and `run` routes require `--calibration`; their outputs cannot
establish the current improvement objective. Candidates may change architecture,
inference or optimization while preserving the contract's permitted observations,
cohort, split, evaluation, required controls and resource budget. The author-source
recipe defines the baseline comparison.

For neural tasks, select the specific direct-observation, typed-viewer,
tool-assisted or frozen-programme condition named by the current definition.
Prepared feature inputs, raw waveforms and rendered images expose different
information. A prediction-programme result cannot be reported as direct or viewer
interpretation. The [NEURAL-007 and NEURAL-077 pilot](../science/difficulty-pilot-20261117.md)
contains programme attempts on exposed development people; the separate NEURAL-077
[waveform](../../benchmarks/neural/NEURAL-077/implementations/complete-direct-condition-v1/EVIDENCE.json)
and [viewer](../../benchmarks/neural/NEURAL-077/implementations/visual-viewer-v1/EVIDENCE.json)
reports describe software controls without model evaluation.

## Portable programme sources

The following published packages retain explicit complete-programme scopes and
source-check interfaces. Their actual inputs, protected evaluation, native
execution and scientific qualification have separate requirements.

| Package | Preserved scope | Required beyond source checks |
| --- | --- | --- |
| [NEURAL-029](../../benchmarks/neural/NEURAL-029/implementations/neural029-programme/README.md) | Complete registered GrC1s-to-2s calcium transfer: all required pairs, cells, query trials and 61 times, with the accepted frozen-program boundary | Complete admitted public/private packet, NumPy grader, qualified Docker environment, capacity and outside observation |
| [NEURAL-030](../../benchmarks/neural/NEURAL-030/implementations/neural030-four-cell/README.md) | All 16 cerebellar sessions, four input arms and two agent modes: 128 dispatches | Authentic MAT extraction and five-mouse/clock binding, complete public/private packets, adaptive agent and native environment qualification |
| [NEURAL-078](../../benchmarks/neural/NEURAL-078/implementations/neural078-deferred-grade/README.md) | Full eight-person EEG reconstruction, all 195 report fields and protected grading after producer closure | Admitted authentic collection/reference export, frozen programme, trusted outside observation and native grading qualification |
| [NEURAL-061](../../benchmarks/neural/NEURAL-061/implementations/neural061-persistent-state/README.md) | 423 source sessions, 29 evaluation sessions, six references, ten seeds and both BR/BC arms; persistent fitted state remains in its isolated child | Authentic inputs/targets, qualified native environment, provider/capture/allocation provenance and independent outside observation |
| [CBraMod / PAPER-paper-method-024](../../benchmarks/paper/PAPER-paper-method-024/implementations/cbramod-paired-program/README.md) | 12 datasets; 800 reproduction artifacts, 60 improvement cases and 420 comparator slots per condition | All 65 exact external official-code files, authentic data/reference lineage, native execution and 8GB output capacity qualification |
| [PAPER-FIND-050](../../benchmarks/paper/PAPER-FIND-050/implementations/paper-find050-programme/README.md) | Critical initialization: 26 operations, 40 complete 10,000-mode spectra, 29 main sessions and a separate prospective memory endpoint | Exact external official source, authentic inputs and all 32 scientific/runtime gates, including live-issuer and full-capacity qualification |

These source scopes preserve their declared populations and comparison conditions.
They do not establish broad paper reproduction, neural understanding, improvement
or an increased completed-benchmark count.

## Current package roots

Some package READMEs preserve their original release text, including commands that
use the former directory layout. From the repository root, select
the matching current `PKG` assignment below before following the package's command
sequence. The [current portable-source workflow](../../.github/workflows/portable-benchmark-source.yml)
provides the selected verifier commands and source pins for this layout.

| Package | Current shell assignment |
| --- | --- |
| NEURAL-029 | `PKG=benchmarks/neural/NEURAL-029/implementations/neural029-programme` |
| NEURAL-030 | `PKG=benchmarks/neural/NEURAL-030/implementations/neural030-four-cell` |
| NEURAL-078 | `PKG=benchmarks/neural/NEURAL-078/implementations/neural078-deferred-grade` |
| NEURAL-061 | `PKG=benchmarks/neural/NEURAL-061/implementations/neural061-persistent-state` |
| CBraMod / PAPER-paper-method-024 | `PKG=benchmarks/paper/PAPER-paper-method-024/implementations/cbramod-paired-program` |
| PAPER-FIND-050 | `PKG=benchmarks/paper/PAPER-FIND-050/implementations/paper-find050-programme` |

These assignments select physical directories. Historical source prose remains
bound to its original revision; embedded capsule names, manifest member names,
logical identifiers and historical pins retain their declared meaning. Do not
replace those identifiers merely because a directory moved. Use the current root
and current CI binding for execution, and preserve the package's input, environment
and admission requirements.

## Check source before execution

Use a trusted, reviewed revision. Each package's guide describes its own source
inventory, verifier and control commands. Authenticate a verifier against the
reviewed release or current CI binding before executing it; a verifier cannot
establish trust in its own bootstrap. The
[portable-source workflow](../../.github/workflows/portable-benchmark-source.yml)
records its selected packages and commands. Per-package counts, pins and environments
belong to that exact revision, rather than a duplicated checklist on this page.

The [repository ownership and source-integrity checks](../development/source-integrity.md)
have distinct scopes: the first covers the artifact ownership and layout declared
in the [current registry](../../benchmarks/registry.json); the second verifies recorded
source pins for four enrolled bundles. Passing either
does not supply missing dependencies or native qualification. Generated source
controls are software evidence, not authentic-data or model results.

## Prepare an actual run

Read the implementation's required input schema, external code dependencies,
interpreter/environment, resource envelope and producer/evaluator separation.
Authentic recordings and protected references may be external. Some packages also
retain unavailable source dependencies: the qualified-imports programme lacks its
required DMFC engine; several registered neural scorer bridges require private
inputs; NEURAL-035 lacks its historical manifest. Read the affected task's registry
notes before selecting an implementation. A nearby implementation is not an
interchangeable substitute. Package-local licenses and attribution notices
continue to apply after relocation.

For existing finished-submission routes, see [artifact grading](artifact-grading.md).
For a controlled paper or neural comparison, use the [study-design guide](../science/study-design/README.md)
and bind its complete endpoint and access conditions before collecting outcomes.
The generic `run` and `score` commands retain their own admission checks. Campaign
commands refuse execution without explicit `campaign_authority` and the required
private inputs. A source binding or successful metadata query does not enable
execution automatically. Delivery exports are local generated files under the
ignored `.neurobench/exports/` directory.
