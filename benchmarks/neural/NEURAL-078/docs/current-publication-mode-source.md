# Current NEURAL-078 public-mode source inspection

The selected [current source manifest](../../../integrity/current-closures/input-neural078/SOURCE_MANIFEST.json) is the accepted public-directory permission successor: 6,014 bytes, SHA256 `a681a439e234e2584fcc6797043d670791bc1939c54d25596819f7a5bc2d0637`. It retains the same 37-member source roster and the original historical manifest while selecting the repaired producer and loader identities. Newly owned public directories are finalized to `0755` under restrictive `umask 077`; private defaults and fail-closed ownership checks remain unchanged.

The [preceding inspection note](current-source-inspection.md) is preserved verbatim as evidence for the earlier source selection. Its examples describe that earlier revision. The immediate central predecessor is preserved exactly in [the repair history](../implementations/publication-mode-repair-v1/history/SOURCE_MANIFEST.pre-publication-mode-repair-v1.json): 6,014 bytes, SHA256 `147d12c27da182604f7f69a943a8ca35a1acb939e3491c233af1cec8d9d392e3`.

From a canonical absolute checkout path without symlink ancestors, Python 3.11 or later can inspect the selected source without a dataset, protected reference or Docker service:

```sh
PKG="$PWD/benchmarks/neural/NEURAL-078/implementations/neural078-deferred-grade"
CURRENT="$PWD/benchmarks/integrity/current-closures/input-neural078/SOURCE_MANIFEST.json"
python3 -I -S -B "$PKG/verify_source.py" verify \
  --source-manifest "$CURRENT" --source-bytes 6014 \
  --source-sha256 a681a439e234e2584fcc6797043d670791bc1939c54d25596819f7a5bc2d0637
python3 -I -S -B "$PKG/score_artifact.py" inspect \
  --source-manifest "$CURRENT" --source-bytes 6014 \
  --source-sha256 a681a439e234e2584fcc6797043d670791bc1939c54d25596819f7a5bc2d0637
```

These are source-inspection commands. The accepted generated permission controls do not establish Docker behavior, authentic-data correctness, participant isolation, native runtime qualification or scientific outcomes. The existing reaction-time validation revision still requires a separately admitted numerical/reference binding; this permission repair does not authorize the updated numerical source against the old protected reference. Original historical manifests, current task criteria, runtime-selection states and broader execution holds remain unchanged.
