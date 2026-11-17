# A brain-wide map of neural activity during complex behaviour

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-005`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The broad regional representation registration includes genuine original decoding endpoints. However, the reviewed paper/code do not establish the exact original regional score vector and complete cohort/scoring manifest needed for a paper comparison. The local single-cell significance/fraction evaluator cannot substitute for source population decoding. A new cross-mouse split or pooled scalar would be an extension.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 14313 bytes; SHA-256 `6270969b695195653e79685973b7a19409f3e5af791ed959cb3264ce2b77a1f8`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Sorted spikes and versioned trial exports to stimulus/choice/feedback single-cell sensitivity, common source masks, regional dual-test fractions and separate mouse-weighted summaries. Native IBL cohort/unit UUID/QC reconciliation, full regional manifest, paper-versus-example choice-window adjudication, authentic numerical agreement, protected references and scientific qualification remain held. Population decoding, trajectories, GLM and whole-atlas reproduction are outside this component. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Decoder score import v1](implementations/decoder-score-import-v1) — Reviewed source component.
  Scope: Original decoding score import. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/int-brain-lab/paper-brain-wide-map)
- [Paper](https://www.nature.com/articles/s41586-025-09235-0)
- [Source](https://int-brain-lab.github.io/iblenv/notebooks_external/data_release_brainwidemap.html)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
