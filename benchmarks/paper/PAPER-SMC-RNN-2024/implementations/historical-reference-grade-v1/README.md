# Historical SMC reference scoring

This operator-facing component scores two already-frozen released-author predictions on the original MC_Maze 20 ms task. It reuses the original evaluator and does not run a model, repeat inference, or train a candidate. It is a separate qualification route; it does not bypass or complete the participant/reference inference owner's gates.

Both prediction files are authenticated and copied into bounded private snapshots. Both original freeze records and complete output arrays are validated before either score call can read the TEST target. The unchanged scorer then reports co-bps, velocity R2, PSTH R2 and forward bps separately for the causal and noncausal references. The final report includes signed differences from authenticated historical scores.

One child owns the entire two-score workload: 2 GiB container memory (including tmpfs), one numerical thread, 600 CPU seconds soft/605 hard, and 720 seconds work plus 60 seconds cleanup. Host supervision has a separately declared 512 MiB allowance; this is not a hard host-memory guarantee. Success requires complete captures, known process closure and exact container removal. Unknown creation or closure remains unresolved.

## Inputs and execution

The host entry is `runtime/historical_grade.py --request HOST_REQUEST.json --sha256 HOST_REQUEST_SHA256`, invoked with qualified Python 3.11 and isolated mode. The request binds the runtime and adapter manifests, exact Docker executable/socket, four saved limited-runtime provenance records, a child request, fresh token and output root. The child request binds both original predictions/freezes, the original panel/protocol, historical scalar report, evaluator and target descriptors, and a fresh private output root.

These are trusted operator inputs. Caller flags do not establish runtime qualification. Source manifests, original scientific identities, saved provenance and fresh daemon/image/container checks remain mandatory. This source is bound to the declared retained environment; it does not provision or qualify another machine. No private requests, original predictions, targets or machine-specific evidence are included here. A separately selected actual operation must supply fresh resources, exact requests and runtime admission.

Image admission uses the exact retained semantic configuration. Only the nine declared Docker defaults may be omitted: `AttachStderr`, `AttachStdin`, `AttachStdout`, `OpenStdin`, `StdinOnce`, `Tty` (all `false`), and `Domainname`, `Hostname`, `Image` (all empty strings). Present values must have those exact JSON types and values. No undeclared key is discarded; image ID, parent, layers, size, labels and every other configuration value remain exact. This representation rule does not change the image or qualify scientific execution.

## Source controls

Run the standalone controls with standard-library Python 3.11 on Unix. Set `ARTIFACT_DIR` to a fresh absolute canonical path outside Git worktrees and disjoint from `runtime`, `adapter` and `controls`; its parent must exist.

```sh
ARTIFACT_DIR=/absolute/fresh/artifacts python3.11 -I -S -B controls/test_historical_grade.py -v
```

There are 12 methods: the retained 11 controls plus one image-admission regression. The latter exercises the real admission callsite using generated and sanitized metadata, including permitted omissions, strict types, changed values and unexpected fields. Standard unittest counts go to stderr; a compact JSON summary and `CONTROL_RESULT.json` report cumulative generated fixture writes, including rewrites/deletions. The numerical scorer, OS limits and Docker are explicit doubles. The retained 11-method campaign and the separate focused policy regression are distinct source evidence; adding the regression does not turn them into a new scientific run. These controls do not qualify numerical equivalence, native containment or original-data scoring.

## Interpretation

The output is historical/current released-checkpoint reference calibration, not exact reconstruction of the paper's checkpoints or data revision. The historical noncausal score was accepted while its supervisor identity failure remained failed; this route preserves that distinction. Neither the old diagnostic 0.01 tolerance nor printed rounding is a new equivalence criterion. The 32 trajectory sets are inference averaging, not independent trained-model or biological replication. No AI performance, improvement or SOTA claim follows from this component.
