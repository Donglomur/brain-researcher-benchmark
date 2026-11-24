# Measured fixed nested-Ridge operator arm

`operator_candidate.py` is byte-identical to the driver that completed the [negative comparison](../../docs/provenance/trusted-figure3b-nested-ridge-20261124/README.md). It reuses the existing original reader, outer split, unchanged [nested-Ridge candidate](../original-nested-ridge-v1/README.md), and endpoint reducer. It adds no general runner or participant execution provider.

## Generic operator inputs

The operator must supply an existing Linux/arm64 runtime with Python 3.11.3, NumPy 1.24.3, SciPy 1.10.1 and scikit-learn 1.2.2. Exact measured source and runtime identities are in [PROVENANCE.json](../../docs/provenance/trusted-figure3b-nested-ridge-20261124/PROVENANCE.json). The measured local image ID is an identity, not a published download location.

| Guest path | Operator-supplied contract |
| --- | --- |
| `/source` | Read-only task directory containing the exact listed 107 reused implementation files. |
| `/driver/operator_candidate.py` | This byte-identical driver, read-only. |
| `/driver/INNER.json` | This frozen protocol, read-only. |
| `/store` | Existing complete authenticated selected original store; its manifest hash is fixed in the protocol. |
| `/reference/RESULT.json` | Exact retained private result of the completed fresh fixed-alpha A3 reference, matching the protocol's byte count and hash. |
| `/output` | Empty private writable output directory, owned by the worker UID. |

The [reference route](../trusted-figure3b-reference-v1/README.md) describes the prior fixed-alpha execution. This package does not distribute its private full result or the selected store. A new reference execution has its own timing/provenance bytes and cannot be substituted for this pinned artifact; a separately admitted binding is required. The present route is usable by the operator holding the authenticated inputs. It is not a self-contained public or participant benchmark.

Set `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `BLIS_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS` and `NUMEXPR_NUM_THREADS` to `1`; also set `PYTHONDONTWRITEBYTECODE=1` and `PYTHONHASHSEED=0`. The driver checks the historical versions and actual loaded thread counts. Run inside an operator-owned bounded container with one CPU, 3 GiB hard memory/no extra swap, no network, read-only root and input mounts, no capabilities, no-new-privileges, a 16 MiB `/tmp`, and only `/output` writable. Clear an inherited entrypoint before supplying the full command:

```sh
/usr/local/bin/python3.11 -I -B /driver/operator_candidate.py --protocol /driver/INNER.json
```

The measured host supervisor is not reimplemented here. Its inner work/closure limits were 1,800/120 seconds and outer limits 2,100/180 seconds. The operator must own process deadlines, container cleanup and closure evidence; a result file or exit code alone does not establish containment.

## Completion and custody

The frozen candidate receives copied outer-training feature/target matrices, query features and training-group metadata. The trusted operator has target access for scoring; this does not isolate arbitrary submitted code. The exact `Ridge.fit` code observer counts entries/returns only, ignores other events, retains no frames/operands, and does not patch the estimator. Its overhead is included in measured wall time.

Completion requires all 42 cells, 5,685 requests and 90,960 fits. Progress reports distinguish requests from fits. The provided fresh-reference file is authenticated and loaded only after all candidate fitting. The driver writes private prediction arrays, cell receipts and a complete result, capped at 32 MiB. Never commit those raw outputs. Publish a separately reviewed aggregate with original weighting, all outcome directions, exposure limits and the explicit distinction between the fresh reference and reused reducer role names.
