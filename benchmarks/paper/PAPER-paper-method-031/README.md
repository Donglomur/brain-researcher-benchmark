# Real-time self-supervised denoising for high-speed fluorescence neural imaging

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-031`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. FAST has an ordered temporal-fidelity comparison, but the exact numeric source baseline and pixel/ROI/synchronization recipe for the registered real recordings are not recovered. The existing evaluator deliberately uses a prospective group-disjoint recipe, which changes the original same-stack self-supervised task and cannot award a source-paper win. Published throughput alone is not a substitute for denoising quality.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 19082 bytes; SHA-256 `226d7b77017d7fef1864401a0fc84598ea69a2fd6a425b8ef7ae7a2995a99381`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prospective measurement evaluator over complete exported movie panels: fixed-ROI traces and ΔF/F, temporal agreement and event diagnostics, synthetic-only image errors, and declared end-to-end latency across FAST, candidate and raw-input conditions. Native FAST fitting/inference and original payload ingestion, authentic real calcium/voltage population, figure normalization/tolerance, competent reference, measured lifecycle resources and protected qualification remain open. Real recordings are not treated as clean-target ground truth; source-specific data rights remain separate. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Native temporal audit v1](implementations/native-temporal-audit-v1) — Reviewed source component.
  Scope: FAST native temporal audit. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.5281/zenodo.15872025)
- [Code](https://github.com/FDU-donglab/FAST)
- [Code](https://raw.githubusercontent.com/FDU-donglab/FAST/6f92663f7a36589507cac57c8d24cfd8adbce7b1/LICENSE)
- [Code](https://raw.githubusercontent.com/FDU-donglab/FAST/6f92663f7a36589507cac57c8d24cfd8adbce7b1/README.md)
- [Code](https://www.nature.com/articles/s41467-025-64681-8)
- [Paper](https://www.nature.com/articles/s41467-025-64681-8)
- [Source](https://zenodo.org/records/15872025)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
