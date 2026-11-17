# Cross-cohort seizure robustness

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-012`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current neural-understanding objective

Siena equal-person event F1 and paired harmonized-minus-native, normalized-minus-harmonized and harmonized-minus-timing contrasts, with mandatory sensitivity and false alarms.

**Source delivery:** partial\_delivery. The source now separates frozen-detector performance from analyst reconstruction. Its four-arm full CHB/Siena programme is source-available, but authentic channel/clock adjudication and observed complete execution remain missing; report reconstruction alone cannot establish transfer.

- [Current target, controls and access conditions](understanding.v1.json)
- [Preserved historical task definition](historical/task.pre-understanding.v1.json)

| Condition | Source availability | Representation and boundary | Missing |
| --- | --- | --- | --- |
| Direct observation | not\_delivered | Whole-cohort transfer contrasts require complete quantitative evidence; a single EEG trace is not a suitable substitute. A direct numerical-summary condition is possible but not delivered with withheld answers. Only the declared observation/demonstration context, no external tools or evaluator feedback; a new direct condition needs an independently frozen view and complete output identity. | No delivered participant condition establishes this mode for the same scientific target. |
| Typed viewer | not\_delivered | Waveform viewing can assist montage/artifact inspection but does not replace the full transfer estimand; no typed viewer condition is supplied. Only typed render/navigation actions with audited limits; no raw arrays, labels, filenames or external source retrieval returned to the participant. | No delivered participant condition establishes this mode for the same scientific target. |
| Tool assisted | not\_delivered | Source analysis and reconstruction CLI are available; actual exploratory per-case interpretation with withheld targets remains unqualified. Same permitted observations, frozen checkpoint tools and accounted compute as the compared arm; case state and feedback policy must be fixed before query. | The analysis/reconstruction CLI is operator computation; a target-withholding adaptive participant investigation condition is not delivered. |
| Frozen program | source\_available | Source phased fit/predict programme and fixed references are available for the full panel; authentic staging, host protection and execution remain unestablished. Freeze code and fitting/adaptation recipe before queries; admit only explicitly allowed labels/calibration, retain all failed/incomplete cases. | Authentic source admission, protected runtime/environment and complete original fit/predict execution remain unqualified. |

Source availability does not establish a qualified runtime. A programme score cannot be reported as direct or viewer interpretation, and unsupported conditions cannot be inferred from a nearby implementation.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 20338 bytes; SHA-256 `7d8f9bdab6de4e8ae37fbb1628323a18e4887f65fb8e20e2095defe5d0b781e7`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification.
- [Detector score v1](implementations/detector-score-v1) — Reviewed source component.
  Scope: Independent frozen-detector scoring. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

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
