# FIND025 current numerical repair

`SOURCE.json` identifies the current repaired metric primitive, its generated
controls, and the unchanged comparison contract and canonical task. Historical
source commits, relocation records and source-evidence pins remain historical.
The package README and CONTRACT statements about byte-identical primitives and
50 tests describe their original construction; this current descriptor records
the subsequent arithmetic repair and the expanded 57-test suite.

The package README now points its test command to the current task directory
and links the maintained artifact evaluator and separate covariance-variance
component. Its current bytes belong to `current_files`; its pre-correction
identity is retained under `historical_binding`. Actual comparison contracts,
schemas, fixtures and historical task definitions remain in
`unchanged_contract_files`. This documentation correction changes no metric or
scientific qualification.

The original squared Pearson primitive returned `1.0000000000000004` for two
identical integer vectors from 0 through 16. Both comparison modes correctly
rejected this value because evaluator correlation scores must lie in `[0, 1]`.
The primitive now normalizes an internally calculated overshoot to exactly 1
only within eight binary64 ULPs of 1 (`1.7763568394002505e-15`). A larger bound
violation raises `UndefinedMetric`; nonfinite arithmetic and constant-support
refusals remain in force. Values already within `[0, 1]` are unchanged. This
arithmetic guard does not create a scientific tolerance, and external scores
even one ULP above 1 remain invalid.

The generated suite checks perfect and nonperfect correlations, both evaluator
modes, strict rejection of external overshoots, and constant/nonfinite inputs.
It also checks a subnormal input whose products cause a material numerical
bound violation, ensuring the repair refuses that case instead of reporting a
clipped success. The change does not promise arbitrary-magnitude stability:
pre-existing overflow, underflow, and cancellation limits remain. Signed
variance explained, all assigned populations, metric identities, unresolved
scientific operands, and scientific/execution holds are unchanged.

Run the source-only controls from the repository root:

```sh
python3.11 -I -S -B -m unittest discover -s benchmarks/paper/PAPER-FIND-025/implementations/submission-comparison -p test_find025_contract.py
python3.11 -I -S -B -m unittest discover -s tests/benchmarks -p test_numeric_find025.py
```

These controls use invented values and declarations. They do not execute a
scientific benchmark, validate provenance, load authentic inputs, or establish
paper reproduction or protected improvement.
