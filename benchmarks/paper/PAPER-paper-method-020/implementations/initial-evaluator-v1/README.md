# BOLD5000-QA assessment construction

This package implements the full official CSI1 inventory audit, a label-blind stimulus/person identity audit, safe model-input projection, isolated neural/zero-neural/shuffled-neural packet preparation, and an exhaustive structured-answer QA scorer. It is a construction component; it does not implement NEURONA training or establish a native reference or a scientifically qualified benchmark.

Python 3.10+ standard library is sufficient. Run from this directory:

```sh
python3 evaluator.py inventory ../../task.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
python3 evaluator.py audit-identities ../../task.json identities.json
python3 evaluator.py prepare ../../task.json identities.json trusted-records.json operator-output --shuffle-seed frozen-seed --id-salt at-least-16-secret-characters
python3 evaluator.py score operator-output/protected.json runs.json vocabulary.json
```

The production inventory is exactly 4,802 train plus 84 test NPY paths. Trusted neutral-format conversion and stimulus identity evidence must be supplied independently. This package never deserializes native pickled NPY records, downloads data, calls a language model, or fits a decoder. The generated controls exercise engineering behavior only.

`operator-output` is operator-only. Release exactly one arm JSON file to each isolated inference environment; retain `protected.json` and all other arms outside it. The same trained model and shared training data are used for the three inference arms. Zero-neural is a prospective all-zero `[5,1024]` ablation; it does not constitute an independently trained language-only baseline. A field allowlist cannot prove the absence of answer cues inside query text.

See [the complete interface, scientific distinctions and retained gates](../../docs/initial-evaluator-v1.md) and [source provenance](provenance.json).
