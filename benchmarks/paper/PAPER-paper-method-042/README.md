# UMBRAE: Unified Multimodal Brain Decoding

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-042`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 128221 bytes; SHA-256 `a136bac3f4f192ace492257181f68638b4f8c73a4f7e0e4d7793756b3215e455`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prospective BrainHub referring-expression grounding scoring with per-subject All-category accuracy at strict IoU greater than 0.5, secondary salience summaries, paired controls and shared-image uncertainty. Authentic annotation/order membership, model/reference execution, actual exposure and intervention fidelity, rights and protected isolation remain held. Captioning, transfer and subject adaptation are outside this component; scientific qualification is unknown.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2404.07202)
- [Code](https://github.com/weihaox/UMBRAE)
- [Code](https://github.com/weihaox/UMBRAE/blob/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/download_data.sh)
- [Code](https://github.com/weihaox/UMBRAE/blob/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/inference.py)
- [Code](https://github.com/weihaox/UMBRAE/blob/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/train.py)
- [Code](https://github.com/weihaox/UMBRAE/blob/8c1795c434a41cdd38ce6628b7e1a774f31d9483/umbrae/train_brainx.py)
- [Code](https://huggingface.co/datasets/pscotti/naturalscenesdataset/tree/main/webdataset_avg_split)
- [Code](https://raw.githubusercontent.com/weihaox/UMBRAE/8c1795c434a41cdd38ce6628b7e1a774f31d9483/LICENSE.txt)
- [Code](https://raw.githubusercontent.com/weihaox/UMBRAE/8c1795c434a41cdd38ce6628b7e1a774f31d9483/README.md)
- [Code](https://raw.githubusercontent.com/weihaox/UMBRAE/main/umbrae/download_data.sh)
- [Code](https://weihaox.github.io/UMBRAE)
- [Paper](https://arxiv.org/abs/2404.07202)
- [Source](https://huggingface.co/api/datasets/pscotti/naturalscenesdataset)
- [Source](https://huggingface.co/datasets/weihaox/brainx/resolve/main/all_images.pt)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
