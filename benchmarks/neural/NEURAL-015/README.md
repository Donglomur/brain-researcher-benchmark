# Word-boundary localization from intracranial activity

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-015`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Whether each fixed grid sample lies within the frozen inclusive tolerance of any manually annotated word start; offsets and sentence-only onsets are different targets.

**Source delivery:** partial\_delivery. A complete26-record fixed-grid word-start evaluator is delivered; its query exporter carries only grid metadata, not neural payloads. Authentic waveform alignment, competent acoustic/visual references and protected participant execution are still absent.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Direct numeric or plotted intracranial windows could elicit word-start probabilities under a fixed contextual view, but no observation packets are supplied. Only the declared observation/demonstration context, no external tools or evaluator feedback; a new direct condition needs an independently frozen view and complete output identity. | No delivered participant condition establishes this mode for the same scientific target. |
| Typed viewer | not\_delivered | Typed signal viewing is scientifically possible for the same fixed-grid target; no image transport or viewer-qualified response collection is delivered. Only typed render/navigation actions with audited limits; no raw arrays, labels, filenames or external source retrieval returned to the participant. | No delivered participant condition establishes this mode for the same scientific target. |
| Tool assisted | not\_delivered | The evaluator/clock converter are operator tools; a participant investigator with actual neural arrays and fixed resource budget is not delivered. Same permitted observations, frozen checkpoint tools and accounted compute as the compared arm; case state and feedback policy must be fixed before query. | No delivered participant condition establishes this mode for the same scientific target. |
| Frozen program | not\_delivered | A frozen decoder can target the strict output schema, but the package is scoring/preparation source without a fit/predict runner or authentic signal reference. Freeze code and fitting/adaptation recipe before queries; admit only explicitly allowed labels/calibration, retain all failed/incomplete cases. | No delivered participant condition establishes this mode for the same scientific target. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 32214 bytes; SHA-256 `c95fe101fd898a4ed44740627c073934f310ac0548b2fcbb0642a92c344e2ecb`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prospective full-cohort word-onset fixed-grid scoring with source-informed trigger alignment, participant summaries and an operator-provided acoustic/visual comparison interface. Authentic HDF5/cohort alignment, frozen grid and tolerance policy, competent signal-derived references, code/media rights and protected execution remain held. Generated controls establish construction behavior only; scientific qualification is unknown.
- [Transcript preparation v1](implementations/transcript-preparation-v1) — Reviewed source component.
  Scope: Complete-row private word-start preparation. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://arxiv.org/abs/2411.08343)
- [Source](https://braintreebank.dev/)
- [Source](https://braintreebank.dev/data/quickstart.ipynb)
- [Source](https://braintreebank.dev/data/subject_metadata.zip)
- [Source](https://braintreebank.dev/data/subject_timings.zip)
- [Source](https://braintreebank.dev/data/transcripts.zip)
- [Source](https://github.com/czlwang/brain_treebank_code_release)
- [Source](https://proceedings.nips.cc/paper_files/paper/2024/hash/aefa2385b3f33abf1526ae4e2c208cd9-Abstract-Datasets_and_Benchmarks_Track.html)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
