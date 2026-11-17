# Brain Treebank: Large-scale intracranial recordings from naturalistic language stimuli

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-011`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Separate paper outcomes

**Current complete-primary paired-outcome admission is unavailable.** Independent reproduction remains separately assessable under the stated source limits. Complete primary pairing is unavailable under the reviewed primary and retained source scopes. Retained source scope and coverage: Figure 5 regional-distribution results, Figures 6–7 word-onset and noun-versus-verb decoding, and Figures 2–3 confound-adjusted responsiveness/modulation remain separately named original empirical components. Preserve their implementations and prior broader definitions. They are neither silently claimed nor automatic prerequisites for the selected Figure 4a–c primary. Reviewed source limits: Original recording, transcript/annotation, example, contact and release-version manifests remain unqualified. The reviewed arXiv v1 source is not asserted to be byte/content equivalent to a separate proceedings version. Exact source negative sampling and buffers, original split identities/seeds and correct configured regression runner remain unresolved. A later release, new split or multichannel input cannot silently replace the selected source task. Source window endpoint handling and identities remain unresolved; nominal 250-ms windows, 100-ms steps and a −1 to +1 second interval do not justify inventing a 21-window manifest. Original contact selection/tie policies, reference curves, map and example identities, source numerical arrays and justified reproduction tolerances remain unresolved. Published timing scalars cannot represent the complete selected panel. Independent authentication of source observations, original training and native evaluation remains unresolved; supplied-score software components alone do not establish it. A candidate may change decoder architecture for the same qualified prediction task, while retaining the independently reproduced original linear baseline. Nonlinear AUC gains do not establish the original linear-specific timing interpretation or language-specificity beyond acoustic correlates. Meaningful effect, participant-aware and selection-aware superiority uncertainty, access/exposure and resource policies remain unresolved. Original electrode-level display intervals do not establish new confirmatory participant-level superiority uncertainty. No AUC margin, original array identity, held-out score, runtime readiness, scientific success or additional task count is established by the selection. Canonical task, outcome, catalog/CLI and admission wording require consistent bounded adoption with predecessor preservation.

**Primary scientific scope:** Complete Figure 4a–c sentence-onset versus no-speech decoding from the original Brain Treebank cohort and recorded movies: source linear contact/time outputs, eligible-contact peak map, source example curve and training-selected temporal/frontal held-out curves. Preserve the original ten-participant population, remove the source 114 corrupted contacts, retain subject 5 in nonregional analyses while excluding that subject from atlas-region analyses and brain plots. Preserve source single-electrode inputs, balanced examples and speech-free buffers, original shared splits, training-fitted preprocessing and five-fold training-CV contact selection. Exact window endpoints and identities remain subject to source verification, not a presumed count.

**Retained secondary policy:** Figure 5 regional-distribution results, Figures 6–7 word-onset and noun-versus-verb decoding, and Figures 2–3 confound-adjusted responsiveness/modulation remain separately named original empirical components. Preserve their implementations and prior broader definitions. They are neither silently claimed nor automatic prerequisites for the selected Figure 4a–c primary.

- [Reproduction proposal (inspection only)](reproduction.v1.json)
- [Primary and retained secondary scope decision](../../../docs/provenance/paper-outcome-scope-decisions.v1.json)
- [Primary-outcome unavailability record](outcomes.v1.json)
- [Preserved definition before dual outcomes](historical/task.pre-outcomes.v1.json)

| Outcome | Information condition | Endpoint eligibility | Protocol status | Declared availability | Scientific outcome |
| --- | --- | --- | --- | --- | --- |
| Reproduction | Paper data | unavailable | unavailable | unavailable | Unknown |
| Reproduction | Paper data author code | unavailable | unavailable | unavailable | Unknown |
| Improvement | Paper data | unavailable | unavailable | unavailable | Unknown |
| Improvement | Paper data author code | unavailable | unavailable | unavailable | Unknown |

Author-baseline replay and historical reconstruction attempts retain their original scopes. They are not promoted to qualified AI reproductions or improvements by these contracts.

## Retained secondary improvement policy

This preserved policy remains source evidence for a different or narrower scientific question. It is unavailable for primary outcome admission and does not define primary paper success.

**Disposition:** source\_unresolved. The paper has an ordered decoding task, but the original release/splits, exact ROC-AUC panel numbers and full source aggregation have not been recovered. The registered implementation tests word responsiveness and cannot stand in for that baseline.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 47497 bytes; SHA-256 `c030ea3ebca0be88e291a1903de891d0b0570d5fb22786a819202ad24bc6e53d`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prepared-epoch Brain Treebank word-responsiveness endpoint with five paired pre/post windows, stable pooled electrode statistics, matched minimum-p/effect output and an explicitly prospective multiplicity policy. Native timing/filtering and full word/electrode admission, temporal dependence, historical tolerances, sentence-position and time-resolved decoding, joint confound adjustment, grouped protected splits and code/media rights remain unresolved. The source family overlaps NEURAL-016 and is not an independent cohort. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Decoding curves v1](implementations/decoding-curves-v1) — Reviewed source component.
  Scope: Brain Treebank decoding curve component. This registration records the reviewed source scope and its generated controls only; it does not activate a runtime or establish authentic-data execution, native interpretation, model performance or scientific qualification.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/czlwang/brain_treebank_code_release)
- [Code](https://proceedings.nips.cc/paper_files/paper/2024/hash/aefa2385b3f33abf1526ae4e2c208cd9-Abstract-Datasets_and_Benchmarks_Track.html)
- [Code](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/data/all_trials.json)
- [Code](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/features_list.txt)
- [Code](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/run_glms.py)
- [Code](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/run_time_tests.py)
- [Code](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/stats/sentence_position_tests.py)
- [Code](https://raw.githubusercontent.com/czlwang/brain_treebank_code_release/c54ba38eab7814538bc03b1b6d29a3f50f034e12/stats/word_onset_tests.py)
- [Paper](https://proceedings.nips.cc/paper_files/paper/2024/hash/aefa2385b3f33abf1526ae4e2c208cd9-Abstract-Datasets_and_Benchmarks_Track.html)
- [Source](https://braintreebank.dev/)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
