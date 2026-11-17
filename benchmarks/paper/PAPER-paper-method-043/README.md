# NeuroPictor: Refining fMRI-to-Image Reconstruction via Multi-individual Pretraining and Multi-level Modulation

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-043`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. The original fMRI-to-image prediction task, Table 1 scores and Inception identification formula are recovered, but the complete eight-metric source panel remains unresolved because historical SSIM environment and grayscale multichannel semantics are unqualified. The paper specifies no single primary endpoint; selecting Inception alone cannot establish full source metric recovery. Preserve its verified published 0.945 component, all four subjects and all eight metrics while resolving metric parity, image membership, checkpoint lineage and the full-panel decision before design admission.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 39706 bytes; SHA-256 `e557a3e84e2d14a320db7f17935e95fd9f00bfebf548fb5658ff4beeecde005b`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prepared-tensor arithmetic panel for eight reconstruction metrics with identity-bound pretrained, target-only and neural-free comparisons; SSIM is explicitly a prospective 2D endpoint. NeuroPictor training, diffusion inference, resizing and feature extraction are not implemented. Authentic 982-stimulus/session membership, checkpoint/pretraining ancestry, native metric parity, NSD/COCO/UKB/model rights, primary grading policy, reference competence, protected evaluation and full-population resources remain unresolved. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

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
