# Population Transformer: Learning Population-level Representations of Neural Activity

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-006`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 31269 bytes; SHA-256 `4b06cd0993642d160ce1f953434c777292f771c86d27896feafa5775c64ca4ef`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Prospective paired PopT-versus-BrainBERT RMS prediction evaluation for seven subjects at nested electrode counts, with ROC-AUC, separately defined F1, temporal-block uncertainty, target-free interface export and native-array binding checks. Authentic population/row-order evidence, historical splits and ranking parity, BrainBERT weight identity/rights, pretraining exposure, model execution and protected grading remain held. Scientific qualification is unknown.

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
