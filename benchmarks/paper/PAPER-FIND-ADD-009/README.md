# An instantaneous voice-synthesis neuroprosthesis

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-ADD-009`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** design\_ready. The final paper has an ordered causal neural-to-voice acoustic endpoint and the author release includes session-specific decoders. A same-task design is identifiable, but the original evaluation/session training manifest, matched evaluator, uncertainty rule and budgets are not qualified. The day195 offline demonstration and control-only archive cannot be substituted for the paper evaluation, and offline replay cannot establish improved closed-loop communication. The canonical scope also includes original control trials and cross-session generalization; Fig. 2b correlation alone is insufficient for a whole-registration win until the complete scope rule is bound.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 20801 bytes; SHA-256 `1a99d7f26e7e78fa28d49217a7e83355f477876f9bbfdce1a81510ddcf97bd06`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Feature-level speech evaluation using speech-only DTW-aligned Pearson correlation across 40 Mel bands and paired-sentence WER/PER summarized across seven listeners, with declared trial/session coverage and exposure checks. Native frontend/DTW/tokenization parity, authentic trial membership, decoder training, waveform generation, original ten-fold controls and protected references remain held. No clinical or whole-paper result is established; scientific qualification is unknown. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Source chronology v1](implementations/source-chronology-v1) — Reviewed source component.
  Scope: Published decoder chronology recovery. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/Neuroprosthetics-Lab/brain-to-voice-2025)
- [Paper](https://www.nature.com/articles/s41586-025-09127-3)
- [Source](https://datadryad.org/dataset/doi:10.5061/dryad.2280gb64f)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
