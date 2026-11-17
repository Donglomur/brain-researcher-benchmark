# GLM-Transformer prospective ablation evaluator

This independently written evaluator scores the complete ten-session history-versus-interaction comparison. Its prospective primary endpoint is equal-session mean neural Poisson-loss gain; source-style variational loss and pooled weighting are separately reported.

Requires an existing Python 3.10+ runtime with NumPy. From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 benchmarks/paper/PAPER-paper-method-018/implementations/initial-evaluator-v1/evaluator.py \
  --reference /operator/reference/reference.json \
  --submission /candidate/predictions/submission.json \
  --output /output/new-report.json
```

Reference and candidate manifests must bind complete numeric NPZ arrays, exact ordered trial/neuron/bin axes, native inference batches and matched construction recipes. The output path must not already exist. The [task documentation](../../docs/initial-evaluator-v1.md) gives the complete input format, equations and source mapping.

Run the generated engineering controls from this package directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

This package does not train a model, load author checkpoints/pickles, download Allen data, or redistribute author code. Native source-interface, split, encoder-layout, figure-reference, rights and population-validation holds remain explicit. Target-conditioned reconstruction is not blind forecasting. All controls are generated engineering data; no authentic reproduction, causal connectivity, scientific qualification or benchmark acceptance is established.
