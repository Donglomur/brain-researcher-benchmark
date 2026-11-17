# Pediatric continuous seizure-event detection

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-009`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Recording-relative annotated seizure intervals, with separate raw annotations and processed intervals under the frozen timescoring merge/split/tolerance policy.

**Source delivery:** partial\_delivery. The complete 686-record/23-person normalized event evaluator is delivered. Authentic EEG preparation and a competent signal reference are not qualified; the implemented tolerant event score cannot establish prompt onset detection.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Rendered continuous EEG windows with fixed scales and declared surrounding causal context could support event annotation, but a complete-record no-tools response protocol is absent. Only the declared observation/demonstration context, no external tools or evaluator feedback; a new direct condition needs an independently frozen view and complete output identity. | No delivered participant condition establishes this mode for the same scientific target. |
| Typed viewer | not\_delivered | A multichannel EEG viewer with bounded navigation is scientifically suitable for annotation; no typed viewer is delivered for this task. Only typed render/navigation actions with audited limits; no raw arrays, labels, filenames or external source retrieval returned to the participant. | No delivered participant condition establishes this mode for the same scientific target. |
| Tool assisted | not\_delivered | An investigator could analyze allowed EEG and submit complete probabilities, but this package delivers the evaluator rather than a case-investigation participant loop. Same permitted observations, frozen checkpoint tools and accounted compute as the compared arm; case state and feedback policy must be fixed before query. | No delivered participant condition establishes this mode for the same scientific target. |
| Frozen program | not\_delivered | A detector recipe can be frozen before outer fold access; the evaluator checks recipe declarations but supplies no protected fit/predict runner. Freeze code and fitting/adaptation recipe before queries; admit only explicitly allowed labels/calibration, retain all failed/incomplete cases. | No delivered participant condition establishes this mode for the same scientific target. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 17137 bytes; SHA-256 `92c3d8c1cb60682d363ab0f2303f1b8b8d259259e9956526c39fe71e2046ba31`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Complete-recording event evaluator and source requirements](docs/seizure-events-v1.md)

## Implementation artifacts

- [Seizure events v1](implementations/seizure-events-v1) — Task implementation.
  Scope: Complete normalized event evaluator over 686 recordings and 23 biological people with an explicit prospective policy and alias-safe leave-one-person-out support. Authentic signals, clocks, native normalization, competent EEG-derived references, patient-paired uncertainty, protected execution and scientific qualification remain unestablished; tolerant processed-event coverage is not original clinical event count or onset timeliness.
- [Seizure diagnostics v1](implementations/seizure-diagnostics-v1) — Reviewed source component.
  Scope: Seizure-event diagnostic supplement. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://github.com/esl-epfl/epilepsy2bids)
- [Source](https://physionet.org/content/chbmit/1.0.0/)
- [Source](https://physionet.org/files/chbmit/1.0.0/RECORDS)
- [Source](https://physionet.org/files/chbmit/1.0.0/SHA256SUMS.txt)
- [Source](https://physionet.org/files/chbmit/1.0.0/SUBJECT-INFO)
- [Source](https://physionet.org/files/chbmit/1.0.0/chb01/chb01-summary.txt)
- [Source](https://physionet.org/files/chbmit/1.0.0/chb01/chb01_03.edf)
- [Source](https://raw.githubusercontent.com/esl-epfl/epilepsy2bids/d3fb17526b8a483e292ae9ba2e51b02d5f9128ff/src/epilepsy2bids/bids/chbmit/convert2bids.py)
- [Source](https://raw.githubusercontent.com/esl-epfl/epilepsy2bids/d3fb17526b8a483e292ae9ba2e51b02d5f9128ff/src/epilepsy2bids/load_annotations/chbmit.py)
- [Source](https://raw.githubusercontent.com/esl-epfl/sz-validation-framework/aba5accc45598156cb178cf48a3203639bc23ff8/3-runSzDetection/docker-szDetection/algo/src/algo/sz_detection.py)
- [Source](https://raw.githubusercontent.com/esl-epfl/timescoring/426f8d2b77974641dc9db71884e0812b249ba93b/src/timescoring/scoring.py)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
