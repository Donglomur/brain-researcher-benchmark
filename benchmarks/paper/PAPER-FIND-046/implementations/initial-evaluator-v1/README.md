# PAPER-FIND-046 initial evaluator component

This package computes source-derived Figure 2 rat stage contrasts, serum
session dopamine AUC differences and descriptive estradiol correlation. It
retains a full session/exclusion ledger and audits the declared Figure 1–3
rat/session relationships. It is a construction component; no empirical
reproduction or benchmark qualification is established.

Requires Python 3.10+ and its standard library. From this directory:

```sh
python3 evaluator.py export.json --output report.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The input must be an explicit native-shaped JSON export or a labeled
generated engineering control. The package does not download archives, read
MAT files, fit models or run Figure 3 RPE/history analyses. Native population,
export parity, protected references, numerical tolerances, grouped assessment,
rights and resource qualification remain unresolved gates.

See the [full scientific contract, input interface and limitations](../../docs/initial-evaluator-v1.md).
`sources.json` records the exact primary-source revision and file hashes;
`SOURCE_LICENSE.txt` preserves the source code’s MIT notice.

## Correlation scale stability

The descriptive serum Pearson correlation rescales each complete vector by its
own largest absolute value before centering, then normalizes the two centered
norms separately. This preserves the same Pearson statistic while avoiding
overflow or underflow caused solely by the units of otherwise finite inputs.
Missing values, constant vectors, fewer than two sessions and all existing
cohort or scientific qualification limits retain their previous treatment. The
focused `tests/test_correlation_scale.py` regressions cover independent unit
scales and the public `evaluate` serum route with generated inputs only.
