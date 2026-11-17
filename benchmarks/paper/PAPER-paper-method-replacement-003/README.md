# A deep learning strategy to identify cell types across species from high-density extracellular recordings

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-003`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. The C4 classification task is ordered, but the complete original confidence/coverage baseline and authenticated original panel are not recovered. The implemented animal-grouped target-blind successor changes the historical comparison and cannot establish a same-task win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 28559 bytes; SHA-256 `094f19393a17a67e2d7456112837afbd15bc981fb9b0bb366a179d9fd0f95ebf`.

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
