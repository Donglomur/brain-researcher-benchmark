# Current DFINE numeric source

`CURRENT_SOURCE.json` binds the current eight-file missing-observation package
for `PAPER-CANDIDATE-20261114-DFINE`. The original `SOURCE_MANIFEST.json`,
`PROVENANCE.json`, scientific specification, canonical task and correction note
retain their historical bytes. Only `scorer.py` and `test_scorer.py` change in
the package.

The Pearson repair subtracts an input value before scaling, so representable
variation near a common offset survives centering. If opposite finite extremes
overflow during subtraction, a power-of-two half-scale bounds that difference.
The constant-column zero contribution, invalid-input rejection, complete
population, block masks, all-timepoint scoring, target-last admission, and
aggregation rules remain in force.

Run the authenticated current controls from the repository root:

```sh
python3 -I -S -B tests/benchmarks/test_numeric_dfine.py -v
```

The wrapper verifies current source identity before importing package tests,
runs all twelve numeric tests and the unchanged relocated CLI/target-last
control, and supplies two current-binding checks. It explicitly supersedes the
historical inventory test, whose old hashes describe the original component.
No historical hashes are rewritten to pretend the repaired source was original.

Controls use generated inputs and the Python standard library. Exact rational
centering and an 80-digit Decimal final reduction provide an independent
Pearson oracle. Tests cover near-offset affine and non-affine values, input
permutations, positive/negative signs, large/small scales, opposite maximum
finite values, subnormal variation, constant columns, invalid inputs, and
propagation through all declared score cells and curves.

This remains a numeric component with no authentic-data or native execution
qualification. Original data/mask/fold provenance, training and causal inference
boundaries, native float32 parity and reference competence remain unresolved.
The repair grants no additional execution authority and introduces no task,
metric threshold, or overall cross-method/ratio scalar.
