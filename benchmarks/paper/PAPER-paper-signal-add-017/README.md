# EEG-based brain-computer interface enables real-time robotic hand control at individual finger level

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-signal-add-017`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

The current definition supports two independent outcomes: recreate the original findings and exceed them on the same task. Each uses matched paper+data and paper+data+author-code conditions. Contract eligibility and declared protocol availability do not establish a delivered runtime or scientific result.

**Corrected primary scope; outcomes remain unqualified.** Both outcome contracts retain the same primary scientific task. Unresolved source criteria still limit receipt admission.

**Primary goal:** Reproduce the original recorded-session finger-decoding and fine-tuning comparisons for the source-defined thumb–pinky and thumb–index–pinky conditions, preserving the complete Figure 2A MI model-by-session comparison and the separately identified ME counterpart in the current task. Keep source chronological training/calibration inputs, common assessment observations, participant/session identities and the controls needed for the claimed result. Evaluate improvement against a qualified author comparator on that same named recorded-decoding result. Report replayed and recorded online outputs distinctly; neither an isolated binary mean nor improved replay accuracy establishes a new human closed-loop gain or whole-paper reproduction.

**Primary scientific scope:** The retained offline-trained finger decoder and recorded cross-session/fine-tuning comparison, already scoped to labels 1/2/4 and binary/ternary conditions. Figure 2A MI compares S1-Base, S1-Finetune and S2-Base replay on common S2-Finetune observations with the recorded S2-Finetune result. Preserve both class conditions and the full source-defined model/participant/session comparison. MI is the explicit historical anchor; the existing current-task ME/S7 counterpart remains separately named and source-qualified, never pooled or inferred from MI-only outputs. Include human-learning/run-trend companions only when claiming their corresponding attribution. No automatic full-Figure-6 or whole-paper scope is enrolled.

**Remaining source limits:**

- The original recorded-session source-member, participant/session/run/trial and exclusion joins, trained-model/checkpoint provenance, complete figure-specific prediction outputs and immutable comparison roster remain unqualified.
- Preserve distinct roles for Figure 2A EEGNet replay, recorded S2-Finetune outputs and source human-learning controls. The author's trial-first 80/20 training/validation split is not the final figure assessment or five-fold FBCSP evaluation. Exact source folds are required only for enrolled five-fold companion outputs.
- The source defines trial-majority voting, but complete window/trial eligibility, tie handling, participant aggregation and numerical original references still need independent verification. Paper means or p-values cannot substitute for computation or agreement/superiority criteria.
- The ME/S7 counterpart is described in the inspected main text, while complete supplementary numerical definitions remain unavailable; preserve its own source identities and report it as unqualified until resolved rather than expanding or pooling from MI.
- Source controls and uncertainty must match the enrolled claim. Machine-versus-human learning attribution requires its relevant FBCSP/run-trend companions; a bounded decoder comparison alone cannot establish that broader interpretation.
- Assessment targets and recorded prediction/probability fields are operator evaluation/reference material, not candidate-time decoding inputs. Preserve authentic chronological training/calibration access and matched paper+data versus +code exposure/resources; these complete manifests remain unresolved.
- No native parity, trained-decoder result, scientific reproduction or improvement is established. Full-Figure-6 four-finger discrepancies and Session-5 missing events are not automatic blockers for the named Session-1/2 result; attach them only to affected outputs if separately enrolled.

**Retained source scope:** No new scientific secondary endpoint is selected. Retain existing source preparation as supporting software and the broader-paper census as context. The complete eleven-combination Figure 6 experiment is a genuine distinct empirical offline-decoding result, not simulation or preprocessing, but its presence in the paper does not make it the registered primary or an automatically enrolled secondary outcome. The source's Figure 2/S7 offline simulation is real recorded-EEG replay within the retained primary family.

- [Reviewed primary scope correction](../../../docs/provenance/paper-outcome-scope-decisions.v1.json)
- [Original-finding reproduction contract](reproduction.v2.json)
- [Paired outcome protocols](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Reproduction | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data | source\_unresolved | unresolved | unresolved | Unknown |
| Improvement | Paper data author code | source\_unresolved | unresolved | unresolved | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The registration scopes recorded offline decoding, which is ordered, but its exact source-paper offline baseline and original folds/session mapping are unrecovered. The published online fine-tuned human-control headline is incompatible with replay scoring and cannot be the offline victory threshold.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 22356 bytes; SHA-256 `2633592d00830def2848af1b003ddfe1417fef34d9ba59de3490d30ae3cfaaf6`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Complete frozen selected numeric-export roster to source-aligned finger-EEG trials/windows, chronological calibration routing, target-free packets, a train-only prospective spectral reference and hard-vote trial/participant metrics with paired uncertainty. Authentic MAT conversion and complete source population, native TensorFlow EEGNet preprocessing/fine-tuning, protected numerical references, artifact controls, source rights/resources and scientific qualification remain held. Recorded replay does not reproduce closed-loop human feedback adaptation. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Recorded panel v1](implementations/recorded-panel-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
- [Source preparation v1](implementations/source-preparation-v1) — Reviewed source component.
  Scope: Original finger-EEG training input preparation. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/bfinl/Finger-BCI-Decoding)
- [Paper](https://www.nature.com/articles/s41467-025-61064-x)
- [Source](https://figshare.com/articles/dataset/29104040)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
