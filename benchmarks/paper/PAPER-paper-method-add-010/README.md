# A data-driven approach to identifying and evaluating connectivity-based neural correlates of conscious visual perception

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-add-010`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** design\_ready. The source has ordered stimulus-decoding accuracies and a recoverable classifier recipe. Exact publication/data/supplement identity, original folds and the complete endpoint matrix remain unbound. The existing nested single-measure component changes selection, weighting and input assumptions; it cannot establish a same-task paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 75099 bytes; SHA-256 `22a5f813e025c553f27b91519909e4e5e206dcbd056d8dd683b74e943d72efdb`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Conditional nested connectivity evaluation](docs/nested-connectivity-v1.md)

## Implementation artifacts

- [Nested connectivity v1](implementations/nested-connectivity-v1) — Calibration only.
  Scope: Conditional 246-feature nested participant-held-out classifier with training-only standardization and complete supplied-protocol support. Canonical feature eligibility, source/cohort/correction joins, upstream functional-connectivity extraction, the matched nuisance comparison, competent references, protected execution and whole-task scientific qualification remain held. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.1093/nc/niag029)
- [Code](https://doi.org/10.17617/1.WQA3-WK71)
- [Code](https://github.com/anniegbryant/MEG_functional_connectivity)
- [Code](https://raw.githubusercontent.com/anniegbryant/MEG_functional_connectivity/cab648bbe2eab7093f9ab7b9a5fcddabf28e60a0/README.md)
- [Code](https://zenodo.org/records/18294156)
- [Paper](https://academic.oup.com/nc/article/2026/1/niag071/8916853)
- [Paper](https://doi.org/10.1093/nc/niag029)
- [Source](https://zenodo.org/records/15315238)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
