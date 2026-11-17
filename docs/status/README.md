# Current status and recorded evidence

The repository contains usable source and scoped execution evidence. Complete
scientific qualification requires additional evidence for each task's declared
population, access condition, comparator and evaluation boundary. Registration,
source availability, software verification and model performance are reported
separately.

From the repository root:

```sh
python3 -I -S -B scripts/neurobench.py status
python3 -I -S -B scripts/neurobench.py evidence
python3 -I -S -B scripts/neurobench.py evidence NEURAL-077
python3 -I -S -B scripts/neurobench.py implementations NEURAL-007
```

`status` derives inventory and contract counts from the current registry and counts
records within an explicit set of public reports. `evidence TASK_ID` returns the
reported condition, scope, metrics, comparators, limitations and source hashes.
Neither command opens private inputs or reruns an experiment.

## What has been observed

| Evidence | Recorded scope | What it establishes |
| --- | --- | --- |
| [Difficulty pilot](../science/difficulty-pilot-20261117.md) | Eight scored attempts on four task IDs: four historical paper-calibration attempts and four neural prediction-programme attempts | Outcomes for the exact reported development endpoints and conditions, with baseline comparisons; no whole-task qualification or paper improvement |
| [NEURAL-077 waveform preparation](../../benchmarks/neural/NEURAL-077/implementations/complete-direct-condition-v1/EVIDENCE.json) | All 400 query waveforms and four demonstrations compared with pinned raw samples | Authentic-input materialization; no model execution or scoring |
| [NEURAL-077 viewer rendering](../../benchmarks/neural/NEURAL-077/implementations/visual-viewer-v1/EVIDENCE.json) | Full packet authentication and rendering of selected query ordinals | Authentic image-generation behavior; no evaluated viewer-model episode |
| [Historical execution projections](../provenance/execution/historical-evidence-v1/README.md) | Three profiles, including four NEURAL-023 programme controls | Retained historical execution and interface-control evidence; current environments and complete scientific scope remain unqualified |

These reports overlap. Together they reference **five distinct registered task
IDs**; the three historical profiles and two engineering reports are not five
additional benchmarks or agent attempts. Within the selected reports, there are
**no direct-interpretation or viewer-interpretation model attempts**. The neural
pilot evaluated programmes on exposed development people, so its results do not
measure unseen-population generalization or direct reading of neural signals.

The reports and their original limits remain available even when a task definition
or runtime changes. Source hashes identify the published report being read; they
do not independently authenticate the original executed environment.

## Current scientific definitions

Paper success requires an improvement over the source paper's original endpoint or
complete panel, under the task's fixed observations, cohort, split, metric and
aggregation, with the required controls. Candidates may change architecture,
inference or optimization within the permitted observation and budget boundary.
The author-source recipe defines the baseline comparison. Historical reconstruction
graders and the pilot's paper attempts remain calibration evidence.

The [paper catalog](../../benchmarks/catalog/paper.md) reports dispositions from the
current contracts. At the comprehensive revision's starting point, all 116 paper
registrations had contracts: 20 source-grounded designs, 87 unresolved source
comparisons and nine ineligible papers, with **zero improvement-ready tasks**.
Contract coverage establishes neither a qualified comparator nor an empirical win.
Use `status` for current counts as source preparation and baseline work develop.
The [improvement guide](../science/paper-improvement/README.md) describes the
comparison rule; the [next-build shortlist](../science/paper-improvement/next-builds.md)
identifies original endpoints and remaining native-baseline work.

For neural tasks, direct observation, typed-viewer interpretation, tool-assisted
investigation and frozen prediction programmes are distinct conditions. Available
programme source cannot supply missing observation access, a working viewer or
competent interpretation controls. Each task's current definition and assigned
implementation scope identify which condition the source actually supports.

## Inventory and execution

The [current registry](../../benchmarks/registry.json) and
[generated catalog](../../benchmarks/catalog/README.md) give current task totals,
implementation ownership and physical paths. The original roster contains 100
paper and 100 neural specifications. Expansion registrations, implementation
artifacts, historical runtime declarations and component collections are counted
separately; overlapping counts must not be added together.

Task definitions live at `benchmarks/<track>/<ID>/task.json`. Implementations live
with their task or under [shared source](../../benchmarks/shared/README.md), which
also identifies related-only sources and families without assigned owners.
The [implementation guide](../usage/implementations.md) gives concrete command
routes and their required inputs. An implementation may cover a named endpoint
within a larger task; a task-to-source link does not establish complete execution.

The [source checks](../development/source-integrity.md) verify their declared
ownership, source pins and behavior. Generated controls test software behavior;
authentic-input controls additionally test the declared data path. Model results,
protected evaluation and scientific qualification require their own evidence.
Known gaps include the qualified-imports programme's DMFC dependency, private
scorer inputs for NEURAL-008, NEURAL-023, NEURAL-046 and NEURAL-096, and the absent
historical NEURAL-035 manifest. Consult each task's current scope before running it.

## Earlier construction reports

The [November 16 source audit](audit-2026-11-16.md) and its
[machine-readable census](audits/2026-11-16.json) preserve the scope and findings of
that review. The [clock arithmetic repair](clock-arithmetic-2026-11-17.md) corrects
comparisons of supplied timestamps; authentic native clock lineage remains open.
The [construction update](construction-2026-11-17.md) and
[source-ownership expansion](expansion-2026-11-17.md) record source additions and
generated checks at their respective revisions. Their historical counts do not
override the current registry or establish new scientific results.

The [provenance index](../provenance/README.md) links earlier releases and execution
reports. The [relocation ledger](../provenance/relocations/2026-11-16.json) records
the original physical moves; later source revisions retain their own lineage.
