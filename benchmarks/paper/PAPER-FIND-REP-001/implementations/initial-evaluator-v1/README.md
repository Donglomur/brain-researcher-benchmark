# PAPER-FIND-REP-001: Fig. 2f evaluator

This package computes the source-derived Fig. 2f endpoint from prepared, pinned
place-field `binF` exports: near/far population correlations, six fixed region
summaries, normalized learning curves, and equal-animal means and source SEM for
the eleven-animal Set A roster.

Requires Python 3.11+ and NumPy. From this directory, using an existing environment:

```sh
python3 evaluator.py /path/to/manifest.json /path/to/new-report.json
```

The manifest must supply all eleven animals, complete declared session ledgers,
and SHA256-pinned numeric NPZ files. Output must be a new file. The
[task documentation](../../docs/initial-evaluator-v1.md) specifies the full input
format, exact source algorithm, provenance, and validation evidence.

This is a prepared-export numerical endpoint, not a native fluorescence pipeline,
whole-paper reproduction, or qualified grader. Native export equivalence,
independent population completeness, authentic references, protected numerical
targets, broader state-versus-position analyses, and scientific qualification
remain held. Generated tests establish engineering behavior only.
