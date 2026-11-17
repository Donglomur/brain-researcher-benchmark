# Opening the black box toward a modular approach to spike sorting

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-add-008`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The same source paper evaluates end-to-end spike sorting against known simulated spike trains in Figure 7 and Figure 7 supplement 1. This is a legitimate ordered original-paper task even though the historical local implementation covers only real-data curation. The source generator and five-seed protocol are recovered, but exact published accuracy/count arrays, dependency-bound matching defaults and figure aggregation are not yet pinned, so no improvement episode is admitted.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 43949 bytes; SHA-256 `04e695a46c75f81900c6d36e8848d02cb3dcac9ec7e67feddb8eb6ba5e109064`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Reduces complete native exports for four sorters into source curation distributions and a full Kilosort4 Bombcell-good raster. A3702 source-path identity, native sorter/curation execution, configuration and preprocessing discrepancies, model/dependency rights, numeric drift and cross-sorter agreement, protected references and scientific qualification remain open; yield/quality are not universal spike accuracy. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

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
