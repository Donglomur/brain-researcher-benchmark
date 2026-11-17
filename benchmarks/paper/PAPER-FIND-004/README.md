# Brain-wide representations of prior information in mouse decision-making

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-004`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The paper has an ordered neural-decoding R-squared endpoint, but exact regional baseline values and the paper-compatible runtime are unrecovered. Pinned generic author defaults and the local evaluator differ from journal cohort, folds and aggregation; significant regions or a mouse-held-out extension cannot substitute.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 14027 bytes; SHA-256 `b6b09302224e7e3b7b9e72f845446e8891a80309a24fbf239929aaf70198ff10`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Exports trusted native prediction dictionaries and computes pooled prior R², repeated-run pseudo-session inference, regional Fisher/BH summaries and matched descriptive motor contrasts for the complete declared subset. Pinned generic-script defaults differ from journal methods; paper-wide cohort/multiplicity, authentic target/pseudo-generation and fitting, native formatter compatibility, held-mouse improvement, rights and protected qualification remain unresolved. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/int-brain-lab/prior-localization)
- [Paper](https://www.nature.com/articles/s41586-025-09226-1)
- [Source](https://int-brain-lab.github.io/iblenv/notebooks_external/data_release_brainwidemap.html)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
