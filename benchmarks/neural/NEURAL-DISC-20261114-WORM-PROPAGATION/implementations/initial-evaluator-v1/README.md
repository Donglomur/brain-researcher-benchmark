# Conditional worm calcium-response evaluation

Source implementation for `NEURAL-DISC-20261114-WORM-PROPAGATION`: score complete
receiver-response predictions against training-only pair means, persistence and
regularized convolution references. It preserves original timestamps/missingness,
uses separate development worms, exports target-free held packets, and reports
hierarchical worm-level raw/normalized errors, correlation, area and uncertainty.

Requires Python 3 and NumPy. Using the existing environment, run from this directory:

```sh
python3 -m unittest discover -s tests -v
python3 worm_evaluator.py export /path/to/verified-custody.json /new/role-packets
python3 worm_evaluator.py score /path/to/verified-custody.json /path/to/predictions.json /path/to/score.json
```

See the [interface, numerical recipe and source gates](../../docs/initial-evaluator-v1.md).
The tests contain generated engineering data only. `provenance.json` pins primary
source observations; `release_inventory.json` contains public metadata for all
223 assets in DANDI release `001075/0.240930.1859`, not data payloads.

Scientific qualification is **unknown** and submission readiness is **false**.
Authentic trace extraction, complete condition coverage, independent worm and ROI
identity joins, rights/exposure review and full scientific controls remain held.
Three imaging subjects lack segmentation partners. Source responses extend after
stimulation, so this is retrospective conditional reconstruction, not forecasting
before stimulation or a claim about direct synaptic connectivity. Numerical
choices are explicitly prospective and require acceptance before authentic use.

## Correlation arithmetic

Pearson correlation now centers independently scaled traces and takes the dot
product of their normalized vectors. The previous variance-product denominator
overflowed for identical traces at scale `1e100` (reporting zero correlation)
and underflowed at `1e-100` (raising division by zero). The metric, constant and
missing-support behavior, MSE, area and held-worm aggregation are unchanged.

The current participant transport pins the corrected evaluator bytes. Re-freeze
new custody artifacts against those bytes; a custody artifact bound to an older
evaluator is not interchangeable. No historical source/task definitions are
rewritten. `tests/test_correlation_scaling.py` adds three standard-library-only
controls with analytic correlation oracles across scales and verifies the actual
transport loader. These are generated software controls, not original-data or
model-performance evidence.
