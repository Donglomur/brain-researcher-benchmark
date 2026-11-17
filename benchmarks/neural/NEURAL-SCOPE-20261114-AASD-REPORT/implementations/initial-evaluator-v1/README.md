# AASD report-state evaluator

This independent construction package prepares exact report-state labels and common EEG contexts, accounts for all 18 participants and 1,260 active/passive trial slots, generates 54 held-participant/held-mixture split cells, and scores participant-macro balanced accuracy after pooling mixture folds within each participant, probability metrics, passive motor diagnostics and paired participant uncertainty.

Requires Python 3.10+ and its standard library; no installation or network access is needed. From this package directory:

```sh
python3 aasd_evaluator.py prepare INVENTORY.json --output PREPARED.json
python3 aasd_evaluator.py split INVENTORY.json --output SPLITS.json
python3 aasd_evaluator.py score INVENTORY.json --predictions PREDICTIONS.json --comparator COMPARATOR.json --output SCORES.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

`--comparator` is optional. Inventory, prepared labels, split plans and scores are evaluator-owned. Predictions must cover every eligible active and passive case. The package consumes an explicitly normalized inventory; it does not read native MAT recordings, train models, enforce protected execution, or establish attention specificity. Native census, clock/channel/stimulus alignment, rights, competent baselines and scientific qualification remain unresolved. Generated tests demonstrate engineering behavior only.

See the [complete interface, scientific semantics, source provenance and retained holds](../../docs/initial-evaluator-v1.md). The registered task remains `NEURAL-SCOPE-20261114-AASD-REPORT`, an alias of specification `HOLD-NEURAL-FRONTIER-AASD-20261114`; this package adds no task count.
