# Matched PopT versus BrainBERT RMS evaluation

This package freezes source-derived low/high RMS labels and evaluates paired predictions for all seven registered downstream subjects at nested electrode counts 1, 10, 50 and 90. It computes subject-specific ROC-AUC, separate semantic/source-class F1, paired differences, descriptive subject SEM, temporal-block uncertainty and electrode scaling. A native-array binding adapter verifies supplied row order and class mapping; a submission-interface exporter excludes targets.

Python 3.10+ standard library only. From this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 evaluator.py freeze operator-plan.json operator-reference.json
python3 evaluator.py interface operator-reference.json submission-interface.json
python3 evaluator.py score operator-reference.json candidate.json baseline.json scores.json
```

See [the complete input, source and policy documentation](../../docs/initial-evaluator-v1.md), including `bind-native` and a generated-control demonstration. Inputs named `operator-*` contain protected targets and must remain outside candidate packets.

This is a complete construction evaluator for an explicitly prospective RMS comparison. It does not run models, establish authentic inputs, reproduce historical splits, resolve checkpoint rights or qualify the whole task. Scientific qualification remains unknown; native/source/reference holds remain in every score output.
