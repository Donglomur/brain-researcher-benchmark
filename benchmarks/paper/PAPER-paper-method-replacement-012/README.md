# Know Thyself by Knowing Others: Learning Neuron Identity from Population Context

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-replacement-012`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 30426 bytes; SHA-256 `f754a7dba9f43a270143fe1bcd0654a29d4d660626724a07e81593d50dde1bff`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Runs an owner-side NuCLR Bugeon linear readout on supplied embeddings with train-only scaling, validation-only checkpoint selection, exact label families, three distinct split/exposure panels and matched context-ablation diagnostics. Authentic joins/splits, paper-era versus December 2025 equivalence, repeated-cell linkage, native references, optional resampling dependency, rights, protected execution and scientific qualification remain unresolved.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/nerdslab/nuclr)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/configs/data/bugeon_inductive.yaml)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/configs/data/bugeon_transductive.yaml)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/eval_scripts/multi_split_eval.py)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/eval_scripts/single_split_eval.py)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/preprocess/bugeon/download.py)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/preprocess/bugeon/experiments.txt)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/preprocess/bugeon/prepare_data.py)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/src/evaluators/bugeon.py)
- [Code](https://raw.githubusercontent.com/nerdslab/nuclr/0fa409b304147ace00507063d44f03155691af62/train.py)
- [Source](https://figshare.com/articles/dataset/19448531)
- [Source](https://ik.imagekit.io/7tkfmw7hc/nuclr/splits.zip)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
