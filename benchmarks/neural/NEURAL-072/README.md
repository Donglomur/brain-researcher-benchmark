# Contextual linguistic information beyond acoustics

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-072`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Signed contextual-minus-fixed-lexical and fixed-lexical-minus-fixed-nuisance prediction contrasts recomputed from candidate contextual predictions, independently fitted evaluator-owned comparator predictions, and measured held-story BOLD; zero or adverse contrasts are valid answers. Current source does not enforce comparator ownership.

**Source delivery:** partial\_delivery. A prospective matrix encoder and independent arithmetic contrast scorer exist, but scoring accepts participant-supplied nuisance, lexical and contextual predictions without authenticating their fit provenance. A participant can inflate the contextual-minus-lexical effect by degrading its lexical predictions. The contrast is unusable for participant ranking until evaluator-owned fixed lexical/nuisance predictions are authenticated; authentic NEURAL-071 case equality and native extraction also remain unresolved.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_suitable | Current answer is a complete held-out incremental-prediction calculation, not a single waveform/map label. Giving a precomputed effect plot would test interpretation of that plot rather than the registered numerical investigation. |  |
| Typed viewer | not\_suitable | No viewer can replace the required full prediction/variance calculation without a separate observation-interpretation endpoint. Do not expose hidden BOLD through plots to the candidate. |  |
| Tool assisted | not\_delivered | The delivered source fits fixed matrix encoders and scores complete prediction arrays; it has no participant-facing per-case investigation actor, controller or tool transport. Candidate supplies contextual predictions only for the revised comparison; evaluator separately supplies authenticated fixed lexical/nuisance references. Freeze cases and outputs before protected targets; no scorer feedback. This comparator boundary is required but not enforced by current source. | Evaluator-owned authenticated comparator enforcement; current all-three-supplied-array scoring is gameable.; Participant transport/runtime and authentic data binding |
| Frozen program | source\_available | Fixed train/dev/test matrix encoder and scorer entrypoints. Fit candidate transformations on training only, tune on development, freeze before test targets; comparator predictions must come from independently frozen evaluator-owned encoders. Current scorer does not verify that ownership or fit ledger. | Evaluator-owned authenticated comparator enforcement before primary ranking.; Native adapter, exact071 equivalence and protected execution |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 19957 bytes; SHA-256 `43e9aa2dbea680680033048858e540271e691b0412fb13e22d0a5cb7e89e1e62`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prospective within-listener nuisance, lexical and contextual matrix encoders and independent held-story variance-contrast scoring, with train-only transformations, matched effective capacity, story-family checks, crossed uncertainty and an alignment diagnostic. Authentic NEURAL-071 case equality, full Narratives population, scan/transcript/HRF timing, atlas and checkpoint lineage, competent reference, rights, protected execution and resource admission remain open. The null diagnostic is not a calibrated significance test.
- [Fixed comparator v2](implementations/fixed-comparator-v2) — Reviewed source component.
  Scope: Fixed comparator scoring for NEURAL-072. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://github.com/snastase/narratives)
- [Source](https://openneuro.org/datasets/ds002345)
- [Source](https://www.nature.com/articles/s41597-021-01033-3)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
