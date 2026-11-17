# NEURAL-027 initial evaluator

This prospective engineering reference converts decoded calcium frame data into fixed trial/position packets, fits an animal-disjoint training-only neural decoder and movement/position comparator, and reports mouse-macro log loss and balanced accuracy by exposure phase with paired mouse uncertainty.

Requires Python 3.11+ and NumPy. From this directory:

```sh
python3 evaluator.py --plan /absolute/path/plan.json --session-dir /absolute/path/safe-exports --output-dir /absolute/path/results
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The operator supplies a frozen session/animal/phase plan and non-pickled numeric/string NPZ exports. The CLI writes an operator-private report, predictions, and an allowlisted public query. See the [full protocol, input schema, source provenance, and limits](../../docs/initial-evaluator-v1.md).

Scientific qualification remains **unknown**. Generated controls establish engineering behavior only. Authentic source population and alignment, original-NPY intake/export equality, position units, anatomical calibration, rights, protected evaluation, and scientific admission remain unresolved. This is not an author-decoder reproduction, a native-data result, or an independent cohort from PAPER-FIND-REP-007.
