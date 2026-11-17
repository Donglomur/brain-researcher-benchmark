# A deep learning strategy to identify cell types across species from high-density extracellular recordings

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-003`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

- [Original-finding reproduction contract](reproduction.v1.json)
- [Paired outcome protocols](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The C4 classification task is ordered, but the complete original confidence/coverage baseline and authenticated original panel are not recovered. The implemented animal-grouped target-blind successor changes the historical comparison and cannot establish a same-task win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 28843 bytes; SHA-256 `cf8ddcf4369953dc79b6ddb13f936985f0cbf71cd0c10935e20a89ba0c79f892`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Paper method replacement 003](implementations/paper-method-replacement-003) — Calibration only.
  Scope: Existing published source retained with its scientific scope. Source ownership does not establish equivalence to the complete task contract or current execution qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.1016/j.cell.2025.01.041)
- [Code](https://github.com/m-beau/NeuroPyxels)
- [Code](https://raw.githubusercontent.com/m-beau/NeuroPyxels/703a10fb43fc7fe0076c9c331e6b52d3195b5e60/npyx/c4/VAE_training/VAE%20singlechannel%20wvf.ipynb)
- [Code](https://raw.githubusercontent.com/m-beau/NeuroPyxels/703a10fb43fc7fe0076c9c331e6b52d3195b5e60/npyx/c4/VAE_training/conv-VAE%20logscale%203D%20ACG.ipynb)
- [Code](https://raw.githubusercontent.com/m-beau/NeuroPyxels/703a10fb43fc7fe0076c9c331e6b52d3195b5e60/npyx/c4/dataset_init.py)
- [Code](https://raw.githubusercontent.com/m-beau/NeuroPyxels/703a10fb43fc7fe0076c9c331e6b52d3195b5e60/npyx/c4/run_baseline_classifier.py)
- [Code](https://raw.githubusercontent.com/m-beau/NeuroPyxels/703a10fb43fc7fe0076c9c331e6b52d3195b5e60/npyx/c4/run_deep_classifier.py)
- [Paper](https://doi.org/10.1016/j.cell.2025.01.041)
- [Source](https://figshare.com/articles/dataset/23702850)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
