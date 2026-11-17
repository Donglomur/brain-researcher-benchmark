# Brain Treebank: Large-scale intracranial recordings from naturalistic language stimuli

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-011`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Source unresolved
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Improvement outcome:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule. Paper reproduction is a separate first-class outcome; this currently bound contract assesses improvement.

**Disposition:** source\_unresolved. The paper has an ordered decoding task, but the original release/splits, exact ROC-AUC panel numbers and full source aggregation have not been recovered. The registered implementation tests word responsiveness and cannot stand in for that baseline.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition](historical/task.pre-improvement.v1.json)

Within the existing improvement contract, historical graders and pilot scores retain their calibration role. They are not automatically qualified reproductions or improvements. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 38093 bytes; SHA-256 `6cb4599d9cc45b471ebc5ce7d10308233c91a4a784d32c9e47e1dadec48d1ca7`.

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
