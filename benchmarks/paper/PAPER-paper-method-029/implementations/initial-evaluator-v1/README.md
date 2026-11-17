# Deeprecon conversion evaluator

Source-grounded converter inference and complete 20-directed-pair pattern/profile correlation evaluation for `PAPER-paper-method-029`, with optional noise-ceiling normalization. Requires an existing Python/NumPy environment; the optional trusted H5 adapter also requires existing `bdpy`.

From this directory:

```sh
python3 ncc_evaluator.py evaluate /absolute/path/manifest.json --output /absolute/path/result.json
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Read [the task implementation documentation](../../docs/initial-evaluator-v1.md) for input schemas, source provenance, native adapter and remaining gates. No authentic fMRI/model execution or scientific qualification is established. Generated controls test numerical engineering behavior only.
