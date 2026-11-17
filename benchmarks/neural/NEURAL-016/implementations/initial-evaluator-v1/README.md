# NEURAL-016 initial evaluator

Recompute paired held-out nuisance/full encoding contrasts from frozen processed
targets and predictions. Outputs distinguish incremental explained variance from
incremental R², summarize blocks/electrodes/participants, and include paired
participant uncertainty. Protocol checks cover the complete 26-recording roster,
declared person/movie separation, temporal guards and exact prediction IDs.

Requires Python 3.10+ and an existing NumPy installation. From this directory:

```sh
python3 evaluator.py --protocol /operator/frozen-protocol.json \
  --private-targets /operator/private-targets.json \
  --submission /operator/paired-predictions.json --output /operator/private-score.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Paths above are placeholders. `tests/test_evaluator.py::packets()` provides a
complete generated input example; dummy pins and exclusions are engineering
fixtures. `controls.py` provides a joint linguistic circular shift for uniform
time grids, with explicit stationarity and conditional-null limits.

This is a prospective evaluator, not an executed native reference or qualified
benchmark. Authentic intake, full-population/electrode validation, actual fit
verification, rights/privacy, clinical cross-person electrode mapping and
protected evaluation remain open. All evaluation output stays operator-private.

See [the full protocol, provenance and preserved holds](../../docs/initial-evaluator-v1.md).
