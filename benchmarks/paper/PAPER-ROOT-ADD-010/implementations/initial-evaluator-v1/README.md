# Sensor RSA construction component

For PAPER-ROOT-ADD-010, compute run-crossvalidated shape RDMs from cleaned reference epochs, then separate symbolic and CORnet-S IT whitened correlations. The cohort command requires all 20 sensor subjects and the exact 158-run inventory; it returns both source smoothing branches, per-subject results, means and SEM.

Use an existing Python 3 environment containing NumPy and SciPy. MNE is optional for native epoch export and cluster inference; pytest runs the generated controls. No download or dependency installation occurs automatically.

```sh
python3 sensor_rsa.py import-models SYMBOLIC.csv CORNET_IT.csv models.json
python3 sensor_rsa.py evaluate packet.json result.json
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -q -p no:cacheprovider tests
```

Inputs are hash-pinned local NPZ files plus explicitly labeled model RDMs. See the [input format, source mapping and retained gates](../../docs/initial-evaluator-v1.md). The optional `export-epochs` command accepts already-cleaned MNE epochs; the `cluster_inference` Python function retains the source's temporal test settings.

This is a standalone numerical construction component. Raw-BIDS preprocessing, historical decoding, authentic reference agreement, paper-version reconciliation, protected evaluation and scientific qualification remain open. Every report preserves those limits. Tests use generated engineering controls, not scientific observations.
