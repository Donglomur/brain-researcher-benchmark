# Held-out target binding

This evaluator-side bridge reconstructs the private 128-row, 147-site target
packet from a pinned serialized observed-target sidecar and paired metadata.
It authenticates the sidecar and metadata, checks the exact split/site identity,
reconstructs and authenticates the field-local float64 mask, and calls the
existing original-input-programme-v1 input_binding.operator_packet function.
The retained retinal-heldout scorer is unchanged.

The constructor accepts --manifest, --manifest-sha256 and --output. Real
manifests and outputs belong to the evaluator and must stay unavailable to
training or candidate selection. No real manifest, target value, fitted model,
prediction or scientific score is included here.

For generated controls, invoke run_generated_controls.py with --artifacts and
an entirely absent absolute directory outside the checkout. The fixed entry
admits the existing hosted jaxley-input-cpu profile (Python 3.11.18, Linux x86_64,
NumPy 1.24.3) and uses the existing pinned reporting_transport.py. Its stdout is
only the complete ordered eight-control JSON summary; DIAGNOSTICS.log and
RESULT.json retain the real unittest output, source pins and child runtime.
The transport has a 55-second child deadline and bounded 64-KiB diagnostics
and reports. Resource allocation remains with the maintained outer CI runner.
The source-stage local Python 3.11.6/NumPy 1.26.3 result is separate; fresh hosted
execution is required for this portable entry.

All eight test methods and their fixture/helper bodies are preserved. They use
generated data through the real file loader, existing producer and scorer,
including identity corruption, target exclusion, mask/dtype/header/link checks,
perfect/reversed correlation, and an undefined site that cannot be dropped.
These are generated engineering controls, not original-data fits or benchmark
results. Whole-record preprocessing and the fresh source-default split remain
disclosed limitations; the retained scorer leaves paper_win and uncertainty null.
