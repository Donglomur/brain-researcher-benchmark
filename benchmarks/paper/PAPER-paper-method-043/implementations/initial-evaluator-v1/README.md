# NeuroPictor initial arithmetic evaluator

See [the task documentation](../../docs/initial-evaluator-v1.md) for the source contract, complete manifest schema, restrictions and commands. This independently written package computes the eight reconstruction metric families from trusted prepared tensors and enforces identity-bound matched comparisons. All scientific/native/rights/protected-population gates remain open.

Dependencies: existing Python 3.10+, NumPy and SciPy. No installation or model/data acquisition is performed.

From the repository root, evaluate an operator-prepared manifest:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 \
  benchmarks/paper/PAPER-paper-method-043/implementations/initial-evaluator-v1/evaluator.py \
  /path/to/operator-manifest.json --output /path/to/panel.json
```

The manifest and identity-bound NPZ inputs must follow the linked documentation; this command does not generate model reconstructions or extract features.
