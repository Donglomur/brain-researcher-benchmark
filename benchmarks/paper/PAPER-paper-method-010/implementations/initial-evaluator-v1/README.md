# Rastermap prospective artifact evaluator

This package implements full-population held-out neighborhood retention,
behavior-to-superneuron ridge prediction, and paired tie-aware order stability
for the existing Rastermap task. It reads pinned processed source NPZ files and
frozen embedding artifacts; it does not train Rastermap or establish paper
reproduction, baseline competence, or scientific qualification.

Dependencies: Python 3.10+ and NumPy. Generated controls were run with Python
3.11.6 and NumPy 2.4.6; no dependencies were installed.

From this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p '*.py' -v
python3 evaluator.py /absolute/operator/request.json --output /absolute/operator/report.json
```

The CLI requires both the 137-neuron hippocampal and 34,086-neuron mouse source
roles, exact input hashes, a candidate, at least one baseline, and paired
repeat-seed plus neuron/time perturbation artifacts. It cannot download data or
execute submitted code. Native zero-variance exclusion, source preprocessing
reconciliation, empirical replay, protected references, rights, resource
measurement and admission gates remain open.

See the [full interface and scientific policy](../../docs/initial-evaluator-v1.md)
and [source provenance](provenance.json). The canonical task is unchanged.
