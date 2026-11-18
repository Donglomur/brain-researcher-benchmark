# NeuroPictor: Refining fMRI-to-Image Reconstruction via Multi-individual Pretraining and Multi-level Modulation

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-043`
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

**Disposition:** source\_unresolved. The original fMRI-to-image prediction task, Table 1 scores and Inception identification formula are recovered, but the complete eight-metric source panel remains unresolved because historical SSIM environment and grayscale multichannel semantics are unqualified. The paper specifies no single primary endpoint; selecting Inception alone cannot establish full source metric recovery. Preserve its verified published 0.945 component, all four subjects and all eight metrics while resolving metric parity, image membership, checkpoint lineage and the full-panel decision before design admission.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 39620 bytes; SHA-256 `b2f45fd4ef34b78eaf1705547e56bf5941348a573423a77b6667a02719777eb5`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prepared-tensor arithmetic panel for eight reconstruction metrics with identity-bound pretrained, target-only and neural-free comparisons; SSIM is explicitly a prospective 2D endpoint. NeuroPictor training, diffusion inference, resizing and feature extraction are not implemented. Authentic 982-stimulus/session membership, checkpoint/pretraining ancestry, native metric parity, NSD/COCO/UKB/model rights, primary grading policy, reference competence, protected evaluation and full-population resources remain unresolved. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Ssim semantics probe v1](implementations/ssim-semantics-probe-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Bounded panel v2](implementations/bounded-panel-v2) — Reviewed source component.
  Scope: NeuroPictor bounded prepared-panel scoring. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2403.18211)
- [Code](https://github.com/jingyanghuo/neuropictor)
- [Code](https://github.com/jingyanghuo/neuropictor/blob/b676b5be320ebb1b12919afd4cf6152e2c45db5d/dataset/dataset.py)
- [Code](https://github.com/jingyanghuo/neuropictor/blob/b676b5be320ebb1b12919afd4cf6152e2c45db5d/eval_metrics.py)
- [Code](https://github.com/jingyanghuo/neuropictor/blob/b676b5be320ebb1b12919afd4cf6152e2c45db5d/reconstruction.py)
- [Code](https://github.com/jingyanghuo/neuropictor/blob/b676b5be320ebb1b12919afd4cf6152e2c45db5d/train.py)
- [Code](https://huggingface.co/Fudan-fMRI/neuropictor/tree/main/NSD)
- [Code](https://raw.githubusercontent.com/jingyanghuo/neuropictor/b676b5be320ebb1b12919afd4cf6152e2c45db5d/README.md)
- [Code](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/06746.pdf)
- [Paper](https://www.ecva.net/papers/eccv_2024/papers_ECCV/papers/06746.pdf)
- [Source](https://huggingface.co/api/models/Fudan-fMRI/neuropictor)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
