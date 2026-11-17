# NeuroPictor: Refining fMRI-to-Image Reconstruction via Multi-individual Pretraining and Multi-level Modulation

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-043`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 39845 bytes; SHA-256 `02f3c335df986b9276f0026fff9ffcd1d16a410be55372299a19ca93e87468af`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prepared-tensor arithmetic panel for eight reconstruction metrics with identity-bound pretrained, target-only and neural-free comparisons; SSIM is explicitly a prospective 2D endpoint. NeuroPictor training, diffusion inference, resizing and feature extraction are not implemented. Authentic 982-stimulus/session membership, checkpoint/pretraining ancestry, native metric parity, NSD/COCO/UKB/model rights, primary grading policy, reference competence, protected evaluation and full-population resources remain unresolved.

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
