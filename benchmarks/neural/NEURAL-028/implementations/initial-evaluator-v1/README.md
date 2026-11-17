# NEURAL-028 initial signal evaluator

Computes source-grounded stimulus and reward-location selectivity, prospective movement/position standardized selectivity, paired animal contrasts and bootstrap intervals, gray-baseline activity, whole-trial null diagnostics, and a before-only leave-animal-out explanatory reference with full held-out residuals. The input is an explicitly mapped neural/behavior array packet with a complete declared session manifest.

The [task scope, input schema and scientific policies](../../docs/initial-evaluator-v1.md) distinguish pinned author definitions from prospective benchmark choices and map implementation coverage to the immutable task contract. [Source provenance](source-provenance.json) records the exact author revision and primary paper.

## Run

Use an existing Python 3 environment with NumPy; no installation or network access is performed. From this package directory:

```sh
python3 -m unittest discover -s tests -v
python3 evaluator.py /absolute/path/packet.json --output /absolute/path/result.json
```

The 26 tests use generated engineering controls. They cover source arithmetic and reward-window definitions, malformed populations/arrays, held-out animal and phase leakage, numerical degeneracy, trial nulls and the CLI.

## Limits

This is tested construction source, not an executed native benchmark. Authentic cohort/session mappings, source payload hashes/alignment, native interpolation, amplitude calibration, the behavior-matched reward endpoint, authentic reference/comparator execution, protected evaluation and scientific admission remain held. Declared evidence strings do not clear these gates. Undefined endpoints retain their biological denominators and are explicitly withheld. Public development data remain development-only; scientific qualification and submission readiness are unknown. No author code or neural payload is vendored.
