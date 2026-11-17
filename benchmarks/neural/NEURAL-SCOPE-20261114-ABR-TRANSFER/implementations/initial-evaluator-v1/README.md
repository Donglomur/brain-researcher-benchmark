# ABR transfer threshold evaluator

This construction package implements equal-animal threshold error, a complete
prediction/failure ledger, uncensored secondary metrics and paired whole-animal
bootstrap intervals. It also audits the distinct published-paper and pinned
historical threshold aggregation rules. It does not contain native data, author
code, pretrained weights or a waveform prediction model.

Use Python 3.10 or newer and its standard library; no installation is required.
From this package directory:

```sh
python3 abr_evaluator.py --reference generated-reference.json \
  --predictions generated-predictions.json --baseline generated-baseline.json \
  --bootstrap-replicates 2000 --seed 0
```

The baseline argument is optional. Input schemas, generated examples, report
fields, exit codes and test commands are documented in the
[full evaluator guide](../../docs/initial-evaluator-v1.md).

Only explicitly generated engineering controls receive aggregate scores.
Unverified prepared references require all 104 animals and the 54/50 background
roster, then remain score-blocked. Missing or invalid required predictions
withhold the aggregate; finite abstained predictions remain in the loss.
Native population and annotation authentication, physical units, protected
evaluation, rights, competent baselines and scientific qualification remain
open. Passing engineering tests or receiving exit code 0 does not admit an
authentic benchmark score.
