# Complete NEURAL-014 fixed-program interface

Supply one UTF-8 self-contained Python file, at most 131072 bytes. Commit it before the controller reads numerical input. The independently frozen reference is selected from the captured source manifest, never from a candidate operand. The same candidate bytes run every mode. Programs have only their declared view, a fresh bounded output volume, and a read-only sealed model when specified. Every phase is offline in the same separately qualified cached image/resource condition.

Commands:

```
python program.py fit --input /input/INPUT.json --model-output /output/model.bin
python program.py adapt --input /input/INPUT.json --model /model/model.bin --model-output /output/model.bin
python program.py infer --input /input/INPUT.json --model /model/model.bin --output /output/prediction.json
python program.py prior --input /input/INPUT.json --output /output/prediction.json
```

`INPUT.json` contains exactly `schema: neural014-program-input-v1`, `mode`, `generation` and `rows`. Fit rows include every retained training/development observation and its permitted phonemes. Development selects settings/checkpoints only; no refitting. Adapt rows contain only that session's usable calibration observations, 1–20, and no query identity or feature. Both fit/adapt start in fresh processes; optimizer/recurrent/cache state is reset. Candidate normalization, adaptation schedule and hyperparameters may not be fitted on query features. Method review remains necessary to verify mathematical intent even when process separation holds.

Infer rows contain exactly one full query with `id`, `session`, `role`, `steps`, and `features` (relative array path, bytes and SHA256), without target tokens. The candidate never sees the perturbation arm name or permutation index. Every array has its original full time extent and 512 ordered columns. Full/shuffle/zero use the exact same sealed adapted artifact. Their input metadata and paths have the same form; differences are the declared feature values and their integrity hashes. An inference algorithm may not branch on inferred treatment to alter the scientific method. Each infer process starts fresh, so other outputs/queries cannot be consulted.

Prior rows contain only `role` and `tokens`, from base training and that session's calibration. There are no query IDs, order, neural values, trial durations or source context. Return one complete sequence; the trusted controller attaches it identically to every query. This is a descriptive unconditioned prior, not an exhaustive language-knowledge control.

Fit/adapt produce exactly one nonempty opaque `model.bin`, at most 256 MiB. Infer produces exactly `{"id":"opaque-id","tokens":[...]}`; prior produces exactly `{"tokens":[...]}`. Raw predictions are at most 32768 bytes. Tokens use the unchanged original ASCII normalization and 40-symbol inventory, at most 2048 final tokens. Empty predicted sequences remain valid, missing rows do not. Perform CTC repeat/blank collapse before submission; repeated final tokens remain. Original lexical JSON bounds are retained, including 48 nested levels, 18-character integer literals, duplicate-field and nonfinite-number refusal.

Every model is captured only after natural producer exit and closure, sealed read-only, and bound to its exact source, phase, base and input view. One full-adapted model per session is reused by three ablations as expressly allowed in the original operator contract; only fitted artifact state is reused, never query state. One loss-adapted model remains separate. Candidate and reference models/programs are independent. All 63 final answers per panel use the original `neural014-predictions-v1` context schema and must be admitted before any private gold access.

The prepared controller input has `PUBLIC.json`, `arrays/`, and `permutations/` only. It is operator-only and is not mounted wholesale. `program/preparation.py` provides the full projection, NumPy2.2.6 index generator and separate semantic recomputation functions; future invocation needs captured source plus independent native preparation and resource authorization. Input review must establish global sentence priority/no refill and original provenance; sanitized descriptors alone cannot establish those facts. The old NEURAL013 split-policy file is used only for the exact45-session roster, not its zero-calibration rule.
