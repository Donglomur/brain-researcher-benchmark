# Figure 2 metric component

This package independently implements the pinned Herber2024 spatial stability
and three context-specificity calculations, then computes an explicitly
prospective mouse-level summary. It accepts admitted, binned spike counts and a
separately frozen complete roster with classification masks. It is **not** a
whole-paper reproduction, native importer, verified classifier, protected grader,
or scientifically qualified benchmark.

See [the implementation documentation](../../docs/initial-evaluator-v1.md) for source mapping, input semantics,
limitations, and the distinction between original and prospective calculations.

Existing NumPy and SciPy are required. No installation or data download is done.

```sh
python evaluator.py input.json roster.json output.json --seed 0 --bootstrap-replicates 1000
PYTHONDONTWRITEBYTECODE=1 python -m pytest -q -p no:cacheprovider tests
```

`tests/test_evaluator.py::make_packet` defines a complete **generated engineering
fixture**, not an empirical dataset. Its masks are examples, not author results.

The implementation is original code describing mathematical operations; no
upstream notebooks, figures, data, or source code are redistributed. Scientific
attribution: Herber CS, Pratt KJB, Shea JM, Villeda SA, Giocomo LM (2025),
*Spatial coding dysfunction and network instability in the aging medial
entorhinal cortex*, Nature Communications 16, 8770,
https://doi.org/10.1038/s41467-025-63229-0. Source recipe inspected at
GiocomoLab/Herber2024 revision `1a9dd3040c9f77662caf26a34c9452403579087a`.
