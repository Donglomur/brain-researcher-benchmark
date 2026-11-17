# Brain Treebank: Large-scale intracranial recordings from naturalistic language stimuli

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-011`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 39979 bytes; SHA-256 `43a4653f5da2600d6df0733d2fff6a821aee5d9588234f236c5f147a6d302b12`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prepared-epoch Brain Treebank word-responsiveness endpoint with five paired pre/post windows, stable pooled electrode statistics, matched minimum-p/effect output and an explicitly prospective multiplicity policy. Native timing/filtering and full word/electrode admission, temporal dependence, historical tolerances, sentence-position and time-resolved decoding, joint confound adjustment, grouped protected splits and code/media rights remain unresolved. The source family overlaps NEURAL-016 and is not an independent cohort.

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
