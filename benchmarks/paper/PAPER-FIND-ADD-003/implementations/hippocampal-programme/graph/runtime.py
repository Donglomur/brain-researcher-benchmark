"""Pure local-window DAG admission and inference.

Only evaluate imports NumPy. This module has no file, network, model-loading or
callback operators. Native-library workspace and process RSS are independently
bounded by the outer provider; the plan bounds explicit graph array storage.
"""
import json
import math
import re
import time


class GraphError(ValueError):
    """Typed unsupported/malformed/numeric/deadline disposition; never a score."""
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def need(ok, code, message):
    if not ok:
        raise GraphError(code, message)


def canonical(value):
    """Exact plain-JSON snapshot, refusing custom objects and nonfinite floats."""
    def plain(x):
        if x is None or type(x) in (str, bool, int):
            return
        if type(x) is float:
            need(math.isfinite(x), "schema", "Nonfinite JSON number")
            return
        if type(x) is list:
            for y in x:
                plain(y)
            return
        if type(x) is dict:
            need(all(type(k) is str for k in x), "schema", "JSON object keys")
            for y in x.values():
                plain(y)
            return
        raise GraphError("schema", "Only plain JSON types are admitted")
    plain(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def shape(value):
    need(type(value) is list and len(value) <= 8, "shape", "Rank at most eight")
    need(all(type(v) is int and v > 0 for v in value), "shape", "Positive dimensions; scalar is []")
    return tuple(value)


def natural(v, name, zero=False):
    need(type(v) is int and v >= (0 if zero else 1), "schema", "Integer " + name)
    return v


def axis(v, rank):
    need(type(v) is int and 0 <= v < rank, "shape", "Literal nonnegative axis in range")
    return v


def product(s):
    return math.prod(s)


def specmap(value):
    need(type(value) is dict, "schema", "Tensor descriptor mapping")
    out = {}
    for name, desc in value.items():
        need(type(name) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,95}", name), "schema", "Tensor name")
        need(type(desc) is dict and set(desc) == {"shape", "dtype"}, "schema", "Exact tensor descriptor")
        need(desc["dtype"] in ("float64", "bool"), "dtype", "Only float64 and bool tensors")
        out[name] = (shape(desc["shape"]), desc["dtype"])
    return out


LIMIT_KEYS = {"max_nodes", "max_graph_bytes", "max_constant_bytes", "max_tensor_elements",
              "max_peak_array_bytes", "max_work_units", "max_seconds", "deadline"}
UNARY = {"abs", "square", "sqrt", "exp", "log", "tanh"}
BINARY = {"add", "sub", "mul", "div", "maximum", "minimum", "less_equal"}
REDUCE = {"sum", "mean", "max", "min"}


def _validate(graph, array_shapes, input_shapes, limits):
    need(type(limits) is dict and set(limits) == LIMIT_KEYS, "limits", "Exact complete limits")
    for k in LIMIT_KEYS - {"max_seconds", "deadline"}:
        natural(limits[k], k)
    need(limits["max_nodes"] <= 10000, "limits", "At most 10,000 nodes")
    for k in ("max_seconds", "deadline"):
        need(type(limits[k]) in (int, float) and math.isfinite(limits[k]) and limits[k] > 0,
             "limits", "Positive finite " + k)
    raw = canonical(graph)
    need(len(raw) <= limits["max_graph_bytes"], "limits", "Graph byte ceiling")
    need(type(graph) is dict and set(graph) == {"schema", "nodes", "output"}
         and graph["schema"] == "h_pure_graph_v1", "schema", "Exact graph envelope")
    nodes = graph["nodes"]
    need(type(nodes) is list and 1 <= len(nodes) <= limits["max_nodes"], "limits", "Node count")
    constants, inputs = specmap(array_shapes), specmap(input_shapes)
    for s, _ in list(constants.values()) + list(inputs.values()):
        need(product(s) <= limits["max_tensor_elements"], "limits", "Input/constant tensor extent")
    base_bytes = sum(product(s) * (8 if d == "float64" else 1) for s, d in list(constants.values()) + list(inputs.values()))
    constant_bytes = sum(product(s) * (8 if d == "float64" else 1) for s, d in constants.values())
    facts, uses, referenced, input_names, constant_names = {}, {}, {}, set(), set()
    total_work = 0
    for index, n in enumerate(nodes):
        need(type(n) is dict and {"id", "op"} <= set(n), "schema", "Node envelope")
        nid, op = n["id"], n["op"]
        need(type(nid) is str and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,95}", nid) and nid not in facts,
             "schema", "Unique node identity")
        refs = []
        def keys(*extra):
            need(set(n) == {"id", "op", *extra}, "schema", "Exact keys for " + str(op))
        def ref(k):
            x = n[k]
            need(type(x) is str and x in facts, "graph", "Only earlier nodes may be referenced")
            refs.append(x)
            return facts[x]["shape"], facts[x]["dtype"]
        work = 1
        if op in ("input", "constant"):
            keys("name")
            source = inputs if op == "input" else constants
            need(type(n["name"]) is str and n["name"] in source, "schema", "Declared tensor name")
            s, d = source[n["name"]]
            (input_names if op == "input" else constant_names).add(n["name"])
        elif op in UNARY:
            keys("x"); s, d = ref("x")
            need(d == "float64", "dtype", "Float arithmetic")
            work = product(s) * (32 if op in {"exp", "log", "tanh"} else 4)
        elif op in BINARY:
            keys("a", "b"); sa, da = ref("a"); sb, db = ref("b")
            need(da == db == "float64", "dtype", "Float operands")
            need(sa == sb or sa == () or sb == (), "shape", "Only same-shape or scalar broadcast")
            s, d = (sb if sa == () else sa), ("bool" if op == "less_equal" else "float64")
            work = product(s) * 4
        elif op == "where":
            keys("condition", "a", "b"); sc, dc = ref("condition"); sa, da = ref("a"); sb, db = ref("b")
            need(dc == "bool" and da == db, "dtype", "Boolean condition and same typed alternatives")
            non_scalar = {z for z in (sc, sa, sb) if z != ()}
            need(len(non_scalar) <= 1, "shape", "Where same-shape or scalar only")
            s, d = (next(iter(non_scalar)) if non_scalar else ()), da
            work = product(s) * 4
        elif op == "reshape":
            keys("x", "shape"); old, d = ref("x"); s = shape(n["shape"])
            need(product(old) == product(s), "shape", "Reshape preserves element count")
        elif op == "transpose":
            keys("x", "axes"); old, d = ref("x")
            need(type(n["axes"]) is list and all(type(i) is int for i in n["axes"])
                 and sorted(n["axes"]) == list(range(len(old))), "shape", "Complete permutation")
            s = tuple(old[i] for i in n["axes"])
        elif op == "slice":
            keys("x", "starts", "stops", "steps"); old, d = ref("x")
            need(all(type(n[k]) is list and len(n[k]) == len(old) for k in ("starts", "stops", "steps")), "shape", "Slice rank")
            out = []
            for extent, start, stop, step in zip(old, n["starts"], n["stops"], n["steps"]):
                need(all(type(v) is int for v in (start, stop, step)) and 0 <= start < stop <= extent and step > 0,
                     "shape", "Nonempty explicit positive slice")
                out.append((stop - start + step - 1) // step)
            s = tuple(out)
        elif op == "gather_constant_indices":
            keys("x", "axis", "indices"); old, d = ref("x"); a = axis(n["axis"], len(old)); ids = n["indices"]
            need(type(ids) is list and ids and all(type(i) is int and 0 <= i < old[a] for i in ids), "shape", "Literal in-range gather indices")
            constant_bytes += 8 * len(ids)
            s = old[:a] + (len(ids),) + old[a + 1:]
        elif op == "concat":
            keys("xs", "axis")
            need(type(n["xs"]) is list and len(n["xs"]) >= 1 and all(type(x) is str and x in facts for x in n["xs"]), "graph", "Declared concat inputs")
            refs.extend(n["xs"])
            first = facts[n["xs"][0]]; old, d = first["shape"], first["dtype"]; a = axis(n["axis"], len(old))
            width = 0
            for x in n["xs"]:
                q = facts[x]
                need(q["dtype"] == d and len(q["shape"]) == len(old)
                     and all(q["shape"][i] == old[i] for i in range(len(old)) if i != a), "shape", "Concat compatible shapes/types")
                width += q["shape"][a]
            s = old[:a] + (width,) + old[a + 1:]
        elif op == "matmul":
            keys("a", "b"); sa, da = ref("a"); sb, db = ref("b")
            need(da == db == "float64" and len(sa) == len(sb) == 2 and sa[1] == sb[0], "shape", "Rank-two compatible float matmul")
            s, d = (sa[0], sb[1]), "float64"
            work = 2 * sa[0] * sa[1] * sb[1]
        elif op in REDUCE:
            keys("x", "axes", "keepdims"); old, d = ref("x"); aa = n["axes"]
            need(d == "float64" and type(aa) is list and aa and len(set(aa)) == len(aa), "shape", "Nonempty distinct reduction axes")
            for a in aa:
                axis(a, len(old))
            need(type(n["keepdims"]) is bool, "schema", "Boolean keepdims")
            s = tuple(1 if i in aa else x for i, x in enumerate(old)) if n["keepdims"] else tuple(x for i, x in enumerate(old) if i not in aa)
            work = 4 * product(old)
        elif op == "softmax":
            keys("x", "axis"); s, d = ref("x"); axis(n["axis"], len(s))
            need(d == "float64", "dtype", "Float softmax")
            work = 48 * product(s)
        else:
            raise GraphError("schema", "Unsupported primitive")
        elements = product(s)
        work = max(work, elements)
        need(elements <= limits["max_tensor_elements"], "limits", "Every intermediate tensor extent")
        own = 0 if op in ("input", "constant") else elements * (8 if d == "float64" else 1)
        # Every explicit output is copied. Eight full-sized float scratch arrays
        # plus the largest operand conservatively cover NumPy expression paths;
        # library-private BLAS workspace and Python objects are outer telemetry.
        operand_bytes = sum(facts[x]["bytes"] for x in set(refs))
        scratch = 8 * (elements * 8 + operand_bytes) if own else elements * 8
        facts[nid] = {"shape": s, "dtype": d, "bytes": elements * (8 if d == "float64" else 1),
                      "owned": own, "scratch": scratch, "work": work, "index": index}
        referenced[nid] = refs
        for x in refs:
            uses[x] = uses.get(x, 0) + 1
        uses.setdefault(nid, 0)
        total_work += work
    need(type(graph["output"]) is str and graph["output"] in facts, "graph", "Declared output node")
    out = facts[graph["output"]]
    need(out["shape"] == () and out["dtype"] == "float64", "shape", "One scalar float64 decision margin")
    reachable, pending = set(), [graph["output"]]
    while pending:
        x = pending.pop()
        if x not in reachable:
            reachable.add(x); pending.extend(referenced[x])
    need(reachable == set(facts), "graph", "Every node contributes to the sole output")
    # A predictor may ignore an admitted channel/mask/clock (including a constant
    # predictor). The outer family contract fixes the full available input map.
    need(constant_names == set(constants), "schema", "Exact used constant tensor names")
    need(constant_bytes <= limits["max_constant_bytes"], "limits", "Complete constant byte ceiling")
    need(total_work <= limits["max_work_units"], "limits", "Complete graph work ceiling")
    live, peak, remaining = base_bytes, 2 * base_bytes, dict(uses)
    for n in nodes:
        f = facts[n["id"]]
        peak = max(peak, live + f["owned"] + f["scratch"])
        live += f["owned"]
        for x in referenced[n["id"]]:
            remaining[x] -= 1
            if remaining[x] == 0 and x != graph["output"]:
                live -= facts[x]["owned"]
    liveness_peak = peak
    # Retaining all intermediates is a deliberately conservative admission bound.
    # It also covers temporary Python references in the NumPy dispatch loop;
    # liveness analysis is descriptive and never debits those references early.
    peak = max(peak, base_bytes + sum(v["owned"] for v in facts.values()) + max(v["scratch"] for v in facts.values()))
    need(peak <= limits["max_peak_array_bytes"], "limits", "Explicit graph array workspace ceiling")
    return {"schema": "h_graph_plan_v1", "graph_bytes": len(raw), "constant_bytes": constant_bytes,
            "input_snapshot_bytes": base_bytes - sum(product(s) * (8 if d == "float64" else 1) for s, d in constants.values()),
            "base_snapshot_bytes": base_bytes, "liveness_array_bytes_bound": liveness_peak,
            "peak_array_bytes_bound": peak, "work_units": total_work,
            "nodes": {k: {**v, "shape": list(v["shape"])} for k, v in facts.items()}, "uses": uses}


def validate(graph, array_shapes, input_shapes, limits):
    """Static admission only. No numeric arrays are read and NumPy is not imported."""
    try:
        return _validate(graph, array_shapes, input_shapes, limits)
    except GraphError:
        raise
    except (KeyError, TypeError, ValueError, OverflowError, RecursionError) as e:
        raise GraphError("schema", "Malformed graph metadata: " + type(e).__name__) from e


def evaluate(graph, arrays, inputs, limits):
    """Return a finite scalar margin. No global cache or cross-call workspace.

    Exact ndarray inputs/constants only; both are copied and made read-only.
    IEEE underflow may become zero. Invalid domains/division/overflow fail the
    record and are never converted into a favorable class or omitted record.
    """
    start = time.monotonic()
    import numpy as np
    frozen_limits = json.loads(canonical(limits))
    frozen = json.loads(canonical(graph))
    need(type(arrays) is dict and type(inputs) is dict, "schema", "Exact numeric maps")
    def descriptors(values):
        result = {}
        for name, a in values.items():
            need(type(a) is np.ndarray and a.dtype in (np.dtype("float64"), np.dtype("bool")), "dtype", "Exact inert numeric ndarray")
            result[name] = {"shape": list(a.shape), "dtype": "bool" if a.dtype == np.dtype("bool") else "float64"}
        return result
    plan = validate(frozen, descriptors(arrays), descriptors(inputs), frozen_limits)
    end = min(start + frozen_limits["max_seconds"], frozen_limits["deadline"])
    def tick():
        need(time.monotonic() < end, "deadline", "Original inference cutoff")
    tick()
    def snapshot(values):
        out = {}
        for name, a in values.items():
            tick()
            need(np.isfinite(a).all(), "numeric", "Finite input/constants; separate missing mask")
            b = np.array(a, copy=True, order="C", subok=False)
            b.setflags(write=False); out[name] = b
        return out
    constants, observed = snapshot(arrays), snapshot(inputs)
    values, remaining = {}, dict(plan["uses"])
    with np.errstate(divide="raise", over="raise", invalid="raise", under="ignore"):
        for n in frozen["nodes"]:
            tick(); op = n["op"]; refs = []
            def get(k):
                refs.append(n[k]); return values[n[k]]
            try:
                if op == "input":
                    result = observed[n["name"]]
                elif op == "constant":
                    result = constants[n["name"]]
                elif op in UNARY:
                    x = get("x")
                    result = {"abs": np.abs, "square": np.square, "sqrt": np.sqrt,
                              "exp": np.exp, "log": np.log, "tanh": np.tanh}[op](x)
                elif op in BINARY:
                    a, b = get("a"), get("b")
                    result = {"add": np.add, "sub": np.subtract, "mul": np.multiply, "div": np.divide,
                              "maximum": np.maximum, "minimum": np.minimum, "less_equal": np.less_equal}[op](a, b)
                elif op == "where":
                    result = np.where(get("condition"), get("a"), get("b"))
                elif op == "reshape":
                    result = np.reshape(get("x"), n["shape"], order="C")
                elif op == "transpose":
                    result = np.transpose(get("x"), n["axes"])
                elif op == "slice":
                    result = get("x")[tuple(slice(a, b, c) for a, b, c in zip(n["starts"], n["stops"], n["steps"]))]
                elif op == "gather_constant_indices":
                    result = np.take(get("x"), n["indices"], axis=n["axis"])
                elif op == "concat":
                    refs.extend(n["xs"]); result = np.concatenate([values[x] for x in n["xs"]], axis=n["axis"])
                elif op == "matmul":
                    result = np.matmul(get("a"), get("b"))
                elif op in REDUCE:
                    result = {"sum": np.sum, "mean": np.mean, "max": np.max, "min": np.min}[op](
                        get("x"), axis=tuple(n["axes"]), keepdims=n["keepdims"])
                elif op == "softmax":
                    x = get("x"); a = n["axis"]
                    e = np.exp(x - np.max(x, axis=a, keepdims=True)); result = e / np.sum(e, axis=a, keepdims=True)
                else:
                    raise GraphError("schema", "Unsupported admitted operator")
                if op not in ("input", "constant"):
                    result = np.array(result, copy=True, order="C", subok=False)
                    result.setflags(write=False)
                expected = plan["nodes"][n["id"]]
                need(list(result.shape) == expected["shape"] and result.dtype == np.dtype(expected["dtype"]), "internal", "Admitted/runtime tensor mismatch")
                need(np.isfinite(result).all(), "numeric", "Nonfinite graph result")
                values[n["id"]] = result
                for x in refs:
                    remaining[x] -= 1
                    if remaining[x] == 0 and x != frozen["output"]:
                        del values[x]
                tick()
            except GraphError:
                raise
            except (FloatingPointError, ValueError, OverflowError, MemoryError) as e:
                raise GraphError("numeric", "Inference failed at " + n["id"] + ": " + type(e).__name__) from e
    score = float(values[frozen["output"]])
    need(math.isfinite(score), "numeric", "Finite decision margin")
    tick()
    return score
