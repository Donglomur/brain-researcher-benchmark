# Original optimizer provenance collector

This operator-only component observes the source optimizer boundary used by the accepted `author-law-production-v1/producer.py`. It adds diagnostics that the original `models.py` discards after requesting `full_output=True`. It does not implement an optimizer, change the original model equations, replace the producer, or decide scientific success.

`collect_injected(targets, backend)` is the generated/injected engineering seam. Its artifact identifies that origin explicitly. `collect_original(targets, models_path)` calls the existing exact-byte source loader, then uses the same observer. The original route still has no independent execution attestation. Importing the collector itself does not load the original model or scientific packages.

The exact authenticated source is `GWeindel/decision-times` revision `76464a9ca15564897e58256081af4b99d08ae8db`, `models.py`, 4,681 bytes, SHA256 `bd7556bc912d0443f2c00c74cd6f9174a2afb9d1734ceb7cf02b10685abf209b`. Its `latency.fit` passes only `p0`, `bounds` and `full_output=True` explicitly to `scipy.optimize.curve_fit`. Linear is `slope*x+t0` with two unbounded parameters, Pieron is `slope*x**-alpha` with two nonnegative parameters and no intercept, and Fechner has three parameters bounded by `[0,0,0]` and `[18.51,7.47,3.69]`. Starting points are respectively `[1,1]`, `[1,1]` and `[1,1,1]`. Method, tolerances, iteration limits, Jacobian and other unspecified arguments remain runtime defaults; this component assigns none.

For each existing source job, the collector checks the exact law, fitting trial vectors in seconds/fractions, and prediction grid. Inside that one backend call it replaces only the separately loaded author's namespace reference to `scipy` with a task-specific optimizer proxy. The installed SciPy module is never patched. The observer forwards the original function, array/series objects and keyword arguments once, then returns the identical five-value tuple. The namespace reference is restored in `finally`, including validation, optimizer and diagnostic-serialization failures.

The record retains the source job identity/input digest, explicit optimizer configuration and operand digest, returned parameter/covariance/info/message/status values, available type/dtype/shape information, and the producer prediction digest. Diagnostic NaN and infinities use explicit JSON tags; integers retain their values. Unsupported diagnostic serialization fails the observation rather than silently omitting fields. The reference artifact is returned only when every original job closes and its input/output digests match the existing producer receipts. A failure retains observations completed so far and the error, with `reference_production=null`; partial reference predictions are never offered as a complete panel. Loader failures are distinguished before any optimizer observations.

Warning filters and suppression registries are left untouched. A scoped `showwarning` observer records each visible emission and forwards all six original positional arguments to the inherited handler, restoring that exact handler in `finally`. No per-fit `catch_warnings` context resets suppression. Ignored warnings cannot be reconstructed, and warnings configured as errors or inherited handlers that raise still fail the original call. Recording a status code, covariance, warning or finite prediction establishes provenance, not convergence quality or scientific reproduction.

This is trusted, sequential operator code for an exclusively owned process. Author namespace and the process-wide warning display handler are not concurrent/process isolation. Do not share either with concurrent work. Inputs, diagnostics and reference predictions are private operator artifacts and must never be delivered as candidate fitting packets. Source-target/B-H lineage, original helper transformations, historical runtime compatibility/defaults, numerical tolerance, uncertainty and the complete126-reference/18-cell improvement policies remain unqualified.

For a separately admitted native run, the CLI is:

```text
python collector.py TARGETS.json --author-models MODELS.py --output PRIVATE_OBSERVATION.json
```

It reuses the existing loader and producer. Output creation is exclusive; completed observations exit0 and recorded failed observations exit1. No such native execution was performed for this construction.

New generated controls, from repository root:

```text
python3 -I -S -B -m unittest discover -s benchmarks/paper/PAPER-paper-signal-add-019/implementations/original-method-binding-v1/tests -v
```

The controls use recording shims that never evaluate a model or invoke a scientific optimizer. Central enrollment and actual-tree checks remain with the sole integrator. The earlier exporter and its tests remain unchanged.
