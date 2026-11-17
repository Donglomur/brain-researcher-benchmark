# Integration–segregation evaluator

Computes the source-defined 100-threshold integration, segregation and ISD metrics from matched GSR/noGSR regional BOLD; produces complete-participant paired state contrasts, connectivity/amplitude/motion controls and phase-randomized null comparisons.

Requires Python 3.10+, NumPy and SciPy already installed. From this directory:

```sh
python evaluator.py /absolute/path/manifest.json --output /absolute/path/report.json
PYTHONDONTWRITEBYTECODE=1 python -m unittest discover -s tests -v
```

The manifest, normalized NPZ boundary, source versions, scientific assumptions and examples are described in the [task implementation guide](../../docs/initial-evaluator-v1.md). No data or dependency installation is performed.

This is an unqualified source implementation with a prospective paired-state input boundary, not an empirical reproduction or finished grader. It retains the source correlation diagonal, so segregation can exceed one. Original BCT identity and MATLAB parity remain unresolved. Dataset-4 admission is held; Dataset-5 unequal stage lengths are rejected; one declared state pair does not cover all Datasets 3–5 conditions. Every report retains scientific holds and `scientifically_qualified: false`. Generated controls establish engineering behavior only.

New Python source is licensed GPL-3.0-only; see `LICENSE` and `provenance.json` for attribution and precise reuse limits. No author/BCT code or participant data are vendored.
