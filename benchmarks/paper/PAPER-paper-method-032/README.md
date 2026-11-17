# MindEye2: Shared-Subject Models Enable fMRI-To-Image With 1 Hour of Data

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-032`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 185659 bytes; SHA-256 `be0baca5eebb4c64fa0d6096fdbd9df12aa16e4abf9342c6d16ab0aa433ac9ff`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Scores identity-bound MindEye2 retrieval embeddings with corrected image/brain directions and 30 frozen 300-candidate pools, plus reconstruction feature kernels, post-model repeat averaging and exposure-ledger audits. Complete native adaptation/reconstruction, authentic four-subject/trial identities, paper/notebook orientation and historical RNG parity, checkpoint/image exposure, rights and protected scientific qualification remain unresolved.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://arxiv.org/abs/2403.11207)
- [Code](https://github.com/MedARC-AI/MindEyeV2)
- [Code](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/Train.ipynb)
- [Code](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/final_evaluations.ipynb)
- [Code](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/recon_inference.ipynb)
- [Code](https://github.com/MedARC-AI/MindEyeV2/blob/76a2609243ba1bacb450e47e3dc78de1f78a9c00/src/setup.sh)
- [Code](https://huggingface.co/datasets/pscotti/mindeyev2)
- [Code](https://proceedings.mlr.press/v235/scotti24a.html)
- [Code](https://raw.githubusercontent.com/MedARC-AI/MindEyeV2/76a2609243ba1bacb450e47e3dc78de1f78a9c00/LICENSE)
- [Code](https://raw.githubusercontent.com/MedARC-AI/MindEyeV2/76a2609243ba1bacb450e47e3dc78de1f78a9c00/README.md)
- [Paper](https://proceedings.mlr.press/v235/scotti24a.html)
- [Source](https://huggingface.co/api/datasets/pscotti/mindeyev2)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
