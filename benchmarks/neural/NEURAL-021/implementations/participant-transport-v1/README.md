# NEURAL-021 participant message transport

This component connects the existing exact-count visual session to a participant process through bounded messages. It preserves the original task: 272 calibration trials are available, all 92 query trials require one immutable 30-by-2 velocity prediction in m/s, and the original session outputs are replayed by the existing grader. It adds no benchmark and changes no scorer, programme profile or readiness gate.

## Conditions and scientific limits

`direct_observation` exposes complete SVG observations. `typed_viewer` also permits explicit unit/time-bin crops after a complete query view. Calibration views are optional and recorded. The entire original query support remains mandatory in both conditions.

The participant receives UTF-8 SVG text/vector content. A model could parse that text: this is **not a qualified raster-vision presentation**. The message API keeps arrays and paths operator-side, but a local child retains host filesystem and computation capabilities. The pipe is **not an OS sandbox or evidence of tool-free/native understanding**. An evaluation making those claims needs separately qualified capability isolation and presentation. The existing programme condition remains separate.

`fixed_response_client.py` is an engineering control: it requests all 272 calibrations and all 92 query views, submits zero velocity trajectories, and exits. `--crop-first` adds one crop in the typed-viewer condition. It is not an AI participant, trained predictor or scientific baseline. This client has not yet been executed against authentic data in this construction stage.

## Wire contract

Each message is a four-byte unsigned big-endian body length followed by UTF-8 JSON. Requests are nonempty and at most 8,192 bytes; responses are at most 524,288 bytes. The operator sends one hello, then each request must wait for its complete response. Sequence numbers start at zero and increase exactly once per accepted request. Unknown/extra fields, duplicate JSON keys, nonfinite numbers and oversized numeric tokens are refused.

Allowed requests are:

- `calibration`: `seq`, `op`, `index` (0 through271).
- `view`: `seq`, `op`, `trial_id` (a complete query view).
- `crop`: `seq`, `op`, `trial_id`, `unit_start`, `unit_stop`, `bin_start`, `bin_stop`; typed-viewer only, after a full view.
- `answer`: `seq`, `op`, `trial_id`, `velocity_m_s` (30 finite signed pairs, subject to the original scorer's numeric domain).
- `finish`: `seq`, `op`; accepted only after all92 first-final answers.

The original 2,048-view limit remains. At most2,141 requests can be accepted. The maximum request wire budget is17,547,636 bytes; maximum response wire budget is1,123,033,464 bytes. These are cumulative streaming ceilings, not retained artifact or resident-memory sizes. Each rendered SVG is bounded independently; only hashes of frames are retained.

## Operator handoff

The operator creates a fresh output directory and fsyncs a bounded lifecycle journal before and after launching its owned participant group. Catchable interruption defers until spawn registration/cleanup completes. Clean handoff requires response completion, participant stdin closure, stdout/stderr EOF, zero leader exit and observed absence of the owned group. Only then does trusted code replay the unchanged original submission and visual receipt. Cleanup uncertainty is a failure. Hard termination, OS failure and escaped descendants still require external supervision.

Outputs are `lifecycle.jsonl`, `submission.json`, `visual_receipt.json`, `replay.json`, and `transport.json`. They always remain explicitly **unadmitted**. A complete-looking directory is insufficient: a final fsync can cross the deadline after all files exist. Before any downstream handoff an independent controller must retain the operator's zero exit and whole-operation deadline outcome and bind hashes of **every output**, including the lifecycle journal. Failure, absent controller evidence or uncertain cleanup prevents handoff. No score feedback or private-target loading occurs here.

The generic per-condition retained body ceilings are4MiB submission +4MiB visual receipt +256KiB replay +2MiB transport +16KiB lifecycle. Reserve that bound prospectively for native execution. Do not run authentic data merely because the source tests pass.

## Generated source controls

Run from a stable repository checkout with Python3.11+ and no third-party dependency:

```sh
python3 -I -S -B benchmarks/neural/NEURAL-021/implementations/participant-transport-v1/test_transport.py
```

There are20 source-control methods. Local evidence contains12 initial checks,8 affected/new repair checks and3 final affected/new checks, with overlap; it does not claim a fresh full20-method run on the final version. The tests use a generated complete packet and simulated process/lifecycle primitives. The complete replay check exposes two calibration examples in each mode; a separate complete direct-observation replay uses zero calibration views. All272 calibration trials remain available. No real process, authentic input or private target was used. CI enrollment requests all20. See `VALIDATION.json` for exact scope and `SOURCE_BINDINGS.json` for original dependencies.
