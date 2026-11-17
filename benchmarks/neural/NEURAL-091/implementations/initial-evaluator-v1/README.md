# NEURAL-091 initial evaluator

Python 3.9+ standard-library exposure-aware preparation, train-only controls and mouse-macro
Poisson bits/spike scoring for a frozen Allen Neuropixels export. Construction
component only; authentic cohort, native adapter, reference, rights and scientific
qualification gates remain open.

Read [the interface and policies](../../docs/initial-evaluator-v1.md).
From this package directory, prepare the pinned export, generate controls, and
score an exact keyed prediction list:

```sh
python3 evaluator.py prepare --bundle bundle.json --protocol protocol.json --public public.json --private private.json
python3 evaluator.py controls --public public.json --output controls.json
python3 evaluator.py score --public public.json --private private.json --predictions predictions.json --output score.json --bootstrap-seed 0
```

The guide defines `bundle.json` and `protocol.json`. `controls.json` contains two
named prediction lists; select one as `predictions.json`, or supply your own
compatible predictions. Keep `private.json` and the source bundle inaccessible to
the prediction process. These commands do not acquire recordings or qualify an
authentic benchmark. Python 3.11.6 was used for the recorded engineering checks.

Run generated engineering controls with:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -p 'test_*.py' -v
```
