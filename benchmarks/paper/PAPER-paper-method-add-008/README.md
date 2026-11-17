# Opening the black box toward a modular approach to spike sorting

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-add-008`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

**Current complete-primary paired-outcome admission is unavailable.** Independent reproduction remains separately assessable under the stated source limits. Complete primary pairing is unavailable under the reviewed primary and retained source scopes. Retained source scope and coverage: Preserve the genuine original Figure 7 simulated ground-truth spike-accuracy comparison across the five seeded static/drifting realizations and four sorters, with its source-defined companion error/runtime results. Its simulated population and accuracy estimand differ from the retained empirical primary; it cannot satisfy primary reproduction or improvement. Reviewed source limits: The retained DANDI inventory does not freeze a selected recording population; neither all 31 assets nor all three Figure 8 datasets are automatically required. The prospective A3702 DANDI asset and the author's session-qualified source filename have not been established as the same recording. Source-supported curation tables and a drift raster do not by themselves define quantitative drift robustness or cross-sorter spike agreement; historical prose cannot create a published estimand. Source preprocessing-order differences, motion defaults, dependency versions and curation-model identities remain unresolved; silently normalizing them would not establish original-paper reproduction. Exact empirical reference outputs and a scientifically defensible superiority criterion remain unresolved. Simulation matching, source baseline arrays and aggregation also remain unresolved. Final-paper bytes and every panel/metric assignment were not newly authenticated in this review. A mixed empirical-primary/simulation-secondary outcome bundle must remain unavailable as full-primary success if the schema cannot represent the distinction.

**Primary scientific scope:** The retained empirical four-sorter comparison on the original DANDI000939-linked recording scope: complete unit yields and source-defined curation-quality outputs, with source-supported drift/agreement outputs and their indispensable controls once authenticated. This does not automatically select every Figure 8 dataset or every asset in the DANDI inventory. Empirical superiority remains unavailable without an independently justified criterion; more units or more favorable curation labels alone do not establish better spike recovery.

**Retained secondary policy:** Preserve the genuine original Figure 7 simulated ground-truth spike-accuracy comparison across the five seeded static/drifting realizations and four sorters, with its source-defined companion error/runtime results. Its simulated population and accuracy estimand differ from the retained empirical primary; it cannot satisfy primary reproduction or improvement.

- [Reproduction proposal (inspection only)](reproduction.v2.json)
- [Primary and retained secondary scope decision](../../../docs/provenance/paper-outcome-scope-decisions.v1.json)
- [Primary-outcome unavailability record](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | unavailable | unavailable | unavailable | Unknown |
| Reproduction | Paper data author code | unavailable | unavailable | unavailable | Unknown |
| Improvement | Paper data | unavailable | unavailable | unavailable | Unknown |
| Improvement | Paper data author code | unavailable | unavailable | unavailable | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Retained secondary improvement policy

This preserved policy remains source evidence for a different or narrower scientific question. It is unavailable for primary outcome admission and does not define primary paper success.

**Disposition:** source\_unresolved. The same source paper evaluates end-to-end spike sorting against known simulated spike trains in Figure 7 and Figure 7 supplement 1. This is a legitimate ordered original-paper task even though the historical local implementation covers only real-data curation. The source generator and five-seed protocol are recovered, but exact published accuracy/count arrays, dependency-bound matching defaults and figure aggregation are not yet pinned, so no improvement episode is admitted.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 49797 bytes; SHA-256 `53230b201db7161f54333460b35ec94799fab4abca189c8c5e6de8653772fdba`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Reduces complete native exports for four sorters into source curation distributions and a full Kilosort4 Bombcell-good raster. A3702 source-path identity, native sorter/curation execution, configuration and preprocessing discrepancies, model/dependency rights, numeric drift and cross-sorter agreement, protected references and scientific qualification remain open; yield/quality are not universal spike accuracy. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Simulation counts v1](implementations/simulation-counts-v1) — Reviewed source component.
  Scope: Original Figure 7 native-count reduction. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://dandiarchive.org/dandiset/000939/0.250207.0025)
- [Code](https://github.com/SpikeInterface/sorting_components_benchmark_paper)
- [Code](https://github.com/SpikeInterface/sorting_components_benchmark_paper/blob/d93ca4e101c822dfe12b99cc59bdb9d0ca1045b1/notebooks/real_data_figure/generate_curation_data.py)
- [Code](https://github.com/SpikeInterface/sorting_components_benchmark_paper/blob/d93ca4e101c822dfe12b99cc59bdb9d0ca1045b1/notebooks/real_data_figure/make_drift_plots.py)
- [Code](https://github.com/SpikeInterface/sorting_components_benchmark_paper/blob/d93ca4e101c822dfe12b99cc59bdb9d0ca1045b1/notebooks/real_data_figure/sort_all_real_data.py)
- [Code](https://github.com/SpikeInterface/sorting_components_benchmark_paper/blob/d93ca4e101c822dfe12b99cc59bdb9d0ca1045b1/notebooks/real_data_figure/sort_one_piece_of_data.py)
- [Code](https://github.com/SpikeInterface/spikeinterface)
- [Code](https://pmc.ncbi.nlm.nih.gov/articles/PMC13614784/)
- [Code](https://raw.githubusercontent.com/SpikeInterface/sorting_components_benchmark_paper/d93ca4e101c822dfe12b99cc59bdb9d0ca1045b1/LICENSE)
- [Code](https://raw.githubusercontent.com/SpikeInterface/sorting_components_benchmark_paper/d93ca4e101c822dfe12b99cc59bdb9d0ca1045b1/README.md)
- [Code](https://zenodo.org/records/20407862)
- [Paper](https://doi.org/10.7554/eLife.110588.3)
- [Paper](https://elifesciences.org/articles/110588)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
