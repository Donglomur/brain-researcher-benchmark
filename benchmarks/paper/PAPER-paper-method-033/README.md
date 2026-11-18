# MindBridge: A Cross-Subject Brain Decoding Framework

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-033`
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
| Reproduction | Paper data | design\_ready | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | design\_ready | unresolved | unresolved | Unknown |
| Improvement | Paper data | design\_ready | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | design\_ready | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The original subject-7 adaptation task has ordered reconstruction endpoints and recoverable published comparisons at all three source calibration budgets. Its target-aware best-of-eight reconstruction selection differs scientifically from the existing fixed-index evaluator, which cannot establish a source-paper win. Exact adaptation subset identities, exposure manifests, competent author replay, meaningful effect, uncertainty and execution budgets remain unqualified.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 127883 bytes; SHA-256 `e8b7e2388462c815d822af46db0232971a158b28a16742bb3349e5e6c80807ed`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)
- [Current source selection and remaining qualification (2026-11-18)](docs/source-selection-status-20261118.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prospective fixed-target MindBridge feature evaluator with source Pearson identification/correlation metrics, explicit paired calibration budgets, exposure/image/session declarations and neural controls. Target, primary metric and budget policy remain unfrozen; actual feature extraction/generation, NSD/weight/pretraining provenance, receipt authentication, protected replay, rights and scientific qualification remain held. Fixed candidate selection deliberately differs from the paper’s target-aware best-of-eight selection, so published-score reproduction is not claimed. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Original panel v1](implementations/original-panel-v1) — Reviewed source component.
  Scope: Implemented original Table 2 scoring and offline metric transforms for Vanilla and MindBridge at 500, 1,500, and 4,000 calibration images: six conditions, all 48 findings and the complete gallery of 982 stimulus images. For target subject 7, source-protocol-v2 chooses one target-aware hidden-token winner among eight reconstruction candidates per stimulus for all eight metrics; fixed-index scoring remains separate calibration. Current source availability supersedes earlier missing-scorer wording only. Authentic inputs/weights, protected generation freeze, historical SSIM/SwAV identity, native parity, competent reference and scientific acceptance remain unqualified.
- [Original method invocation v1](implementations/original-method-invocation-v1) — Reviewed source component.
  Scope: Offline invocation builder connects six target7 conditions to explicit checkpoint roles and existing source interfaces without opening weights/data or executing code. Only the recovered reset4000 training command is emitted; other historical launch recipes remain unresolved. Original target-aware reconstruction and separate eight-draw high-level transport remain distinct, with checkpoint/exposure/caption/runtime lineage and reproduction/improvement unqualified.
- [Selection features v1](implementations/selection-features-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Target7 composition v1](implementations/target7-composition-v1) — Reviewed source component.
  Scope: Portable MindBridge target7 composition and operator-only support: original88-file/32-case input scope,982-image gallery, source1/2/5 and train-only budgets retained. No original archives, checkpoints, scientific reproduction or improvement qualification.
- [Target7 operator support v1](implementations/target7-operator-support-v1) — Reviewed source component.
  Scope: Portable MindBridge target7 composition and operator-only support: original88-file/32-case input scope,982-image gallery, source1/2/5 and train-only budgets retained. No original archives, checkpoints, scientific reproduction or improvement qualification.
- [Source protocol v2](implementations/source-protocol-v2) — Reviewed source component.
  Scope: Implemented source calibration and target-aware selection of eight reconstruction candidates per stimulus, preserving target subject 7, source subjects 1, 2, and 5, and train-only budgets of 500, 1,500, and 4,000 images. One common selected reconstruction supplies every final metric through original-panel-v1. Earlier contract wording that source-protocol scoring must be implemented is superseded only as a source-availability statement; native execution, authentic memberships/features/weights, protected target access and scientific qualification remain unestablished.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/littlepure2333/MindBridge)
- [Code](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/scripts/adapt_bridge.sh)
- [Code](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/scripts/inference.sh)
- [Code](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/scripts/train_bridge.sh)
- [Code](https://github.com/littlepure2333/MindBridge/blob/2a3943ff5b619db6f85f16a5e7ff1331d25def55/scripts/train_single.sh)
- [Code](https://huggingface.co/datasets/pscotti/naturalscenesdataset/tree/main/webdataset_avg_split)
- [Code](https://littlepure2333.github.io/MindBridge)
- [Code](https://littlepure2333.github.io/MindBridge/)
- [Code](https://openaccess.thecvf.com/content/CVPR2024/html/Wang_MindBridge_A_Cross-Subject_Brain_Decoding_Framework_CVPR_2024_paper.html)
- [Code](https://raw.githubusercontent.com/littlepure2333/MindBridge/2a3943ff5b619db6f85f16a5e7ff1331d25def55/README.md)
- [Paper](https://openaccess.thecvf.com/content/CVPR2024/html/Wang_MindBridge_A_Cross-Subject_Brain_Decoding_Framework_CVPR_2024_paper.html)
- [Source](https://huggingface.co/api/datasets/pscotti/naturalscenesdataset)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
