# Neuro-Symbolic Decoding of Neural Activity

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-paper-method-020`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 2231796 bytes; SHA-256 `263ea4a405bdee13a1003048c883293b224589ebce6e4816e7a3e5e4b8248182`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Audits the complete CSI1 BOLD5000-QA inventory and image/person aliases, projects separate neural/zero/shuffled inference packets, and scores every declared structured QA answer. Native NPY conversion, actual stimulus identity, question-text leakage, genuine model provenance, protected runtime, source test-informed selection differences, broader person/stimulus independence, independently trained text-only baseline and scientific qualification remain open.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/PPWangyc/neurona)
- [Code](https://github.com/PPWangyc/neurona/blob/8071fb42c3ddac0355f2c0b5977baa32e33f6e14/scripts/download_data.sh)
- [Code](https://github.com/PPWangyc/neurona/blob/8071fb42c3ddac0355f2c0b5977baa32e33f6e14/scripts/train_bold5000.sh)
- [Code](https://github.com/PPWangyc/neurona/blob/8071fb42c3ddac0355f2c0b5977baa32e33f6e14/src/loader/fqa.py)
- [Code](https://github.com/PPWangyc/neurona/blob/8071fb42c3ddac0355f2c0b5977baa32e33f6e14/src/train_bold5000.py)
- [Code](https://huggingface.co/datasets/PPWangyc/BOLD5000-QA)
- [Code](https://proceedings.iclr.cc/paper_files/paper/2026/hash/33c069ac8440595724bcc373c9a52852-Abstract-Conference.html)
- [Code](https://raw.githubusercontent.com/PPWangyc/neurona/8071fb42c3ddac0355f2c0b5977baa32e33f6e14/LICENSE)
- [Code](https://raw.githubusercontent.com/PPWangyc/neurona/8071fb42c3ddac0355f2c0b5977baa32e33f6e14/README.md)
- [Paper](https://proceedings.iclr.cc/paper_files/paper/2026/hash/33c069ac8440595724bcc373c9a52852-Abstract-Conference.html)
- [Source](https://huggingface.co/api/datasets/PPWangyc/BOLD5000-QA)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
