# Rastermap: a discovery method for neural population recordings

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-010`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 28326 bytes; SHA-256 `8764f79a3610f0323b82f342d2bfde9a98b5551241604d44af8684c1a97932bd`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Evaluates both complete declared processed hippocampal and mouse source populations using prospective held-out neighborhood retention, behavior-to-superneuron prediction and paired tie-aware order stability. Native Rastermap fitting/preprocessing, source paper/tutorial differences, zero-variance exclusions, empirical baselines, protected execution, rights and full-population quadratic runtime/memory qualification remain open.

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
