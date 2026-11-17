# Pure local-window graph ABI

This is source for the prospectively selected local-representation condition. It
does not implement unrestricted arbitrary executable inference and does not
qualify a numerical runtime. No model weights or authentic arrays are bundled.

`validate(graph, array_shapes, input_shapes, limits)` reads metadata only and
does not import NumPy. `evaluate(graph, arrays, inputs, limits)` imports NumPy at
the actual future call, validates the complete graph before numerical work,
copies input/constant arrays, makes them read-only, and returns one finite Python
float `decision_margin`. The outer operator predicts class 1 iff margin >= 0.
Any learned calibration threshold is already subtracted inside the graph.

The graph has exactly `schema`, `nodes`, `output`; schema is
`h_pure_graph_v1`. Nodes are topologically ordered and all must contribute to the
one output. Every node has unique `id` and `op` plus precisely these keys:

| Primitive | Additional keys |
| --- | --- |
| input, constant | name |
| abs, square, sqrt, exp, log, tanh | x |
| add, sub, mul, div, maximum, minimum, less_equal, matmul | a, b |
| where | condition, a, b |
| reshape | x, shape |
| transpose | x, axes |
| slice | x, starts, stops, steps |
| gather_constant_indices | x, axis, indices |
| concat | xs, axis |
| sum, mean, max, min | x, axes, keepdims |
| softmax | x, axis |

References name earlier node IDs. `name` references an external tensor map.
Descriptors are exactly `{shape: [...], dtype: "float64"|"bool"}`. A scalar has
shape `[]`; other dimensions must be positive, rank <= 8. Numerical maps contain
exact NumPy ndarrays with native float64 or bool dtype, not object arrays or
subclasses. Inert file parsing and exact complete map membership belong to the
outer source-pinned array reader, which supplies these arrays after admission.
All constant arrays must be used; a model may legitimately ignore available
inputs. The outer family contract must reject extra/missing names even when
the graph does not use a name.

The accepted caller inputs are `values` float64 `[C,15]` with missing entries
zero-filled and `missing` bool `[C,15]`, true meaning missing. Clock-permitted
families also have `clock` float64 `[5]`. Neural-only has no clock. The analytic
clock-prior model has only clock, and no zero-length values/missing arrays.
Neither identifiers nor other windows enter this map. The outer source must
validate binary mask semantics and one-hot clock before graph dispatch.

Elementwise primitives allow equal shapes or scalar-only broadcast. `where`
uses a bool condition and alternatives with identical dtype; its nonscalar
shapes must agree. `less_equal` returns bool. Other arithmetic/reductions require
float64. `matmul` has rank-two inputs only. Reductions specify distinct literal
nonnegative axes and boolean keepdims. Slices use positive explicit start/stop/
step triples, no empty outputs. Gather has a one-dimensional literal integer
index list (duplicates allowed); reshape can arrange gathered values into CNN
patches. Flattening and reshaping use C/channel-major order. A training compiler
can explicitly expand per-channel constants with reshape/matmul; general
implicit NumPy broadcasting is deliberately unavailable.

Each limits object has exactly positive `max_nodes` (<= 10000),
`max_graph_bytes`, `max_constant_bytes`, `max_tensor_elements`,
`max_peak_array_bytes`, `max_work_units`, finite positive `max_seconds`, and the
original monotonic `deadline`. No default resource ceiling is silently selected.
The caller must derive a full-input policy before operation, and must not crop
the scientific panel to make admission pass.

The plan includes all external constant bytes plus eight bytes per literal
gather index. Its arithmetic work is an abstract admission measure, not elapsed
time or an instruction count. Unary transcendental operations charge 32 units
per element, softmax 48, matmul 2*m*k*n, other arithmetic/reductions at least four
units per relevant element. Shape-only/copy primitives also charge their full
output element count. The array bound includes immutable snapshots, every
intermediate retained conservatively, and an eightfold explicit operand/output
scratch allowance. A separate descriptive liveness estimate is returned but
does not lower admission. Python objects, allocator effects, imported library
state and BLAS private workspace are not certified RSS; the outer isolated
provider must enforce total process memory and wall time independently.

Domain/overflow/nonfinite failures return a typed GraphError, never a score or
discarded record. IEEE float64 underflow may produce zero; later log/division
failure remains a failure. Stable softmax subtracts the axis maximum. This
source requires future runtime/version/round-trip qualification; NumPy/BLAS
rounding differences are not claimed historical identity. Tick checks before
and after every operation and final return cannot preempt a currently executing
native kernel; the independently enforced outer deadline remains necessary.

The graph can express linear/RBF predictors, finite MLPs, local CNNs via gather
and matmul, trees via comparisons/where, within-window attention, and finite
recurrent unrolling. It cannot carry state across calls or use file/network
operations, custom callbacks, stochastic inference, unbounded loops, online
adaptation, or a tensor/workspace beyond the admitted policy. Constants and
inputs are never mutated by this implementation. Callers must own exclusive
custody of input arrays during snapshotting; no shared writable producer may
race private evaluation.
