# Robust self-supervised denoising of voltage imaging data using CellMincer

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-030`
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

**Disposition:** source\_unresolved. The original paired-electrophysiology denoising task is ordered, and several numeric secondary results are recovered, but the exact published prominence-binned F1\* profile, complete original cohort mapping and spectral/peak evaluation conventions are not recovered. The existing whole-cell held-out panel changes the paper’s self-supervised26-training/22-evaluation design and cannot establish a same-task paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 163328 bytes; SHA-256 `a21286f536964a73a8b4d510696c6294d464779d80b9425cdc5402e02b4d4fa8`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prepared paired optical/electrical trace assessment for the saved 22 TIFF/ABF pairs across nine filename-derived cell groups, including prominence-tolerant peak F1, lagged correlation, false-event and residual-spectrum metrics. Native loading, ROI/channel/clock/calibration validation, authentic denoiser execution, historical training/evaluation identity, dataset rights and protected EP admission remain held. Scientific qualification is unknown. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Ep affine calibration v1](implementations/ep-affine-calibration-v1) — Reviewed source component.
  Scope: Selected inactive source component for the existing task. The package documentation and source contracts define its retained scope; runtime admission and scientific qualification remain separate.
- [Original metric kernels v1](implementations/original-metric-kernels-v1) — Reviewed source component.
  Scope: Reviewed original metric kernels and generated software controls; authentic evaluation, source operand custody and scientific claims remain separately scoped.
- [Native roi v1](implementations/native-roi-v1) — Reviewed source component.
  Scope: CellMincer optical ROI extraction. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/cellarium-ai/CellMincer)
- [Code](https://github.com/cellarium-ai/CellMincer/blob/8cc2dd3192671e4287c16a3a92c4ccdbd2eb7942/README.md)
- [Code](https://github.com/cellarium-ai/CellMincer/blob/8cc2dd3192671e4287c16a3a92c4ccdbd2eb7942/configs/manifest/miller-ephys-standard.yaml)
- [Code](https://github.com/cellarium-ai/CellMincer/blob/8cc2dd3192671e4287c16a3a92c4ccdbd2eb7942/configs/preprocess/pairedephys.yaml)
- [Code](https://pmc.ncbi.nlm.nih.gov/articles/PMC11618097/)
- [Code](https://raw.githubusercontent.com/cellarium-ai/CellMincer/8cc2dd3192671e4287c16a3a92c4ccdbd2eb7942/LICENSE)
- [Code](https://raw.githubusercontent.com/cellarium-ai/CellMincer/8cc2dd3192671e4287c16a3a92c4ccdbd2eb7942/README.md)
- [Code](https://www.nature.com/articles/s44303-024-00055-x)
- [Paper](https://www.nature.com/articles/s44303-024-00055-x)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
