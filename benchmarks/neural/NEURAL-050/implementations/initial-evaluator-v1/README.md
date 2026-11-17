# NEURAL-050 prospective development evaluator

Runnable bounded raw-array preparation, grouped state/time versus gamma ridge comparison, paired patient/day scoring, matched-event contrasts and a day-shift diagnostic. Read [the task documentation](../../docs/initial-evaluator-v1.md) before using it. All scientific admission gates remain unresolved.

```sh
python3 evaluator.py prepare raw-manifest.json feature-packet.json
python3 evaluator.py evaluate feature-packet.json report.json
python3 -m pytest -q tests
```

Python 3.10+ and NumPy are required; pytest is used for generated engineering controls. No authentic data, remote downloads or model runs are included.
