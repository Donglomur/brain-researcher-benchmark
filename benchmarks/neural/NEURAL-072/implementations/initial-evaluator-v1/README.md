# NEURAL-072 prospective held-story contrast evaluator

This package fits nuisance, lexical and contextual encoders separately within each listener, then independently scores signed held-out variance contrasts. It binds inputs to a frozen NEURAL-071 case manifest, checks story/passage/scan separation and causal feature support, matches lexical/contextual effective capacity, and reports listener/story-family uncertainty plus a temporal alignment diagnostic.

Use an existing Python 3 environment with NumPy. No recordings, checkpoints, downloads or dependency installation are included. From this package directory:

```sh
python3 evaluator.py predict --protocol protocol.json --cases cases.json --features features.json --targets train_dev_targets.json --output predictions.json
python3 evaluator.py score --protocol protocol.json --cases cases.json --targets protected_test_targets.json --predictions predictions.json --output report.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The JSON inputs are externally prepared, frozen matrices and manifests. Test targets enter only the scorer. The [detailed scope and input contract](../../docs/initial-evaluator-v1.md) specifies fields, prospective model/metric choices, exact provenance and required admission reviews; `provenance.json` records inspected source identities.

This is a prospective engineering implementation, not an author encoder reproduction or a scientifically qualified benchmark. Generated controls establish code behavior only. Authentic NEURAL-071 membership and the full population, native scan/transcript/HRF clocks, atlas and checkpoint lineage, a strong predictive reference, rights, protected execution and resource admission remain unresolved. The temporal null is an alignment diagnostic, not a calibrated significance test. Reports retain scientific and submission holds.
