# Linguistic effects beyond natural-movie covariates

[Neural-data understanding](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `NEURAL-016`
- **Track:** Neural-data understanding
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 28911 bytes; SHA-256 `ab8710a3ec322e86df18814b376f34c6b11910517dd4487fce807dcd767a5ac5`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prospective evaluator for paired nuisance/full held-out predictions, with separate incremental explained variance and R², declared person/movie and temporal split checks, complete recording accounting, participant summaries, paired uncertainty and a temporal control utility. Native Brain Treebank preprocessing, actual fit-lineage and privacy verification, electrode and population admission, competent references, rights and protected scientific evaluation remain unresolved. This shares the Brain Treebank source family with PAPER-paper-method-replacement-011, not an independent cohort.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Source](https://arxiv.org/abs/2411.08343)
- [Source](https://braintreebank.dev/)
- [Source](https://braintreebank.dev/data/quickstart.ipynb)
- [Source](https://braintreebank.dev/data/subject_metadata.zip)
- [Source](https://braintreebank.dev/data/subject_timings.zip)
- [Source](https://braintreebank.dev/data/transcripts.zip)
- [Source](https://github.com/czlwang/brain_treebank_code_release)
- [Source](https://proceedings.nips.cc/paper_files/paper/2024/hash/aefa2385b3f33abf1526ae4e2c208cd9-Abstract-Datasets_and_Benchmarks_Track.html)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
