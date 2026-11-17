# Measuring the dynamic balance of integration and segregation underlying consciousness, anesthesia, and sleep in humans

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-012`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** design\_ready. The paper contains an ordered consciousness-state prediction task in Figure 5 with a published random-forest baseline. This design scopes the comparison to the complete original Dataset-1 leave-one-subject-out result in Figure 5b,c, including all 19 subjects and its required source controls/companion metrics. Original label/timing bindings, classifier replay and calibrated sampling remain unresolved; the local state-contrast evaluator does not implement this task. No readiness is claimed.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 24620 bytes; SHA-256 `042001419a4c65e36666566d190553df8624073cf0345d672e812a53e0958184`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Source-guided static integration/segregation/ISD kernel with prospective complete-roster paired-state scoring, simpler connectivity/amplitude/motion comparisons and phase-randomized controls. Original BCT/diagonal parity, native MAT population and condition mapping, all Dataset 3–5 state coverage, variable-length policy and Dataset-4 overlap remain unresolved; transition and prediction branches are absent. Authentic references, rights, protected replay and scientific qualification remain open. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/janghw4/multilevel-integration-segregation-balance)
- [Paper](https://www.nature.com/articles/s41467-024-53299-x)
- [Source](https://figshare.com/articles/dataset/26367193)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
