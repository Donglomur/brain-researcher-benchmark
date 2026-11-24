# Fixed trusted Figure 3b reference driver

`operator_replay.py` is byte-identical to the guest driver that completed the [24 November reference](../../docs/provenance/trusted-figure3b-reference-20261124/README.md): 42 cells, 14 sessions, eight people and 5,685 fresh source Ridge fits. It is a fixed task-local operator route, not a participant executor or a general runner.

## Inputs and runtime

Use an existing Linux/arm64 runtime with **Python 3.11.3, NumPy 1.24.3, SciPy 1.10.1 and scikit-learn 1.2.2**. The driver refuses other versions and refuses loaded numerical pools with more than one thread. The exact measured image ID is in the [provenance](../../docs/provenance/trusted-figure3b-reference-20261124/PROVENANCE.json); that local content identity is not a claim that a downloadable image is published here.

The operator supplies these generic container paths:

| Guest path | Input or output | Contract |
| --- | --- | --- |
| `/source` | Read-only task directory | Must contain this task's existing `implementations`; exact 107 reused source identities are listed in the provenance. |
| `/driver/operator_replay.py` | Read-only driver | This file, unchanged. |
| `/driver/INNER.json` | Read-only protocol | The supplied fixed protocol, unchanged. |
| `/store` | Read-only selected original store | Existing complete `original_figure3b_improvement` store; authenticated manifest identity is fixed in `INNER.json`. No generated fixture or partial store qualifies. |
| `/provided/REFERENCE.json` | Read-only provided-author reference | This task's `docs/provenance/original-reference-20261117/REFERENCE.json`. |
| `/output` | Private writable directory | Empty before invocation; owned by the worker UID. Never commit its raw contents. |

The store is not bundled. Its existing [producer and reader contract](../original-figure3b-store-v1/README.md) describes preparation from authenticated original inputs. The measured store occupied 18,497,064 logical bytes. This driver does not download data or prepare another store. Use the selected immutable store and unchanged protocol; substituting a store hash is a different operation.

Before starting the interpreter, set `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, `BLIS_NUM_THREADS`, `VECLIB_MAXIMUM_THREADS` and `NUMEXPR_NUM_THREADS` to `1`, plus `PYTHONDONTWRITEBYTECODE=1` and `PYTHONHASHSEED=0`. The operator owns container/process deadlines and cleanup. The measured condition used one CPU quota, 3 GiB hard memory/no additional swap, a read-only root, no network, no capabilities, no-new-privileges, a 16 MiB `/tmp`, and only `/output` as a writable bind mount. Clear an inherited Docker entrypoint when supplying the full command below.

Inside that operator-owned runtime, invoke:

```sh
/usr/local/bin/python3.11 -I -B /driver/operator_replay.py --protocol /driver/INNER.json
```

This is the actual measured command with generic guest mounts. It does not independently supply the bounded host supervisor used for the reported run. An exit code or copied result alone does not establish owned-container closure or participant isolation. The measured operation allowed 14,400 seconds of work and 120 seconds for inner closure; the outer supervisor allowed 14,700 plus 180 seconds. No new supervisor is implemented in this package.

## Outputs and interpretation

The driver writes private prediction arrays, cell receipts and `RESULT.json`, using exclusive creation. It requires all 42 canonical cells and 5,685 source calls before producing the complete result. Standard output reports completion counts and a final result hash, never raw predictions or labels. The output cap is 32 MiB. The selected-store reader is bounded to 32 MiB logical reads and 128 MiB declared working admission; those reader counters are distinct from process RSS and repeated in-memory fit operands.

The trusted operator can access original targets for training and scoring; the fixed predictor receives only copied training labels for its held-qid fold. This does not isolate arbitrary submitted code. The historical PCA, response smoothing and public exposure remain unchanged. `candidate` in the reused reducer's packet is a mechanical interface role, not evidence of an AI candidate or an improvement. The driver reads the provided author reference only after all fits. All raw outputs remain private; publish only a reviewed aggregate with its precise scope.
