# Exact metadata reference admission

`graph.compile_reference.reference_capacity(parameters, n_support, limits)`
constructs the identical graph topology and constant descriptors used by
`build_reference`, then calls the actual `graph.runtime.validate`. It imports no
NumPy, reads no numerical arrays, and allocates no support-vector matrix. The
numeric and metadata compiler share the sole `_assemble` function. Only the
builder's constant materialization differs.

`parameters` has exactly schema (`h_svm_parameters_v1`), family
(`linear_mean`, `linear_fullwindow`, or `gaussian_fullwindow`), positive channels,
and boolean clock. Gaussian `n_support` must be a positive integer. For
prospective complete-model admission, the owner supplies the full admitted
training-row count as the worst-case support count, without assuming a smaller
support set before fitting. Linear families require `n_support=None` because
their exported model uses the complete signed linear coefficient vector.

The result has schema `h_reference_capacity_v1`, frozen parameter metadata,
n_support, graph, array_shapes, input_shapes, and plan. The `plan` member is the
unmodified return of `runtime.validate`; use its exact constant_bytes,
peak_array_bytes_bound, work_units and all other validated bounds. This replaces
a hand-derived approximation. A proposed limit below the required bound raises
the usual typed GraphError. Caller-selected limits stay prospective; this API
does not silently increase them or reduce the scientific input support.

The model constant bytes include the explicit Gaussian replication vector and
all scalar/feature/parameter arrays. Graph JSON is counted separately by the
plan's graph_bytes. Outer model-file headers, descriptors, receipts and capture
envelopes require additional source-defined retention accounting. The result is
an inference-graph array/work bound. Native MATLAB fitting, compiler/export
buffers, Python objects, library workspace and total process RSS are distinct
outer limits; this source does not certify them from a graph plan.

The original compiler and manifest remain byte-for-byte under
`history/capacity-v1/`. The additive capacity manifest supersedes only the current
compile_reference.py member of the original manifest. Historical test receipts
continue to identify the original compiler bytes and are not silently rewritten.
