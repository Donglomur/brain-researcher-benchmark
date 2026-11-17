"""Trusted numerical-parameter compiler; no fitting or executable deserialization.

Callers capture parameters through their typed inert-array reader. Numerical
compilation and training-only round-trip checking require a qualified runtime;
this source bundle contains no fitted parameters or scientific output.
"""
import math
from .runtime import GraphError, need, canonical, evaluate, validate


class Builder:
    def __init__(self):
        self.nodes = []
        self.arrays = {}

    def node(self, op, **fields):
        nid = "n" + str(len(self.nodes))
        self.nodes.append({"id": nid, "op": op, **fields})
        return nid

    def constant(self, name, value):
        import numpy as np
        need(name not in self.arrays, "schema", "Unique compiler constant name")
        a = np.array(value, copy=True, order="C", subok=False)
        need(a.dtype in (np.dtype("float64"), np.dtype("bool")) and np.isfinite(a).all(), "numeric", "Finite typed compiler constants")
        a.setflags(write=False)
        self.arrays[name] = a
        return self.node("constant", name=name)

    def finish(self, output):
        return {"schema": "h_pure_graph_v1", "nodes": self.nodes, "output": output}, self.arrays

    def scalar(self, name, value):
        return self.constant(name, float(value))

    def ones(self, name, count):
        import numpy as np
        return self.constant(name, np.ones((count, 1), dtype=np.float64))

    def reshaped(self, name, value, new_shape):
        return self.constant(name, value.reshape(new_shape))


class MetadataBuilder(Builder):
    """Same graph construction, with descriptors instead of numeric tensors."""
    def constant(self, name, value):
        need(name not in self.arrays and type(value) is dict and set(value) == {"shape", "dtype"},
             "schema", "Exact unique metadata constant")
        self.arrays[name] = {"shape": list(value["shape"]), "dtype": value["dtype"]}
        return self.node("constant", name=name)

    def scalar(self, name, value):
        return self.constant(name, {"shape": [], "dtype": "float64"})

    def ones(self, name, count):
        return self.constant(name, {"shape": [count, 1], "dtype": "float64"})

    def reshaped(self, name, value, new_shape):
        need(math.prod(value["shape"]) == math.prod(new_shape), "shape", "Metadata reshape extent")
        return self.constant(name, {"shape": list(new_shape), "dtype": value["dtype"]})


def _parameters(metadata):
    import json
    m = json.loads(canonical(metadata))
    need(type(m) is dict and set(m) == {"schema", "family", "channels", "clock"}
         and m["schema"] == "h_svm_parameters_v1", "schema", "Exact parameter metadata")
    need(m["family"] in ("linear_mean", "linear_fullwindow", "gaussian_fullwindow"), "schema", "Declared comparator family")
    need(type(m["channels"]) is int and m["channels"] > 0 and type(m["clock"]) is bool, "shape", "Positive channel count and clock policy")
    c = m["channels"]; f = c if m["family"] == "linear_mean" else 15 * c
    return m, f, 2 * f + (5 if m["clock"] else 0)


def _input_shapes(m):
    shapes = {"values": {"shape": [m["channels"], 15], "dtype": "float64"},
              "missing": {"shape": [m["channels"], 15], "dtype": "bool"}}
    if m["clock"]:
        shapes["clock"] = {"shape": [5], "dtype": "float64"}
    return shapes


def compile_parameters(metadata, arrays):
    """Compile h_svm_parameters_v1 metadata and exact typed parameter arrays.

    metadata: schema, family, channels, clock. Array keys are mean, scale,
    all_missing, bias, threshold and beta (linear), or support_vectors,
    signed_alpha, gamma (Gaussian). beta is the positive-class decision vector;
    signed_alpha must already include source class signs. This function never
    guesses a native library's coefficient orientation from query agreement.
    """
    import numpy as np
    m, f, d = _parameters(metadata)
    common = {"mean", "scale", "all_missing", "bias", "threshold"}
    required = common | ({"support_vectors", "signed_alpha", "gamma"} if m["family"] == "gaussian_fullwindow" else {"beta"})
    need(type(arrays) is dict and set(arrays) == required, "schema", "Complete exact parameter arrays")
    params = {}
    for name, a in arrays.items():
        dtype = np.dtype("bool") if name == "all_missing" else np.dtype("float64")
        need(type(a) is np.ndarray and a.dtype == dtype and np.isfinite(a).all(), "dtype", "Finite typed parameter " + name)
        params[name] = np.array(a, copy=True, order="C", subok=False)
    for name in ("mean", "scale", "all_missing"):
        need(params[name].shape == (f,), "shape", "Exact continuous feature count")
    need((params["scale"] > 0).all(), "numeric", "Positive training scales")
    need((params["mean"][params["all_missing"]] == 0).all()
         and (params["scale"][params["all_missing"]] == 1).all(), "numeric", "All-missing training mean/scale convention")
    for name in ("bias", "threshold"):
        need(params[name].shape == (), "shape", "Scalar margin offset")
    if m["family"] == "gaussian_fullwindow":
        sv = params["support_vectors"]
        need(sv.ndim == 2 and sv.shape[0] > 0 and sv.shape[1] == d, "shape", "Complete support-vector layout")
        need(params["signed_alpha"].shape == (sv.shape[0],), "shape", "One signed coefficient per support vector")
        need(params["gamma"].shape == () and float(params["gamma"]) > 0, "numeric", "Positive explicit Gaussian gamma")
    else:
        need(params["beta"].shape == (d,), "shape", "Complete signed linear coefficient layout")
    k = params["support_vectors"].shape[0] if m["family"] == "gaussian_fullwindow" else None
    return _assemble(m, f, d, k, Builder(), params)


def _assemble(m, f, d, k, b, params):
    """Sole graph topology for numerical export and metadata capacity admission."""
    value = b.node("input", name="values"); missing = b.node("input", name="missing")
    zero = b.scalar("zero", 0.0); one = b.scalar("one", 1.0)
    mask = b.node("where", condition=missing, a=one, b=zero)
    if m["family"] == "linear_mean":
        value = b.node("mean", x=value, axes=[1], keepdims=False)
        mask = b.node("max", x=mask, axes=[1], keepdims=False)
    else:
        value = b.node("reshape", x=value, shape=[f]); mask = b.node("reshape", x=mask, shape=[f])
    present = b.node("less_equal", a=mask, b=zero)
    mu = b.constant("mean", params["mean"]); scale = b.constant("scale", params["scale"])
    all_missing = b.constant("all_missing", params["all_missing"])
    imputed = b.node("where", condition=present, a=value, b=mu)
    z = b.node("div", a=b.node("sub", a=imputed, b=mu), b=scale)
    z = b.node("where", condition=all_missing, a=zero, b=z)
    features = [z, mask]
    if m["clock"]:
        features.append(b.node("input", name="clock"))
    feature = b.node("concat", xs=features, axis=0)
    row = b.node("reshape", x=feature, shape=[1, d])
    if m["family"] == "gaussian_fullwindow":
        # This explicit replication is part of the admitted graph array/work cap.
        ones = b.ones("replication_ones", k)
        repeated = b.node("matmul", a=ones, b=row)
        support = b.constant("support_vectors", params["support_vectors"])
        delta = b.node("sub", a=repeated, b=support)
        squared = b.node("square", x=delta)
        distance = b.node("sum", x=squared, axes=[1], keepdims=False)
        distance = b.node("maximum", a=distance, b=zero)
        gamma = b.constant("gamma", params["gamma"])
        exponent = b.node("mul", a=distance, b=gamma)
        exponent = b.node("sub", a=zero, b=exponent)
        kernel = b.node("exp", x=exponent)
        kernel = b.node("reshape", x=kernel, shape=[1, k])
        coefficient = b.reshaped("signed_alpha", params["signed_alpha"], (k, 1))
        margin = b.node("matmul", a=kernel, b=coefficient)
    else:
        coefficient = b.reshaped("beta", params["beta"], (d, 1))
        margin = b.node("matmul", a=row, b=coefficient)
    margin = b.node("reshape", x=margin, shape=[])
    margin = b.node("add", a=margin, b=b.constant("bias", params["bias"]))
    margin = b.node("sub", a=margin, b=b.constant("threshold", params["threshold"]))
    return b.finish(margin)


def reference_capacity(parameters, n_support, limits):
    """Pure metadata exact compiler plan; no NumPy import or numeric allocation.

    Gaussian support count must be positive. Use all admitted fitting rows for
    a worst-case prospective support count; do not infer a smaller selected
    count before fitting. Linear models require n_support=None. The returned
    plan is exactly runtime.validate for this topology, descriptors and policy.
    It bounds graph inference arrays/work, not native fitting or export buffers.
    """
    m, f, d = _parameters(parameters)
    params = {name: {"shape": [f], "dtype": "bool" if name == "all_missing" else "float64"}
              for name in ("mean", "scale", "all_missing")}
    params.update({name: {"shape": [], "dtype": "float64"} for name in ("bias", "threshold")})
    if m["family"] == "gaussian_fullwindow":
        need(type(n_support) is int and n_support > 0, "shape", "Positive exact/prospective support count")
        params.update({"support_vectors": {"shape": [n_support, d], "dtype": "float64"},
                       "signed_alpha": {"shape": [n_support], "dtype": "float64"},
                       "gamma": {"shape": [], "dtype": "float64"}})
    else:
        need(n_support is None, "shape", "Linear reference has no support-vector count")
        params["beta"] = {"shape": [d], "dtype": "float64"}
    graph, shapes = _assemble(m, f, d, n_support, MetadataBuilder(), params)
    inputs = _input_shapes(m)
    plan = validate(graph, shapes, inputs, limits)
    return {"schema": "h_reference_capacity_v1", "parameters": m, "n_support": n_support,
            "graph": graph, "array_shapes": shapes, "input_shapes": inputs, "plan": plan}


def compile_prior(probabilities):
    """Five training-only P(class=1|window) values after global-prior backoff.

    The design's exact p=.5 tie is class 0; a strictly negative representable
    margin is used for that tie because the common output decision uses >=0.
    """
    import numpy as np
    need(type(probabilities) is np.ndarray and probabilities.dtype == np.dtype("float64")
         and probabilities.shape == (5,) and np.isfinite(probabilities).all()
         and (probabilities >= 0).all() and (probabilities <= 1).all(), "numeric", "Five finite training probabilities")
    margins = probabilities - 0.5
    margins[margins == 0] = -np.finfo(np.float64).eps
    b = Builder(); clock = b.node("input", name="clock")
    weights = b.constant("prior_margins", margins)
    product = b.node("mul", a=clock, b=weights)
    return b.finish(b.node("sum", x=product, axes=[0], keepdims=False))


def build_reference(parameters, arrays):
    """Owner-facing compiler, returning graph, constants, complete input shapes."""
    graph, constants = compile_parameters(parameters, arrays)
    return graph, constants, _input_shapes(parameters)


def build_prior(class_counts):
    """Owner-facing analytic prior using complete admitted training counts.

    Exact mapping: window_counts int64[5,2], global_counts int64[2]. A zero-total
    window uses the nonempty global support. Counts are for class 0 then class 1;
    callers authenticate complete training membership and no query labels.
    """
    import numpy as np
    need(type(class_counts) is dict and set(class_counts) == {"window_counts", "global_counts"}, "schema", "Complete prior counts")
    w, g = class_counts["window_counts"], class_counts["global_counts"]
    need(type(w) is np.ndarray and type(g) is np.ndarray and w.dtype == g.dtype == np.dtype("int64")
         and w.shape == (5, 2) and g.shape == (2,) and (w >= 0).all() and (g >= 0).all(), "shape", "Nonnegative integer prior counts")
    total = int(g[0]) + int(g[1])
    need(total > 0 and all(int(row[0]) <= int(g[0]) and int(row[1]) <= int(g[1]) for row in w), "support", "Nonempty complete global prior support")
    probabilities = np.array([int(row[1]) / (int(row[0]) + int(row[1]))
                              if int(row[0]) + int(row[1]) else int(g[1]) / total for row in w], dtype=np.float64)
    graph, constants = compile_prior(probabilities)
    return graph, constants, {"clock": {"shape": [5], "dtype": "float64"}}


def training_roundtrip(graph, arrays, training_inputs, native_margins, limits, *, atol, rtol):
    """All supplied training rows only; never searches signs/formulas/tolerances.

    The caller authenticates that rows are exclusively the admitted fitting
    support and native_margins already subtracts the selected threshold. The
    fixed prospective runtime policy must pin tolerances before native fitting.
    """
    import numpy as np
    need(type(training_inputs) is list and training_inputs, "schema", "Complete nonempty training rows")
    need(type(native_margins) is np.ndarray and native_margins.dtype == np.dtype("float64")
         and native_margins.shape == (len(training_inputs),) and np.isfinite(native_margins).all(), "shape", "Complete finite native training margins")
    need(all(type(t) in (int, float) and math.isfinite(t) and t >= 0 for t in (atol, rtol)), "limits", "Prospectively fixed finite tolerances")
    max_abs, max_relative = 0.0, 0.0
    for inputs, native in zip(training_inputs, native_margins):
        got = evaluate(graph, arrays, inputs, limits)
        err = abs(got - float(native))
        need(math.isfinite(err) and err <= atol + rtol * abs(float(native)), "roundtrip", "Training-only graph/native mismatch")
        need((got >= 0) == (float(native) >= 0), "roundtrip", "Training-only calibrated class mismatch")
        max_abs = max(max_abs, err)
        max_relative = max(max_relative, err / max(1.0, abs(float(native))))
    return {"schema": "h_training_roundtrip_v1", "status": "complete", "rows": len(training_inputs),
            "max_absolute_error": max_abs, "max_scaled_error": max_relative, "atol": atol, "rtol": rtol,
            "scope": "caller-attested complete training support; no query selection"}
