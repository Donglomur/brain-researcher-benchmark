# Cross-cohort seizure robustness

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-012`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 16574 bytes; SHA-256 `b5242449dfe9a858a50cd61ac3f367669c2f7a33f90194cb6afd45e3a01da82b`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Catalog registered source package.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification.

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
