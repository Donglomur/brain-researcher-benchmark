# Risky-decision reactivation evaluator

Computes three localizer-trained outcome decoders, source-convention probability/reward reactivation effects, and a prospective nested participant-held-out comparison predicting behavioral parameters. It accepts explicit primitive numeric exports and preserves the full 21-participant roster, with source exclusions applied only to the second level.

Requires an existing Python 3.11 environment with NumPy and SciPy. Verified with Python 3.11.6, NumPy 2.4.6 and SciPy 1.17.1; the exact validation interpreter is recorded in external construction evidence. Select an existing environment that provides these dependencies. From this directory:

```sh
python3.11 evaluator.py /absolute/path/manifest.json /absolute/path/result.json
python3.11 -m unittest discover -s tests -v
```

The manifest and numeric NPZ schema, exact source semantics, prospective choices, and input example are documented in [the full implementation guide](../../docs/initial-evaluator-v1.md). The generated `tests/test_evaluator.py::write_packet` helper demonstrates the input format.

This is engineering source at an unqualified primitive-export boundary. Native MATLAB/MCOS conversion, authentic event and participant linkage, participant-independent behavioral target provenance, author scaling/solver equivalence, protected evaluation, grading targets and rights remain unresolved. Shared-prior behavioral target declarations and pickled/opaque arrays are rejected. Generated tests do not establish paper reproduction or scientific qualification; every result preserves unknown scientific readiness and false qualification/reproduction flags.
