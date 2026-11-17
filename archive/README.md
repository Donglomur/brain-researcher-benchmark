# Retained inactive material

This directory contains two former language-encoding replay files:

- [Operator source](legacy-operators/language-encoding/replay_language_submission.py).
- [Associated test source](legacy-operators/language-encoding/tests/test_replay_language_submission.py).

They retain the original task paths, source pins and runtime assumptions as
historical source. They are not a supported current operator or a new benchmark
implementation. Their relocation does not recreate the missing original task or
its external runtime inputs.

Active task packages belong under `benchmarks/paper/`, `benchmarks/neural/` or
`benchmarks/shared/`. Material belongs in this archive only after its inactive role
has been established. The [relocation ledger](../docs/provenance/relocations/2026-11-16.json)
preserves original paths and Git identities; the [provenance guide](../docs/provenance/README.md)
explains how to interpret retained source.
