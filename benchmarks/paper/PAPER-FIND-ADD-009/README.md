# An instantaneous voice-synthesis neuroprosthesis

[Paper research](../README.md) · [All benchmarks](../../README.md)

- **Task ID:** `PAPER-FIND-ADD-009`
- **Track:** Paper research
- **Registration:** Original canonical specification
- **Declared specification status:** Specification only
- **Scientific and submission readiness:** Unknown

The `task.json` in this folder is the authoritative registered definition. Implementation artifacts below are assigned explicitly by the registry; their scope may be narrower or alternative, as described in each scope note. Source presence is not evidence of successful execution or complete scientific qualification.

## Specification and implementation

- [Authoritative task specification](task.json)
- Specification identity: 19354 bytes; SHA-256 `6407aa25a490bc29f256e5f8e063b1782e633c5c7ec5e4a409d0b864430c3a30`.

No legacy runtime declaration is linked to this registered ID. The current implementation artifacts are listed separately below.

## Task documentation

- [Initial evaluator and source requirements](docs/initial-evaluator-v1.md)

## Implementation artifacts

- [Initial evaluator v1](implementations/initial-evaluator-v1) — Task implementation.
  Scope: Feature-level speech evaluation using speech-only DTW-aligned Pearson correlation across 40 Mel bands and paired-sentence WER/PER summarized across seven listeners, with declared trial/session coverage and exposure checks. Native frontend/DTW/tokenization parity, authentic trial membership, decoder training, waveform generation, original ten-fold controls and protected references remain held. No clinical or whole-paper result is established; scientific qualification is unknown.

Package-local task IDs do not override this registered definition; ownership links alone do not establish equivalent scientific scope.

## Public source citations

- [Code](https://github.com/Neuroprosthetics-Lab/brain-to-voice-2025)
- [Paper](https://www.nature.com/articles/s41586-025-09127-3)
- [Source](https://datadryad.org/dataset/doi:10.5061/dryad.2280gb64f)

Citations come from the specification; their availability was not rechecked when generating this page.

Generated from the public catalog; edit the authoritative definition and regenerate instead of editing this page.
