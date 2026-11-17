# An end-to-end recurrent compressed sensing method to denoise, detect and demix calcium imaging data

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-013`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 30161 bytes; SHA-256 `10ddbdc9848384c6c39c42c55e13e78b4720e2b8649f59c5bddb9f8c03842a12`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Post-assembly mask and trace evaluation across ten fixed recordings using strict IoU greater than 0.5 segmentation metrics, common-detected-neuron trace correlations and paired runtime summaries, plus a tile geometry planner. Native frame/crop mapping, patch assembly, checkpoint/reference identity, donor/tuning partitions, rights and operational protected-reference isolation remain held. Scientific qualification is unknown.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/AllenInstitute/AllenSDK/wiki/Use-the-Allen-Brain-Observatory-%E2%80%93-Visual-Coding-on-AWS)
- [Code](https://github.com/KangningZhang/DeepCaImX/tree/v1.0.0)
- [Code](https://pmc.ncbi.nlm.nih.gov/articles/PMC12327232/)
- [Code](https://raw.githubusercontent.com/KangningZhang/DeepCaImX/305a4827929b2c6e82e44c5c69b2ea9d410e20a4/LICENSE)
- [Code](https://raw.githubusercontent.com/KangningZhang/DeepCaImX/305a4827929b2c6e82e44c5c69b2ea9d410e20a4/README.md)
- [Code](https://www.nature.com/articles/s42256-024-00892-w)
- [Code](https://zenodo.org/records/12650420)
- [Paper](https://www.nature.com/articles/s42256-024-00892-w)
- [Source](https://zenodo.org/records/12650420)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
