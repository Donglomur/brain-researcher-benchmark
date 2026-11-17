# DPAD Figure 6h–i prediction evaluator

This source component selects DPAD architectures and latent dimensions from
training-only result records, then recomputes neural/behavior correlations,
session summaries, nonlinear-locus contrasts and the two-metric frontier from
all 1,960 held prediction cases. It covers the fixed seven-session candidate
roster, five folds, eight dimensions, four individual nonlinear loci, the linear
model and both flexible-selection profiles with the full 90-architecture search.

Use Python 3.10+ with its standard library; no installation or native DPAD
runtime is required. From this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v test_evaluator
python3 evaluator.py select --training training.json --output selection.json
python3 evaluator.py evaluate --targets targets.json --predictions predictions.json --plan selection.json --output results.json
```

The evaluator owner must freeze and protect `selection.json` before accepting
held predictions. `generated_control.py --output-dir /tmp/dpad-engineering-control`
creates bounded engineering fixtures that illustrate every input field; invoke
it with `python3`. These controls are not neural data or trained-model results.

This package does not train models, retrieve data, establish historical
reproduction, or certify scientific qualification. Candidate session mapping,
the random electrode subset, original preprocessing/runtime, native model
provenance, protected references, access parity and applicable rights remain
gates. Historical and prospective profiles stay separate, and temporal-fold
results are not held-session improvement claims.

See the [full interface, source semantics and limitations](../../docs/initial-evaluator-v1.md)
and [primary-source identities](provenance.json). All outputs retain scientific
qualification as unknown.
