# Running a submitted NEURAL-095 program locally

This operator guide supplements the frozen scoring README. The independently qualified local runner accepts a single Python program and computes its score after execution. It is one development task on one historical macaque session; it is not a hosted release, full investigator-mode implementation or model capability result.

From the repository root, inspect the command without executing the candidate:

```sh
python3 tools/neurobench.py run NEURAL-095 --program /absolute/program.py --output /absolute/repository/artifacts-build/fresh-attempt --dry-run
```

The output directory must be new and below this repository's `artifacts-build`. Omit `--dry-run` for an actual operator-allocated attempt after checking its full compute and storage reservation. The recorded construction allowance was consumed by qualification and does not allocate future attempts. The current registered command uses a 110-second whole-call limit, including cleanup, and a 20-second candidate work limit. Its literal reservation covers 4 MB for this attempt plus 2 MB for concurrent bookkeeping; update the reviewed invocation before a run if other unmaterialized reservations exceed that amount.

The runner invokes the submitted file inside the fixed offline Python image:

```sh
python -I /program/program.py --input /input --out /output
```

The only task inputs are `train.npz`, `query.npz`, `schema.json` and `units.json` under `/input`; the exact names and hashes are in the runner's public asset inventory. The program must write only `/output/submission.npz`, containing the `case_id` and finite `prediction_ms` arrays defined in the scoring README. The Python source is limited to 64 KiB and the output to 1 MiB. There is no network, private-target mount, host repository or Docker socket. Runtime dependencies are fixed; installing packages during the attempt is unsupported.

The program's snapshot and hash are committed before the four public files are released. Each attempt uses fresh scratch/output storage. The candidate is stopped and removed before output capture, and all candidate resources are removed before private numerical scoring. The scorer retains continuous errors and signed comparisons; no positive neural gain is required for a valid submission. Inspect `outer_execution.json` and the linked attempt receipts to distinguish a valid score from candidate failure, malformed output or operator failure.

The actual qualification recomputed condition-median predictions from training data (MAE 78.964 ms), rejected a malformed output with a lingering child, rejected a private-path probe without output, and passed an interrupted-wrapper recovery check. The earlier failed recovery test remains in the evidence. See [qualification results](../../../authoring/dmfc-timing/program-runner-v2/RESULTS.md) and [public program contract](../../../authoring/dmfc-timing/program-runner-v2/PUBLIC_INSTRUCTIONS.md).

These commands currently require this checkout's pinned local assets and Docker image. An acquisition/build rehearsal on a clean host and a downloadable release bundle remain unverified. Do not distribute the operator asset map or private targets as the candidate packet.
