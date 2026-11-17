# Plexus initial evaluator

A Python 3.10+ standard-library evaluator for prospective complete52-gene/four-line held-plate predictions, calibration, blocked inference and paired batch uncertainty. No external dependencies are required. See [the task implementation documentation](../../docs/initial-evaluator-v1.md) for inputs, scientific policies, primary sources and unresolved gates.

From the repository root, set the working directory to this package before running either command:

```sh
cd benchmarks/paper/PAPER-CANDIDATE-20261114-PLEXUS/implementations/initial-evaluator-v1
python3 plexus_evaluator.py --manifest /absolute/approved-manifest.json \
  --manifest-sha256 APPROVED_CANONICAL_SHA256 \
  --submission /absolute/predictions.json --output /absolute/report.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Use `python3 plexus_evaluator.py --help` from the same directory for available arguments. The manifest hash must be independently frozen before evaluation. The tests use generated engineering controls; no authentic dataset/model execution or scientific qualification is claimed.
