# Network-aware neuronal activity phenotyping across a complete CRISPRi screen

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-CANDIDATE-20261114-PLEXUS`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The original guide-versus-control AUROC is ordered, but the complete final-paper baseline vector and its archive/version mapping are unrecovered. The installed whole-plate, four-line evaluation changes the original Figure 4 split and population and cannot establish a same-task paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 9820 bytes; SHA-256 `31ce7dcff8df58f00f95886b4af310de0dffc753cbeb700147d100a9142eeffd`.
- [Registration and provenance](../../../docs/provenance/registrations/expansion-20261114-v11/registry.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prospective complete 52-gene/four-line held-plate prediction scoring with exact well coverage, AUROC, calibration, blocked inference and paired batch uncertainty. Authentic v2 population and v1 equivalence, archived-code parity, train-only native representations, matched model comparisons and protected references remain held. Cross-line transfer and biological effect estimation are unimplemented; scientific qualification is unknown. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Original figure4 v1](implementations/original-figure4-v1) — Reviewed source component.
  Scope: Original Figure 4 folds and AUROC. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

No public HTTP(S) citation was extracted for this catalog entry. Consult the authoritative specification and its provenance.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
