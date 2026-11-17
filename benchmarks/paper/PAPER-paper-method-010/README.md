# Rastermap: a discovery method for neural population recordings

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-010`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The source paper has a defensible ordered task: recover the original within-module ordering in its Figure 1 five-module simulation benchmark. The original generator, population, ten realization IDs and metric implementations are recoverable, but the published numeric Rastermap score panel and original result artifact have not been recovered and pinned. No scientific run establishes an author replay. The legacy empirical evaluator is not the simulation scorer and cannot establish this paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 29064 bytes; SHA-256 `cc334ec68c203a7f9b64390e5b6a00123a4c0b469a45d0b6d5ae514063a089cc`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Evaluates both complete declared processed hippocampal and mouse source populations using prospective held-out neighborhood retention, behavior-to-superneuron prediction and paired tie-aware order stability. Native Rastermap fitting/preprocessing, source paper/tutorial differences, zero-variance exclusions, empirical baselines, protected execution, rights and full-population quadratic runtime/memory qualification remain open. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.17605/OSF.IO/XN4CM)
- [Code](https://github.com/MouseLand/rastermap/blob/b37644ea52c4cd81f143a9c2cec90286ffd61c49/notebooks/rastermap_largescale.ipynb)
- [Code](https://github.com/MouseLand/rastermap/blob/b37644ea52c4cd81f143a9c2cec90286ffd61c49/notebooks/rastermap_singleneurons.ipynb)
- [Code](https://github.com/MouseLand/rastermap/blob/b37644ea52c4cd81f143a9c2cec90286ffd61c49/paper/loaders.py)
- [Code](https://github.com/MouseLand/rastermap/tree/main/paper)
- [Code](https://raw.githubusercontent.com/MouseLand/rastermap/b37644ea52c4cd81f143a9c2cec90286ffd61c49/LICENSE)
- [Code](https://raw.githubusercontent.com/MouseLand/rastermap/b37644ea52c4cd81f143a9c2cec90286ffd61c49/README.md)
- [Code](https://www.nature.com/articles/s41593-024-01783-4)
- [Paper](https://www.nature.com/articles/s41593-024-01783-4)
- [Source](https://api.osf.io/v2/nodes/xn4cm/files/osfstorage/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
