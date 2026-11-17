# Source-peak beta amplitude analysis

`beta_evaluator.py` evaluates trial-resolved 13–30 Hz Hilbert amplitudes at the native index and pinky source peaks. It includes full-cohort accounting, primary code and paper-equation normalization profiles, age/covariate models, participant uncertainty, matched-trial analysis and local shift diagnostics.

Read [the complete boundary, interface, scientific semantics and holds](../../docs/initial-evaluator-v1.md) before using this package. This is downstream construction source; native reproduction and scientific qualification remain unresolved.

Dependencies: Python 3.11+, NumPy and SciPy; use existing installations. Run the generated controls from the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3.11 -m unittest discover -s benchmarks/paper/PAPER-paper-signal-add-005/implementations/initial-evaluator-v1/tests -v
```

From the repository root, inspect the interface or evaluate an existing manifest:

```sh
python3.11 benchmarks/paper/PAPER-paper-signal-add-005/implementations/initial-evaluator-v1/beta_evaluator.py --help
python3.11 benchmarks/paper/PAPER-paper-signal-add-005/implementations/initial-evaluator-v1/beta_evaluator.py /absolute/input/manifest.json /absolute/output/report.json
```

The `python3.11` command must resolve to an existing environment with NumPy and SciPy; substitute a compatible `python3` command if needed. The manifest must list all 53 participant dispositions and pin the 51 included participants' NPZ envelopes; see the linked documentation for the exact schema and scientific prerequisites.
