# Brain Treebank word-responsiveness component

Computes five fixed paired pre/post word-response tests from processed 2048 Hz epochs, merges all declared runs per electrode, reports matched minimum-p/effect values, and applies an explicitly prospective global Bonferroni correction. This implements one substantive endpoint of `PAPER-paper-method-replacement-011`.

Requires Python 3.10+, NumPy and SciPy. Engineering checks used Python 3.12.8, NumPy 2.4.6 and SciPy 1.17.1. Use an existing environment with these dependencies; this package neither installs dependencies nor downloads data.

From this directory:

```sh
python -B evaluator.py /absolute/manifest.json --input-root /absolute/inputs --output /absolute/result.json
python -B -m unittest discover -s tests -v
```

See the [input schema, source provenance and endpoint documentation](../../docs/initial-evaluator-v1.md). The tests contain a complete generated-input builder. Input NPZ files and word/electrode/run identities are checked against the declared manifest; missing units or shortened windows fail.

This is a processed-epoch component, not a native loader or complete paper benchmark. Authentic population and preprocessing, temporal dependence, joint acoustic/visual/speaker/scene adjustment, sentence-position effects, time-resolved decoding, protected evaluation, reference agreement and source/stimulus rights remain unresolved. Generated controls establish engineering behavior only. All scientific qualification and full-contract flags remain false.
