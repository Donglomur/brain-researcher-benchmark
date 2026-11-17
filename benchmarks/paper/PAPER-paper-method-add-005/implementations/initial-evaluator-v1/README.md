# AJILE12 reconstruction evaluation component

See [the task documentation](../../docs/initial-evaluator-v1.md) for exact inputs, source provenance, prospective metric definitions, commands and scientific holds. This package prepares a complete 12-participant × 15-mask panel, exports one isolated case at a time, computes train-only mean/ridge baselines and scores privately held reconstruction targets. It does not train diffusion models or claim authentic scientific qualification.

Runtime dependency: NumPy. Optional native NetCDF conversion requires an already installed xarray/backend; that route has not been run on authentic data. No installation is performed.

From the repository root, inspect the evaluator commands and run this package’s generated engineering controls:

```sh
python3 benchmarks/paper/PAPER-paper-method-add-005/implementations/initial-evaluator-v1/evaluator.py --help
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s benchmarks/paper/PAPER-paper-method-add-005/implementations/initial-evaluator-v1/tests -v
```
