# Know Thyself by Knowing Others: Learning Neuron Identity from Population Context

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-012`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
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
| Improvement | Paper data | design\_ready | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | design\_ready | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The original conference paper supplies ordered macro-F1 targets for nine distinct Bugeon label/exposure panels, and pinned author code defines their readout and split regimes. A complete original panel may support a predeclared, precisely scoped paper comparison. Exact paper-era artifact equivalence, native reference execution, meaningful-effect/uncertainty policy and concrete budgets remain unresolved, so this is a source-grounded design rather than an admitted task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 31596 bytes; SHA-256 `cde7612e71a6133fc3d660b2800d9e4c71ede1a687eec81c611918d323ae8ab8`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Runs an owner-side NuCLR Bugeon linear readout on supplied embeddings with train-only scaling, validation-only checkpoint selection, exact label families, three distinct split/exposure panels and matched context-ablation diagnostics. Authentic joins/splits, paper-era versus December 2025 equivalence, repeated-cell linkage, native references, optional resampling dependency, rights, protected execution and scientific qualification remain unresolved. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Native inputs v1](implementations/native-inputs-v1) — Reviewed source component.
  Scope: Complete original ZIP/member authentication and17-session/69-subrecording native activity/identity bridge preserve all nine original label/exposure projections under the explicitly adopted current-release order. The existing ninth E/I-inductive source selector still refuses; transductive balancing and historical order remain unresolved. Authentic preparation, native reference comparisons and protected participant execution are not conferred by generated source controls.
- [Source splits v2](implementations/source-splits-v2) — Reviewed source component.
  Scope: Original Bugeon split recovery. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/nerdslab/nuclr)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/configs/data/bugeon_inductive.yaml)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/configs/data/bugeon_transductive.yaml)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/eval_scripts/multi_split_eval.py)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/eval_scripts/single_split_eval.py)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/preprocess/bugeon/download.py)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/preprocess/bugeon/experiments.txt)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/preprocess/bugeon/prepare_data.py)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/src/evaluators/bugeon.py)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/train.py)
- [Source](https://figshare.com/articles/dataset/19448531)
- [Source](https://ik.imagekit.io/7tkfmw7hc/nuclr/splits.zip)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
