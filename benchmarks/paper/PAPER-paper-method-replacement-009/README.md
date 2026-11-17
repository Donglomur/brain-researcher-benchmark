# Exploiting correlations across trials and behavioral sessions to improve neural decoding

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-009`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

### Current selected paper endpoint

**Disposition:** source\_unresolved.

This version selects an exact author-reported computational result as the primary benchmark endpoint. The broader biological finding and prior contracts retain their original scope. The source selection does not establish runnable delivery, an AI evaluation, reproduction or improvement; both access conditions remain uninstantiated.

- [Selected current improvement contract](primary-endpoint-v1/improvement.v1.json)
- [Authenticated endpoint selection](primary-endpoint-v1/selection.v1.json)
- [Reviewed endpoint selection authority](../../../docs/provenance/paper-primary-endpoint-selections.v2.json)

**Remaining reproduction/source limits:**

- Authenticate original Figure 5A immutable RE objects, ten-session animal/unit/trial identities and every supported author-condition/region incidence; no synthetic rectangular census.
- Recover complete published author choice-AUC vectors and original class orientation, continuous-score implementation, undefined policy and panel aggregation. Released argmax accuracy is a proven incompatible endpoint.
- Reconcile original static window, eligibility, scaling, missing-value handling and full scored-trial coverage with example cache/loader/drop\_last behavior.
- Recover source-permitted choice prior/sequence/model incidence and original stochastic split/training settings; do not use target-session oracle behavior or demand historical RNG identity without a scientific reason.
- Qualify native original author-model replay and independent prediction-to-AUC verification, calibrated reproduction tolerance and strongest applicable source comparator.
- Freeze meaningful AUC gain, original animal/session-aware paired inference, region/method multiplicity, complete-panel decision and common assistance/resource budgets before final scoring.

- [Selected-endpoint reproduction contract](primary-endpoint-v1/reproduction.v2.json)
- [Paired outcome protocols](primary-endpoint-v1/outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Retained predecessor improvement policy

This original contract preserves the predecessor scientific instructions and source scope. The selected primary policy above governs current improvement.

**Disposition:** source\_unresolved. The selected original task is the complete Figure 5A-D decoding comparison: four behaviors, five brain regions and ten IBL sessions, with every applicable source author-model condition and baseline. This is an ordered performance task, but exact panel cohort identities, preprocessing/metric provenance and numeric published results remain unrecovered. A new cohort or the separate prospective40 condition cannot establish this same-task paper win.

- [Retained original improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 30473 bytes; SHA-256 `c1f20d3824e96d36deaacd6a77b3be0209363b2b1fed64adf3f43e0cb3923d33`.
- [Preserved legacy runtime declaration](implementations/registered-runtime/manifest.json)
- [Legacy declaration package](implementations/registered-runtime)

This preserved declaration is lineage, not current execution qualification. Its historical paths may describe the source snapshot.

## Implementation artifacts

- [Registered runtime](implementations/registered-runtime) — Calibration only.
  Scope: This is the source package currently selected by the published catalog; current does not assert executable/scientific qualification. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Figure5 metric diagnostics v1](implementations/figure5-metric-diagnostics-v1) — Reviewed source component.
  Scope: Figure 5 metric diagnostics. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

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
