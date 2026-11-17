# Prospective fixed-neuron held-trial evaluator

This standalone Python 3 package provides owner-side prospective neural prediction
scoring for `PAPER-SCOPE-20261114-LATENTCIRCUIT`. It audits the declared unit/trial
census and nested partition, derives train-only normalization, constructs separate
development and assessment metadata packets, and computes the fixed-coordinate
loss and paired condition-mean control. It uses only the Python standard library.

Read [the complete interface and scientific scope](../../docs/initial-evaluator-v1.md)
before preparing an owner dataset. No authentic data, fitted weights, neural
archive or official source is included. The owner supplies already preprocessed
single-unit trial trajectories; this package does not resolve their native timing
or establish that they match the empirical reference.

From the repository root, run the engineering controls:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s benchmarks/paper/PAPER-SCOPE-20261114-LATENTCIRCUIT/implementations/initial-evaluator-v1/tests -v
```

The executable offers `audit`, `prepare`, `baseline`, and `score` commands; use
`python3 benchmarks/paper/PAPER-SCOPE-20261114-LATENTCIRCUIT/implementations/initial-evaluator-v1/evaluator.py --help`
from the repository root for arguments. All commands require an owner-frozen
SHA256 of the exact owner JSON bytes. All reports remain owner-side. This is not
an execution sandbox or a complete activated benchmark. Native reconstruction,
behavioral non-inferiority, reference fitting, rights admission, protected
execution and scientific qualification remain held. Task counts are unchanged.
