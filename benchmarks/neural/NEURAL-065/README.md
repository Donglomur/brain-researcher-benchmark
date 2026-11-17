# Neural typing character reconstruction

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-065`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 11607 bytes; SHA-256 `1888547c763c67793b92ae4d1602c51917aa9d898755291e421ed545a54f7c47`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: V1 typed-button transcript evaluation with alias/session/template checks, sentence CER averaged within people and then across people, required neural-only and language-only arms, and paired person uncertainty. Typed-button targets differ from the paper intended-key endpoint. Authentic DTW/session mapping, cross-modality identity, decoder/checkpoint parity and protected execution remain held; V2 is excluded and scientific qualification is unknown.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://github.com/facebookresearch/brain2qwerty)
- [Source](https://huggingface.co/api/datasets/bcbl190626/SpanishBCBL)
- [Source](https://huggingface.co/datasets/bcbl190626/SpanishBCBL)
- [Source](https://raw.githubusercontent.com/facebookresearch/brain2qwerty/5f9889621d0df391c5aab37c996683d308e6e926/LICENSE)
- [Source](https://raw.githubusercontent.com/facebookresearch/brain2qwerty/5f9889621d0df391c5aab37c996683d308e6e926/studies/spanishbcbl.py)
- [Source](https://www.nature.com/articles/s41593-026-02303-2)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
