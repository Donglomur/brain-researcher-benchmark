# Exploiting correlations across trials and behavioral sessions to improve neural decoding

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-009`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The selected original task is the complete Figure 5A-D decoding comparison: four behaviors, five brain regions and ten IBL sessions, with every applicable source author-model condition and baseline. This is an ordered performance task, but exact panel cohort identities, preprocessing/metric provenance and numeric published results remain unrecovered. A new cohort or the separate prospective40 condition cannot establish this same-task paper win.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 29997 bytes; SHA-256 `6980d89c75ef3ed7566f4e860761946caaa4d6892119ce75095e3fb0961105c5`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://doi.org/10.1016/j.neuron.2025.10.026)
- [Code](https://github.com/yzhang511/neural_decoding)
- [Code](https://raw.githubusercontent.com/yzhang511/neural_decoding/1508b1ac5a95af2f8627f0c304ee0a750cb36e77/data/repro_ephys_release.txt)
- [Code](https://raw.githubusercontent.com/yzhang511/neural_decoding/1508b1ac5a95af2f8627f0c304ee0a750cb36e77/env.yaml)
- [Code](https://raw.githubusercontent.com/yzhang511/neural_decoding/1508b1ac5a95af2f8627f0c304ee0a750cb36e77/src/0_data_caching.py)
- [Code](https://raw.githubusercontent.com/yzhang511/neural_decoding/1508b1ac5a95af2f8627f0c304ee0a750cb36e77/src/1_decode_single_session.py)
- [Code](https://raw.githubusercontent.com/yzhang511/neural_decoding/1508b1ac5a95af2f8627f0c304ee0a750cb36e77/src/2_decode_multi_session.py)
- [Code](https://raw.githubusercontent.com/yzhang511/neural_decoding/1508b1ac5a95af2f8627f0c304ee0a750cb36e77/src/3_decode_multi_region.py)
- [Code](https://raw.githubusercontent.com/yzhang511/neural_decoding/1508b1ac5a95af2f8627f0c304ee0a750cb36e77/src/models/decoders.py)
- [Code](https://raw.githubusercontent.com/yzhang511/neural_decoding/1508b1ac5a95af2f8627f0c304ee0a750cb36e77/src/utils/ibl_data_utils.py)
- [Paper](https://doi.org/10.1016/j.neuron.2025.10.026)
- [Source](https://openalyx.internationalbrainlab.org)
- [Source](https://zenodo.org/records/17317498)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
