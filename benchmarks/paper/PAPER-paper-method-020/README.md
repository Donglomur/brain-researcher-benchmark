# Neuro-Symbolic Decoding of Neural Activity

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-020`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

- [Original-finding reproduction contract](reproduction.v1.json)
- [Paired outcome protocols](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. Table 1 CSI1 overall accuracy 0.7041 is a verified numeric anchor, but the publication-identical evaluated query denominator, checkpoint selection and source scoring identity remain unresolved. Author test-based selection and query skipping differ from the local exhaustive train-only evaluator; that extension cannot be used to claim a source-paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 2231805 bytes; SHA-256 `ebae859633ceb9029849a9e70b487bc3d9d536a1d03a009c4f192a31aee27eac`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Audits the complete CSI1 BOLD5000-QA inventory and image/person aliases, projects separate neural/zero/shuffled inference packets, and scores every declared structured QA answer. Native NPY conversion, actual stimulus identity, question-text leakage, genuine model provenance, protected runtime, source test-informed selection differences, broader person/stimulus independence, independently trained text-only baseline and scientific qualification remain open. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Six cell suite v1](implementations/six-cell-suite-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Source scoring v2](implementations/source-scoring-v2) — Reviewed source component.
  Scope: NEURONA source scoring paths. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/PPWangyc/neurona)
- [Code](https://github.com/PPWangyc/neurona/blob/8071fb42c3ddac0355f2c0b5977baa32e33f6e14/scripts/download_data.sh)
- [Code](https://github.com/PPWangyc/neurona/blob/8071fb42c3ddac0355f2c0b5977baa32e33f6e14/scripts/train_bold5000.sh)
- [Code](https://github.com/PPWangyc/neurona/blob/8071fb42c3ddac0355f2c0b5977baa32e33f6e14/src/loader/fqa.py)
- [Code](https://github.com/PPWangyc/neurona/blob/8071fb42c3ddac0355f2c0b5977baa32e33f6e14/src/train_bold5000.py)
- [Code](https://huggingface.co/datasets/PPWangyc/BOLD5000-QA)
- [Code](https://proceedings.iclr.cc/paper_files/paper/2026/hash/33c069ac8440595724bcc373c9a52852-Abstract-Conference.html)
- [Code](https://raw.githubusercontent.com/PPWangyc/neurona/8071fb42c3ddac0355f2c0b5977baa32e33f6e14/LICENSE)
- [Code](https://raw.githubusercontent.com/PPWangyc/neurona/8071fb42c3ddac0355f2c0b5977baa32e33f6e14/README.md)
- [Paper](https://proceedings.iclr.cc/paper_files/paper/2026/hash/33c069ac8440595724bcc373c9a52852-Abstract-Conference.html)
- [Source](https://huggingface.co/api/datasets/PPWangyc/BOLD5000-QA)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
