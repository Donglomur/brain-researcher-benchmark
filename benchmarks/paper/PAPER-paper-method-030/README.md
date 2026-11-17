# Robust self-supervised denoising of voltage imaging data using CellMincer

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-030`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 162244 bytes; SHA-256 `6de9351af83dcd990e576873f65802b6df7df963dbdf3c008100b1d87dc0806e`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prepared paired optical/electrical trace assessment for the saved 22 TIFF/ABF pairs across nine filename-derived cell groups, including prominence-tolerant peak F1, lagged correlation, false-event and residual-spectrum metrics. Native loading, ROI/channel/clock/calibration validation, authentic denoiser execution, historical training/evaluation identity, dataset rights and protected EP admission remain held. Scientific qualification is unknown.

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
