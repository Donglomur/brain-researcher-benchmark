# Adult clinical seizure-event detection

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-011`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Siena recording-relative seizure intervals after explicit reconciliation of source clock annotations and native EDF start clocks.

**Source delivery:** partial\_delivery. A within-Siena event evaluator, causal line-length and timing references are delivered as construction source. Selected complete-patient support is checked, but source authentication and full-cohort qualification are not established; CHB-to-Siena transfer belongs to NEURAL-012.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Complete continuous EEG could be interpreted directly with calibrated displays, but no no-tools full-record protocol is delivered. Only the declared observation/demonstration context, no external tools or evaluator feedback; a new direct condition needs an independently frozen view and complete output identity. | No delivered participant condition establishes this mode for the same scientific target. |
| Typed viewer | not\_delivered | Typed multichannel viewing would be suitable for interval annotation; no Siena image transport is delivered. Only typed render/navigation actions with audited limits; no raw arrays, labels, filenames or external source retrieval returned to the participant. | No delivered participant condition establishes this mode for the same scientific target. |
| Tool assisted | not\_delivered | The evaluator and fit/predict commands are analysis tools; an interactive case-level investigator protocol and target-withholding broker are not delivered. Same permitted observations, frozen checkpoint tools and accounted compute as the compared arm; case state and feedback policy must be fixed before query. | No delivered participant condition establishes this mode for the same scientific target. |
| Frozen program | not\_delivered | reference.py supplies preselected fit/predict implementations for line-length and timing arms; a protected arbitrary-candidate runner and authentic source packet are absent. Freeze code and fitting/adaptation recipe before queries; admit only explicitly allowed labels/calibration, retain all failed/incomplete cases. | The inspected source supports reconstruction or fixed-reference computation; a participant condition for the revised withheld scientific target is not delivered. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 18134 bytes; SHA-256 `93deb7919ee477e0e46c62bcba6cf0390fd27d6577563cc9063fe07a3798f46c`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Complete selected-patient Siena recording evaluation: pinned event matching, clock-annotation normalization, patient-macro F1/sensitivity/false alarms per 24 hours, train-only causal EEG line-length and timing references, and paired patient uncertainty. Authentic EDF/header equality, complete patient protocol and montage, signal-reference competence, rights, isolated protected evaluation and scientific admission remain held; the CHB-training to Siena-confirmation branch is not implemented.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://doi.org/10.3390/pr8070846)
- [Source](https://github.com/esl-epfl/epilepsy2bids)
- [Source](https://physionet.org/content/siena-scalp-eeg/1.0.0/)
- [Source](https://physionet.org/files/siena-scalp-eeg/1.0.0/PN00/PN00-1.edf)
- [Source](https://physionet.org/files/siena-scalp-eeg/1.0.0/PN00/Seizures-list-PN00.txt)
- [Source](https://physionet.org/files/siena-scalp-eeg/1.0.0/RECORDS)
- [Source](https://physionet.org/files/siena-scalp-eeg/1.0.0/SHA256SUMS.txt)
- [Source](https://physionet.org/files/siena-scalp-eeg/1.0.0/subject_info.csv)
- [Source](https://raw.githubusercontent.com/esl-epfl/epilepsy2bids/d3fb17526b8a483e292ae9ba2e51b02d5f9128ff/src/epilepsy2bids/bids/siena/convert2bids.py)
- [Source](https://raw.githubusercontent.com/esl-epfl/epilepsy2bids/d3fb17526b8a483e292ae9ba2e51b02d5f9128ff/src/epilepsy2bids/load_annotations/siena.py)
- [Source](https://raw.githubusercontent.com/esl-epfl/sz-validation-framework/aba5accc45598156cb178cf48a3203639bc23ff8/3-runSzDetection/docker-szDetection/algo/src/algo/sz_detection.py)
- [Source](https://raw.githubusercontent.com/esl-epfl/timescoring/426f8d2b77974641dc9db71884e0812b249ba93b/src/timescoring/scoring.py)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
