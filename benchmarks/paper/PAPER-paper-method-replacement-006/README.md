# Population Transformer: Learning Population-level Representations of Neural Activity

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-006`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Design ready
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Current paper-improvement objective

**Success:** surpass the source-paper result on its exact original task, with a justified meaningful effect and predeclared uncertainty rule.

**Disposition:** design\_ready. The original volume-decoding task and Table 1 90-channel PopT+BrainBERT result are identifiable, including all seven downstream participants. Exact historical rows, ranked channel ensembles and checkpoint/feature binding are still unqualified. The existing support-disjoint prospective RMS evaluator cannot stand in for the paper’s random-row task.

- [Source-grounded improvement contract](improvement.v1.json)
- [Preserved historical task definition (calibration only)](historical/task.pre-improvement.v1.json)

Existing reproduction graders and pilot scores remain calibration evidence. They cannot establish paper improvement. Published paper results, reproduced author baselines, and verified current SOTA are separate claims. A new split, easier inputs, smaller cohort or changed metric is an extension.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 32190 bytes; SHA-256 `777b642dc2813291a7d2a6a1bea22df6500a12513a01743cd765e088f7a81108`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Calibration only.
  Scope: Prospective paired PopT-versus-BrainBERT RMS prediction evaluation for seven subjects at nested electrode counts, with ROC-AUC, separately defined F1, temporal-block uncertainty, target-free interface export and native-array binding checks. Authentic population/row-order evidence, historical splits and ranking parity, BrainBERT weight identity/rights, pretraining exposure, model execution and protected grading remain held. Scientific qualification is unknown. Retained historical reproduction/calibration component; this implementation does not establish source-paper improvement success.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/czlwang/PopulationTransformer)
- [Code](https://raw.githubusercontent.com/czlwang/PopulationTransformer/d237755bbdea123c60bface0cecbb48bab6f42de/3_write_finetuning_data.sh)
- [Code](https://raw.githubusercontent.com/czlwang/PopulationTransformer/d237755bbdea123c60bface0cecbb48bab6f42de/4_create_finetuning_manifest.sh)
- [Code](https://raw.githubusercontent.com/czlwang/PopulationTransformer/d237755bbdea123c60bface0cecbb48bab6f42de/5_run_finetuning.sh)
- [Code](https://raw.githubusercontent.com/czlwang/PopulationTransformer/d237755bbdea123c60bface0cecbb48bab6f42de/data/write_multi_subject_multi_channel.py)
- [Code](https://raw.githubusercontent.com/czlwang/PopulationTransformer/d237755bbdea123c60bface0cecbb48bab6f42de/electrode_selections/clean_laplacian.json)
- [Code](https://raw.githubusercontent.com/czlwang/PopulationTransformer/d237755bbdea123c60bface0cecbb48bab6f42de/run_train.py)
- [Code](https://raw.githubusercontent.com/czlwang/PopulationTransformer/d237755bbdea123c60bface0cecbb48bab6f42de/trial_selections/pretrain_split_trials.json)
- [Code](https://raw.githubusercontent.com/czlwang/PopulationTransformer/d237755bbdea123c60bface0cecbb48bab6f42de/trial_selections/test_trials.json)
- [Source](https://braintreebank.dev/)
- [Source](https://drive.google.com/file/d/14ZBOafR7RJ4A6TsurOXjFVMXiVH6Kd_Q/view)
- [Source](https://huggingface.co/api/models/PopulationTransformer/popt_brainbert_stft)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
