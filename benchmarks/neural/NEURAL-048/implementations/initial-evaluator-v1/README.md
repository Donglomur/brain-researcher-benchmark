# NEURAL-048 initial evaluator

This component scores matched behavior-only, neural-history and time-shifted neural-history probabilities for dorsal versus ventral postreversal turns. It reports equal-worm natural-log-loss improvement and paired worm uncertainty, with complete declared episode coverage and whole-worm split checks. A separate callable builds histories using exact clocks and causal support/availability checks.

Requires Python 3.10+ and the standard library; no installation is needed. From this directory:

```sh
python3 evaluator.py operator-reference.json matched-predictions.json --output report.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

See the [full interface, prospective scoring policy and source mapping](../../docs/initial-evaluator-v1.md). The scoring CLI does not execute or certify the separate history builder, native preprocessing, model fitting or resource receipts. Generated controls establish engineering correctness only. Native source conversion, animal identities, causal alignment, rights, authentic references, protocol freeze and scientific admission remain unresolved; this is public development source, not a scientifically qualified or submission-ready benchmark.
