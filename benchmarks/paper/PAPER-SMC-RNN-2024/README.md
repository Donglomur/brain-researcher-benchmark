# SMC-RNN: same-task improvement on the complete MC\_Maze 20-ms panel

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-SMC-RNN-2024`
- **Track:** Paper research
- **Registration:** Expansion draft
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The complete original endpoint, author code/checkpoints and original scorer are recovered. Source preparation and qualification have executable routes; no full author score match, candidate superiority or final admission policy is established.

- [Source-grounded improvement contract](improvement.v1.json)
- [Initial source-paper task registration (no predecessor)](../../../docs/provenance/registrations/paper-initial/PAPER-SMC-RNN-2024.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Recorded public evidence

Each record keeps the scope of its original report. It is not current runtime qualification.

- [Author model inference probe](docs/native-cost-characterization.json): Actual selected author-checkpoint inference on the first train and eval chunks only; no complete predictions, scores or 32-repeat baseline.
- [Author model inference probe](docs/native-cost-characterization.json): Actual selected author-checkpoint inference on the first train and eval chunks only; no complete predictions, scores or 32-repeat baseline.
- [Paper source preparation](docs/source-preparation-evidence.json): Complete original MC\_Maze 20ms input preparation and paired participant materials, with generated source/scorer controls. This report excludes separately recorded author-model timing and all scientific performance evaluation.

Inspect conditions, metrics and limits with `python3 scripts/neurobench.py evidence PAPER-SMC-RNN-2024`. Programme evidence does not establish direct interpretation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 6174 bytes; SHA-256 `5380450592ce4f379a0ecbd9d2da33d2ca8a3a5900a7b3ab5d5a8570ab015824`.
- [Registration and provenance](../../../docs/provenance/registrations/paper-initial/PAPER-SMC-RNN-2024.json)

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Original two-arm scientific comparison and scope](docs/scientific-contract.json)
- [Source preparation and paired-export engineering evidence](docs/source-preparation-evidence.json)
- [Partial native execution and full-run cost estimates](docs/native-cost-characterization.json)

## Implementation artifacts

- [Source matched nlb v1](implementations/source-matched-nlb-v1) — Original panel preparation, paired materials and frozen prediction scoring.
  Scope: Source-matched MC\_Maze 20-ms preparation and paired paper/data versus paper/data/official-code exports, selected author-checkpoint inference and frozen-prediction scoring for both original proposal arms with all companion metrics. Complete author-score calibration, equal participant budgets, joint superiority admission and scientific qualification remain unestablished. Source delivery and engineering controls are not solver performance; original targets are publicly exposed.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/mackelab/smc_rnns)
- [Paper](https://papers.neurips.cc/paper_files/paper/2024/file/209423f076b6479ab3a4f45886e30306-Paper-Conference.pdf)
- [Source](https://doi.org/10.48324/dandi.000128/0.220113.0400)
- [Source](https://github.com/mackelab/smc_rnns)
- [Source](https://papers.neurips.cc/paper_files/paper/2024/file/209423f076b6479ab3a4f45886e30306-Paper-Conference.pdf)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
