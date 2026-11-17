# A brain-wide map of neural activity during complex behaviour

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-005`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 15756 bytes; SHA-256 `e3871b4438eeb026643dd24f74f8730a706a67b85d70f36c56e9d55838f41174`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Sorted spikes and versioned trial exports to stimulus/choice/feedback single-cell sensitivity, common source masks, regional dual-test fractions and separate mouse-weighted summaries. Native IBL cohort/unit UUID/QC reconciliation, full regional manifest, paper-versus-example choice-window adjudication, authentic numerical agreement, protected references and scientific qualification remain held. Population decoding, trajectories, GLM and whole-atlas reproduction are outside this component.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/int-brain-lab/paper-brain-wide-map)
- [Paper](https://www.nature.com/articles/s41586-025-09235-0)
- [Source](https://int-brain-lab.github.io/iblenv/notebooks_external/data_release_brainwidemap.html)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
