# NEURAL-095 — Produced interval prediction from pre-Set motor-cortex activity

Predict the released behavioral produced interval `tp`, in milliseconds, for every one of the 258 development cases. Training supplies the original 748 released training cases from the same Haydn 20161211 session. This is public historical development data, not an unseen final test or an animal-transfer evaluation.

At the observed Set event, the public inputs contain four left-inclusive/right-exclusive 50 ms spike-count bins covering `[Set−0.2s, Set)` from all 40 source held-in units. Set-boundary spikes are excluded. Public context includes the nominal sample interval, prior/response-effector/direction condition, and elapsed recording time. This is prediction **at Set**, not 200 ms before Set. Behavioral `tp` is retained as reported; it is not equivalent to the event-clock Go−Set interval. Exact hand-clock conversion remains unresolved. Neither online spike sorting nor causal neural information is established by this task.

Use only the public train/query NPZ files, schema, units and case identity referenced in `assets.json`. Training targets and five fixed training folds are public. Query targets, source NWB, Go/acquisition/reward times, source selection records, outcome flags and operator receipts are private. No source row is dropped because of its target or outlier status; all selected windows passed the fixed support and overlap gates.

Submit one NPZ with exactly two arrays:

- `case_id`: all 258 public development IDs exactly once, as a Unicode vector. Row order may differ.
- `prediction_ms`: matching float32/float64 finite scalar predictions. Negative finite predictions are allowed and are not clipped.

Files are limited to 1 MiB. The scorer inspects bounded ZIP/NPY structure before loading, rejects duplicate or extra arrays, incomplete or ambiguous IDs, linked/truncated files, pickle/object types and nonfinite values. Every public submission check completes before private targets load. Candidate code is never executed by this scoring command.

Primary output is trial-mean absolute error (MAE) in milliseconds. Outputs also retain RMSE, equal-weight mean MAE over all eight cue contexts, and all 40 sample×context groups. All groups and cases are required; none are silently dropped. Signed candidate-minus-reference differences are reported against the nominal-interval, condition-median, cue+clock ridge, total-spike ridge and temporal-spike ridge references. Negative error differences are better. **There is no scientific success threshold.**

The fixed total-spike reference had MAE 77.01 ms versus 78.96 ms for condition median; the temporal-spike reference was worse at 83.03 ms. These are development comparisons, not published SOTA. Three ridge arms selected regularization using training-only folds under the frozen recipe; no current candidate is constrained to reproduce their outputs. One animal/session does not support biological population confidence intervals or p-values from its trials.

After qualification, use `python3 tools/neurobench.py score NEURAL-095 --submission candidate.npz --output fresh-result.json`. Local scoring qualification is distinct from a full agent experiment, independent hidden evaluation, research qualification and submission readiness.

Data source: DANDI 000130, version 0.241017.1448, CC-BY-4.0; exact asset and scientific source lineage remain pinned in `assets.json` and the local `authoring/dmfc-timing/preset-pilot-v1` protocol.
