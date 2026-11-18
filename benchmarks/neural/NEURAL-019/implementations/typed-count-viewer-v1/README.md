# NEURAL-019 typed count viewer and trajectory collection

This construction component fills the missing task-specific observation renderer
and answer collector. It does not replace the existing submitted-program route
or scorer. The operator owns the public packet and `Session`; a participant may
receive only responses from a separately qualified transport. No such transport,
OS isolation, AI trial, authentic-packet execution or scientific readiness is
established here. Passing generated controls does not change the registration.

The fixed task remains one exposed Jenkins macaque/session, 1,340 calibration
trials in 28 training maze groups, and all 126 assessment trials from eight other
maze groups. Every trial contains 140 five-millisecond bins and all 137 units.
Assessment group labels and velocity are absent from this component. The required
response is the complete 126 × 140 × 2 signed velocity array in m/s. A velocity
score cannot establish that a submitted latent representation obeyed a matched
ten-dimensional fitting comparison.

## Observation and response boundary

`load_public(path, max_actions=...)` is a future trusted-operator entrypoint. It
accepts only the fixed 59,347,496-byte public packet with SHA256
`98e9b00b9a641e3aa1117c2ea2d737956c3e0df5daa8e77105d34a3449ef02c2`.
It authenticates the file before parsing, checks exact NPZ/NPY inventory, shapes,
dtypes and expanded bounds before array allocation, and checks source stability.
The authentic file was not opened during construction. The expected inventory
comes from the existing registered public contract and remains to be exercised
on the pinned file under a separately admitted operation.

`Session(public_arrays, max_actions=...)` exists for trusted operator integration
and generated controls. This route always reports an unauthenticated mapping.
Both routes copy public arrays into operator-owned state. Neither accepts private
targets, raw NWB paths, decoder models or code execution requests.

Each request is a bounded UTF-8 JSON object. Duplicate keys, nonfinite values,
extra fields, booleans in integer coordinates and unsupported actions are refused.

```json
{"action":"view","role":"assessment","trial":125,"unit_start":121,"unit_stop":137,"bin_start":120,"bin_stop":140}
```

The fixed-coordinate view returns SVG with at most 16 units and 20 bins. Every
count is printed exactly; there is no averaging, normalization, filtering,
interpolation or clipping. All units and bins remain reachable, including unit
136 and bin139. The two-color background distinguishes zero from nonzero without
claiming an analog amplitude scale. This is a count-grid raster, not recovered
within-bin spike timing. Calibration views expose the matching measured x/y
velocity values as round-trippable float64 decimal strings, plus the allowed
anonymous training group and fold. All 1,340 calibration trials are available;
viewing them is optional rather than a hidden prerequisite.

Neural bin edges run −250 to445ms. Velocity bin edges run −150 to545ms: the fixed
100ms lag is labeled explicitly. Existing symmetric preprocessing makes this a
retrospective assay; this interface does not turn it into an online decoder.

```text
{"action":"answer","trial":0,"velocity":[[x_0,y_0], ... all140 pairs ...]}
{"action":"finish"}
```

Each trial accepts one complete first-final answer. Missing rows, NaN/infinity,
booleans, duplicates and partial answers are rejected without filling values.
Finish requires all126 trajectories. Only then can the operator call
`submission()` to obtain the unchanged six fields expected by the existing
scorer: velocity, trial_ids, velocity_left_edges_ms, velocity_axes,
velocity_units and panel_fingerprint. The collector does not score predictions.
The operator must authenticate the finalized output and close any participant
before separately invoking the existing scorer with operator-only targets.

Every request admitted within an open session and available action budget,
including malformed requests, consumes one action and joins a hash chain.
Closed or budget-exhausted calls are refused before recording another action.
The required `max_actions` parameter is a construction bound
between127 and200000, not an admitted scientific study budget or permission for
a run. A future protocol must freeze its budget and whole-session deadline,
calibration access, process/target custody and visual rendering path. The
minimum127 allows complete answers plus finish but no views; it is not a proposed
evaluation setting. Exhausting a budget cannot produce a complete result by
omitting cases.

SVG **source text** contains the displayed numbers. It is not evidence of an
image-only or native-vision condition. A future image-only transport must render
the SVG, verify readability and restrict its participant interface. Current
generated tests inspect SVG structure and exact values; no raster readability,
actual model perception, filesystem isolation or full-session resource envelope
has been qualified. The transcript hash is an integrity aid, not an isolation
proof or a scientific result.

## Construction verification

`test_viewer.py` uses generated complete-shape public tensors in memory, no
authentic arrays, models, fits or target scorer. It covers complete geometry,
whole-group folds, distinct clocks, last-bin/unit coverage, exact calibration,
typed-action rejection, complete immutable responses, budgets and transcript
integrity. Run it using the project's existing two-slot generated-test pool.

This is an additive task-owned source component. Its proposed command requires
explicit component enrollment by the sole integrator; presence of this directory
alone does not enroll or activate a runtime. Source bindings and the private
handoff record the unchanged upstream contracts used to derive its interface.
