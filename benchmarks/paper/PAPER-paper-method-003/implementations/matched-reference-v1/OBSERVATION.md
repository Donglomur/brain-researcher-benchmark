# Phase cost observation

`observe.py` is an optional trusted-operator wrapper for the unchanged `run.py`
**fit** and **compatibility** commands. It records elapsed time and process memory
around the actual maintained methods. It neither admits execution nor changes the
model, data, recipe, RNG calls or argument order, and never rewrites a returned
result or scientific output file. Timing metadata such as the compatibility
receipt's own elapsed seconds can include observer overhead and therefore differ.
It provides no resource enforcement or participant isolation.

The dependency identities are checked before loading and after execution. The
surrounding operator must independently authenticate the observer, complete source
closure, environment and inputs, and provide immutable source and an owned
execution deadline. The trace is measurement metadata, not proof of execution or
qualification. The existing profile's source and runtime restrictions still apply.

For an already admitted operation, put the unchanged operator arguments after `--`:

```sh
python3 -I -B observe.py --trace /absolute/path/new-cost.jsonl -- \
  fit --info /absolute/path/info.json --packet /absolute/path/packet \
  --author-source /absolute/path/author-source \
  --profile cpu-fp32-math --overlay /absolute/path/site-packages \
  --encoder /absolute/path/encoder.safetensors --seed 42 \
  --output /absolute/path/fresh-fit-output
```

The trace parent must exist; the trace and operator output must be fresh. The same
wrapper supports `compatibility`/`compat` with its existing arguments. It does not
add training examples, a validation pass, fitting, repetitions or a new command to
the compatibility workload. **No authentic workload has been run with this
observer.** Prediction is explicitly refused by the wrapper: the existing
`predict` command remains available without partial instrumentation being presented
as full observation.

## What the trace measures

The JSONL header binds the declared profile and the maintained run/native/recipe
source hashes. Fixed phase names cover construction, stage entry, training epochs
and batches, validation, selected-state snapshots, restoration and checkpoint
saving. The outer operation also includes ordinary CLI input and result handling.
Source import and observer setup occur before that outer phase. Phases may nest;
summing all durations would double-count their children. Stage order remains the
pinned LP then FT recipe; argument values and scientific metrics are not copied
into the trace.

Each phase boundary records:

- Monotonic elapsed seconds and the end-to-start duration when both observations
  are valid. These are host wall times and include instrumentation overhead.
  No CUDA synchronization is inserted; a future CUDA trace must not be treated
  as synchronized device-kernel phase timing.
- **Cumulative lifetime high-water RSS for this process**, from
  `RUSAGE_SELF`. This includes earlier phases. It is not an independent peak for
  the current phase, nor a simultaneous process-tree measurement.
- **Current RSS sampled only at phase boundaries.** A transient between samples
  can be missed; no field claims an exact phase maximum. macOS uses the system
  `proc_pidinfo(PROC_PIDTASKINFO)` resident-size field; Linux uses its current
  process `statm` resident-page count. Linux accounting may itself be approximate.

Sampling accesses only the current process. There are no sampler processes or
threads, no subprocess calls, and no model or data reads for measurement. This is
compatible with the CPU profile's subprocess refusal. Unsupported platforms or
failed measurements yield null fields and an incomplete observation, not zero
memory or a successful qualification. Header and summary fields never contain
signal values, labels, logits, predictions, per-case IDs, exception text or input
paths.

## Bounds and failures

The defaults reserve 20,000 begin/end event slots and at most 8 MiB cumulative
trace bytes; `--max-events` and `--max-bytes` select explicit bounded alternatives.
The ordinary maximum 25-epoch recipe has 4,925 training batches and fits within
that event allowance. The writer reserves room for its final summary. Overflow,
invalid clock observations, unavailable RSS, changed dependencies, or scientific
operation failure mark the observation incomplete. Measurement failure does not
skip, repeat, retune or replace a scientific call. Original exceptions propagate
through each wrapper; class members are restored afterward. Scientific files
already produced remain untouched.

Require both wrapper exit status zero and a complete final summary before using a
trace as completed cost observation. A partial trace, terminated process or failed
close is not a successful measurement. An observation failure can make this wrapper
exit nonzero even when the underlying scientific operation wrote a result; inspect
those two outcomes separately. As with `run.py`, all scientific results still need
independent admission. No automatic retry is supplied.

These measurements can distinguish FT cost from LP cost and identify when a new
process high-water mark occurs. They do not establish a safe full-fit budget from
a short compatibility run. Later allocation behavior, the complete validation
panel, and checkpoint/snapshot lifetimes still require appropriately selected
cost evidence. The November 23 numerical pass exceeded its frozen 8 GiB ceiling;
that failure is preserved in [CPU_PROFILE.md](CPU_PROFILE.md).

## Generated controls

```sh
python3 -I -B observer_tests.py
```

The controls use the actual `run.main`, `native.fit_reference` and
`recipe.drive_fit` with an inert backend. They compare scientific result bytes,
call order and Python RNG state with and without observation for the inert fit,
and exercise trace
privacy, failures, bounds, fresh-file protection and source identity. A current
process memory sample checks the platform reader. No tensor library, EEG array,
label payload, model weight or authentic fit is loaded. Actual tensor parity is
unqualified; compatibility timing fields are not claimed to be byte-identical.
