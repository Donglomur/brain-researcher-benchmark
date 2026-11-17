# Non-invasive decoding of typed sentences from human brain activity

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-ROOT-ADD-002`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** source\_unresolved. The original V1 sentence-decoding task is ordered, but the registered neural-only export has no recovered matching published numeric baseline. The headline MEG CER of 29% includes the language model. Current source defaults also differ from the paper training recipe and split description; a successful local transcript score cannot establish a same-task win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 110197 bytes; SHA-256 `d3bb8832202da3d4c29ad130505b8a92aa57968fabfcc7fc29fbeec535b7ff10`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [V1 presented-sentence evaluation and source admission](docs/v1-transcript-evaluation-v1.md)

## Implementation artifacts

- [V1 transcript evaluation v1](implementations/v1-transcript-evaluation-v1) — Calibration only.
  Scope: Offline evaluation of the complete declared V1 presented-sentence panel, with source per-keystroke scoring and separately labeled prospective transcript conditions. No native decoder, authenticated cohort/transcript/keystroke universe, cross-label biological equivalence, competent reference, paper headline reproduction, protected execution or scientific qualification is established. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/facebookresearch/brain2qwerty)
- [Paper](https://www.nature.com/articles/s41593-026-02303-2)
- [Source](https://huggingface.co/datasets/bcbl190626/SpanishBCBL)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
