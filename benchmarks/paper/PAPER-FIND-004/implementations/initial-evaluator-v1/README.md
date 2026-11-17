# PAPER-FIND-004 initial evaluator

This Python standard-library component safely converts trusted native prediction dictionaries, recomputes pooled prior-decoding R², applies repeated-run pseudo-session inference and regional Fisher/BH summaries, and reports matched descriptive neural/motor comparisons. It requires the complete declared cell, trial, pseudo-session and repeat population.

The implemented endpoint follows generic defaults at author commit `380e7e68f31f9b55ec20e3f4863abec9eec25d30`. Those defaults differ materially from the journal methods. This is a construction component; authentic reference execution, paper reconstruction, data rights, protected assessment and scientific qualification remain open.

Dependencies: Python 3 standard library only. From this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 example_control.py /tmp/find004-control
PYTHONDONTWRITEBYTECODE=1 python3 evaluator.py /tmp/find004-control/manifest.json /tmp/find004-control/predictions.json --output /tmp/find004-control/result.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The example is generated engineering data, never authentic neuroscience evidence. The evaluator performs no data downloads, model fitting or pickle loading. See the [full task documentation](../../docs/initial-evaluator-v1.md) for source discrepancies, immutable input/export contracts, exact metrics and preserved holds; `provenance.json` binds inspected sources.
