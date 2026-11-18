# Brain Treebank: Large-scale intracranial recordings from naturalistic language stimuli

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-011`
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

- Recover source ROC-AUC arrays or an independently reproduced exact author baseline for the full original panel.
- Freeze original recording/transcript/example and electrode inventories, negative-sample selection, split seeds and the correct regression runner configuration.
- Verify train-only top-ten electrode selection, complete time-window coverage and paper panel aggregation; generic all-ROC averaging is not equivalent.
- Validate native alignment/preprocessing and retain documented corrupted-contact and subject-5 region exclusions.
- Define meaningful effect, participant-aware uncertainty, fixed access/resource budgets and a working protected decoding evaluator.
- Authenticate exact original temporal/frontal DK grouping, top-ten cutoff tie convention, source 95% display interval formula and nearest-pial/fsaverage projection artifacts.
- Preserve explicit author-all-contact versus new 133-exclusion wrapper distinction; authenticate historical source result lineage rather than declaring reconstructed mask automatically equivalent.
- Resolve paper balanced-test versus native unstratified split, exact terminal-window support and actual source samples across contact/window calls; no silent repairs.
- Source figure4-producer-v2 is delivered owner/reference code with generated controls only; native recordings, runtime and complete original panel agreement remain unexecuted/unqualified.
- Pending full-panel comparison/admission implementation: improvement/v1 scalar fields cannot alone admit this original vector or curve panel. Preserve source-defined metrics and full support; do not invent a pooled scalar. An additive panel comparator is being constructed separately and is not bound here.
- No authentic computation/admission policy or immutable result identity is fabricated. All four AI outcome/assistance cells remain unknown.

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

**Disposition:** source\_unresolved. The paper has an ordered decoding task, but the original release/splits, exact ROC-AUC panel numbers and full source aggregation have not been recovered. The registered implementation tests word responsiveness and cannot stand in for that baseline.

- [Retained original improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 59104 bytes; SHA-256 `247b5f7bffeb4b8c5301e4e9532139912f9b0cf0b49efd0461818830ad7fee66`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prepared-epoch Brain Treebank word-responsiveness endpoint with five paired pre/post windows, stable pooled electrode statistics, matched minimum-p/effect output and an explicitly prospective multiplicity policy. Native timing/filtering and full word/electrode admission, temporal dependence, historical tolerances, sentence-position and time-resolved decoding, joint confound adjustment, grouped protected splits and code/media rights remain unresolved. The source family overlaps NEURAL-016 and is not an independent cohort. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.
- [Treebank figure4 producer v2](implementations/treebank-figure4-producer-v2) — Reviewed task source component.
  Scope: Partial Figure4 owner-reference source only. It does not complete all original assays or qualify reproduction or improvement; exact source and generated controls retain their original limits.
- [Treebank observation verification v1](implementations/treebank-observation-verification-v1) — Reviewed source component.
  Scope: Reviewed additive source component for the existing task. The package documentation and source contracts define its scope; source enrollment does not establish authentic-data execution or scientific qualification.
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
