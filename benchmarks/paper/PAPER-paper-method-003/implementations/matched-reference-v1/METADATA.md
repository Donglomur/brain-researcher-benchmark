# REVE metadata commands

These commands validate public metadata using the REVE validators.
They do not import the model stack, read arrays or checkpoints, admit execution,
or verify that a claimed fit occurred. Source hashes bind the selected validators.

Use independently selected hashes and identities from your trusted preparation
record, not values copied from an untrusted submission.

```sh
python3 -I -B metadata.py prepare-info \
  --manifest /absolute/path/materials.json \
  --manifest-sha256 MANIFEST_SHA256 \
  --materials-identity MATERIALS_IDENTITY \
  --panel-identity SOURCE_PANEL_IDENTITY \
  --output /absolute/path/new-info.json

python3 -I -B metadata.py check-fit \
  --info /absolute/path/new-info.json \
  --info-sha256 INFO_SHA256 \
  --fit-receipt /absolute/path/fit.json \
  --fit-identity FIT_IDENTITY
```

`prepare-info` accepts the canonical JSON encoding committed by the existing
packet ABI and creates a fresh info file. It validates the full 6,300 / 1,734 /
1,803 split census, permitted labels and opaque test identities. It does not
authenticate the referenced signal bodies, geometry, paper, code or weights.

`check-fit` assumes an independently admitted info file and checks a complete
receipt against the independently selected profile. A successful check reports
`metadata_valid`; it is not a training result or checkpoint-body authentication.
Omitting `--profile` preserves the original `cuda-fp16` default. Checking an
explicit prospective CPU receipt requires `--profile cpu-fp32-math`; its full
recipe, exact runtime versions and math-attention declaration must match.
The command does not infer the profile from a submission. CPU receipts fail
CUDA-default checking, and CUDA receipts fail CPU checking. A compatibility-only
receipt is rejected under both profiles because it lacks a complete fit trace.
Neither profile authenticates historical Table 12 or admits a scientific run.

Run the small generated boundary tests with a fresh scratch directory:
```sh
python3 -I -B metadata_tests.py /absolute/path/new-metadata-test-scratch
```

The tests use synthetic manifests and receipts, forbid scientific imports and
payload access, and retain at most 2 MiB of generated metadata. Synthetic receipt
metrics are test fixtures, not measured neuroscience performance.
