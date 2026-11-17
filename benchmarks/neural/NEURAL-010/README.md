# Seizure false alarms and montage confounding

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-010`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Held-person differences in event F1, sensitivity and false alarms per observed day for frozen EEG, matched no-EEG, montage-only and fixed signal-reference streams; null or inconclusive contrasts are valid answers.

**Source delivery:** target\_mismatch. The delivered analyst grade measures reconstruction of an answer-bearing event/annotation table. Its detector-generation programme source and montage reports are useful construction components, but a zero reconstruction error does not establish neural evidence interpretation or better seizure detection.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | A no-tools analyst may interpret an operator-produced numerical evidence display, but current complete table copying does not test a withheld scientific answer. Only the declared observation/demonstration context, no external tools or evaluator feedback; a new direct condition needs an independently frozen view and complete output identity. | No delivered participant condition establishes this mode for the same scientific target. |
| Typed viewer | not\_delivered | Viewing EEG false-alarm windows could support localization review, but an image cannot by itself establish a whole-cohort matched contrast; no typed transport is delivered. Only typed render/navigation actions with audited limits; no raw arrays, labels, filenames or external source retrieval returned to the participant. | No delivered participant condition establishes this mode for the same scientific target. |
| Tool assisted | not\_delivered | Source analyst phases permit case-adaptive numerical reconstruction over released tables; this is source availability for calibration, with target-withholding investigation absent. Same permitted observations, frozen checkpoint tools and accounted compute as the compared arm; case state and feedback policy must be fixed before query. | The inspected source supports reconstruction or fixed-reference computation; a participant condition for the revised withheld scientific target is not delivered. |
| Frozen program | not\_delivered | Source precommits analyst code and detector-generation graph; currently scored analyst output is reconstruction, not a qualified frozen EEG detector outcome. Freeze code and fitting/adaptation recipe before queries; admit only explicitly allowed labels/calibration, retain all failed/incomplete cases. | The inspected source supports reconstruction or fixed-reference computation; a participant condition for the revised withheld scientific target is not delivered. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 18882 bytes; SHA-256 `82f23b594faed50480d2eb3c42f0321e0dd5aab7b5017fa4e292044d05ef5bd9`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Implementation artifacts

- [Programme source](implementations/programme-source) — Task implementation.
  Scope: Keep mixed current/source-predecessor/context members together; this map does not select a new operative version or qualify execution.

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
