"""Immutable restricted row plans. This module does not establish runtime qualification.

No plan operation accepts a batch axis, a callback, a filename, a query identity,
or mutable state. The complete plan, including constants, is canonical JSON.
The operator must independently approve this evaluator and exact dependencies.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re


class PlanError(ValueError):
    pass


def canonical_bytes(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise PlanError("noncanonical or nonfinite JSON") from exc


def digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _keys(obj, names):
    if type(obj) is not dict or set(obj) != set(names):
        raise PlanError("unexpected or missing object fields")


def _integer(value, minimum=0):
    if type(value) is not int or value < minimum:
        raise PlanError("invalid integer")
    return value


def _name(value):
    if type(value) is not str or re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,95}", value) is None:
        raise PlanError("invalid graph identifier")
    return value


def _number(value):
    try:
        valid = type(value) in (float, int) and math.isfinite(value) and abs(value) <= 1.7976931348623157e308
    except OverflowError:
        valid = False
    if not valid:
        raise PlanError("nonfinite or nonnumeric constant")
    return value


def _validate_tree(tree, input_width, classes, constants):
    if type(tree) is not list or not tree:
        raise PlanError("tree must be a finite nonempty node list")
    reachable = {0}
    for i, node in enumerate(tree):
        if type(node) is not dict:
            raise PlanError("invalid tree node")
        if set(node) == {"scores"}:
            key = _name(node["scores"])
            if key not in constants or constants[key]["shape"] != [classes]:
                raise PlanError("tree leaf score shape")
        else:
            _keys(node, ["feature", "threshold", "left", "right"])
            if _integer(node["feature"]) >= input_width:
                raise PlanError("tree feature out of range")
            _number(node["threshold"])
            for side in ("left", "right"):
                target = _integer(node[side])
                if not i < target < len(tree):
                    raise PlanError("tree children must be later finite nodes")
                if i in reachable:
                    reachable.add(target)
    if reachable != set(range(len(tree))):
        raise PlanError("unreachable tree nodes")


@dataclass(frozen=True, slots=True)
class RowPlan:
    """Only canonical immutable bytes are retained; no ndarray state is exposed."""
    encoded: bytes
    input_dim: int
    class_count: int
    digest: str
    state_digest: str
    operations: tuple


def load_plan(document, *, max_encoded_bytes=268435456, max_constant_values=16777216,
              max_nodes=4096):
    """Validate JSON vocabulary/shapes before numerical inference.

    Resource caps are engineering ceilings, not a selected scientific runtime
    allocation. The eventual operator may impose a stricter admitted profile.
    """
    _keys(document, ["schema", "input_dim", "class_count", "constants", "nodes", "output"])
    if document["schema"] != "neural053_row_plan_v1":
        raise PlanError("unsupported plan schema")
    d = _integer(document["input_dim"], 1)
    c = _integer(document["class_count"], 2)
    constants = document["constants"]
    if type(constants) is not dict:
        raise PlanError("constants must be typed JSON objects")
    total = 0
    for name, con in constants.items():
        _name(name)
        _keys(con, ["dtype", "shape", "values"])
        if con["dtype"] != "float64" or type(con["shape"]) is not list or len(con["shape"]) > 2:
            raise PlanError("unsupported constant dtype or rank")
        size = 1
        for dim in con["shape"]:
            size *= _integer(dim, 1)
        if type(con["values"]) is not list or len(con["values"]) != size:
            raise PlanError("constant extent mismatch")
        total += size
        if total > max_constant_values:
            raise PlanError("constant value ceiling exceeded")
        for x in con["values"]:
            _number(x)
    nodes = document["nodes"]
    if type(nodes) is not list or not 1 <= len(nodes) <= max_nodes:
        raise PlanError("invalid node count")
    widths = {"input": d}
    ops = []
    unary = {"abs", "exp", "log", "log1p", "sqrt", "cos", "tanh", "sigmoid", "relu"}
    used_constants = set()
    dependencies = {}
    for node in nodes:
        if type(node) is not dict:
            raise PlanError("graph nodes must be JSON objects")
        name = _name(node.get("id"))
        if name in widths:
            raise PlanError("duplicate node identifier")
        op = node.get("op")
        if type(op) is not str:
            raise PlanError("missing operation")
        refs = node.get("inputs") if op in {"concat", "add", "sub", "mul"} else [node.get("input")]
        if type(refs) is not list or not refs or any(type(x) is not str or x not in widths for x in refs):
            raise PlanError("forward, missing or non-row graph reference")
        dependencies[name] = refs
        w = widths[refs[0]]
        if op == "affine":
            _keys(node, ["id", "op", "input", "weight", "bias"])
            for key in ("weight", "bias"):
                _name(node[key]); used_constants.add(node[key])
                if node[key] not in constants:
                    raise PlanError("unknown affine constant")
            shape = constants[node["weight"]]["shape"]
            if len(shape) != 2 or shape[0] != w or constants[node["bias"]]["shape"] != [shape[1]]:
                raise PlanError("affine constant shape mismatch")
            out = shape[1]
        elif op == "gather":
            _keys(node, ["id", "op", "input", "indices"])
            inds = node["indices"]
            if type(inds) is not list or not inds or any(type(i) is not int or not 0 <= i < w for i in inds):
                raise PlanError("invalid fixed feature indices")
            out = len(inds)
        elif op == "concat":
            _keys(node, ["id", "op", "inputs"])
            out = sum(widths[x] for x in refs)
        elif op in {"add", "sub", "mul"}:
            _keys(node, ["id", "op", "inputs"])
            if len(refs) != 2 or (widths[refs[0]] != widths[refs[1]] and min(widths[x] for x in refs) != 1):
                raise PlanError("binary row feature shape mismatch")
            out = max(widths[x] for x in refs)
        elif op in {"add_const", "sub_const", "mul_const", "div_const"}:
            _keys(node, ["id", "op", "input", "constant"])
            key = _name(node["constant"]); used_constants.add(key)
            if key not in constants or constants[key]["shape"] not in ([], [w]):
                raise PlanError("constant elementwise shape mismatch")
            if op == "div_const" and any(x == 0 for x in constants[key]["values"]):
                raise PlanError("zero divisor")
            out = w
        elif op in unary:
            _keys(node, ["id", "op", "input"])
            out = w
        elif op == "sum":
            _keys(node, ["id", "op", "input", "axis"])
            if node["axis"] != "features":
                raise PlanError("only row feature reduction is admitted")
            out = 1
        elif op == "softmax":
            _keys(node, ["id", "op", "input", "axis"])
            if node["axis"] != "classes" or w != c:
                raise PlanError("softmax class axis mismatch")
            out = c
        elif op == "tree":
            _keys(node, ["id", "op", "input", "tree"])
            _validate_tree(node["tree"], w, c, constants)
            used_constants.update(t["scores"] for t in node["tree"] if "scores" in t)
            out = c
        else:
            raise PlanError("unsupported operation: " + op)
        widths[name] = out
        ops.append(op)
    output = document["output"]
    if type(output) is not str or output != nodes[-1]["id"] or nodes[-1]["op"] != "softmax":
        raise PlanError("final output must be the final class softmax")
    reached = {output}
    for node in reversed(nodes):
        if node["id"] in reached:
            reached.update(dependencies[node["id"]])
    if reached != set(widths):
        raise PlanError("unreachable graph nodes")
    if used_constants != set(constants):
        raise PlanError("unreferenced constants cannot hide model state")
    encoded = canonical_bytes(document)
    if len(encoded) > max_encoded_bytes:
        raise PlanError("encoded plan ceiling exceeded")
    return RowPlan(encoded, d, c, hashlib.sha256(encoded).hexdigest(), digest(constants), tuple(sorted(set(ops))))


def validate_plan_object(plan):
    """Re-admit bytes and all derived fields; a manually forged dataclass is refused."""
    if type(plan) is not RowPlan or type(plan.encoded) is not bytes:
        raise PlanError("expected frozen RowPlan")
    fresh = load_plan(json.loads(plan.encoded))
    if fresh != plan:
        raise PlanError("plan identity mismatch")
    return fresh


def _run(document, row_or_batch, np):
    constants = {k: np.array(v["values"], dtype=np.float64).reshape(v["shape"])
                 for k, v in document["constants"].items()}
    vals = {"input": row_or_batch}
    for node in document["nodes"]:
        op = node["op"]
        x = vals[node["input"]] if "input" in node else None
        with np.errstate(all="raise"):
            if op == "affine":
                value = x @ constants[node["weight"]] + constants[node["bias"]]
            elif op == "gather": value = x[..., node["indices"]]
            elif op == "concat": value = np.concatenate([vals[k] for k in node["inputs"]], axis=-1)
            elif op in {"add", "sub", "mul"}:
                a, b = [vals[k] for k in node["inputs"]]
                value = {"add": np.add, "sub": np.subtract, "mul": np.multiply}[op](a, b)
            elif op in {"add_const", "sub_const", "mul_const", "div_const"}:
                c = constants[node["constant"]]
                value = {"add_const": np.add, "sub_const": np.subtract, "mul_const": np.multiply,
                         "div_const": np.divide}[op](x, c)
            elif op == "sum": value = np.sum(x, axis=-1, keepdims=True)
            elif op == "softmax":
                shifted = x - np.max(x, axis=-1, keepdims=True)
                with np.errstate(under="ignore"):
                    ex = np.exp(shifted)
                    # A positive subnormal exp may round to zero only during
                    # normalization (e.g. exp(-745)/2). Preserve that valid zero;
                    # over/invalid/divide still inherit "raise" from the outer scope.
                    value = ex / np.sum(ex, axis=-1, keepdims=True)
            elif op == "sigmoid":
                with np.errstate(under="ignore"):
                    ex = np.exp(-np.abs(x))
                value = np.where(x >= 0, 1 / (1 + ex), ex / (1 + ex))
            elif op == "relu": value = np.maximum(x, 0)
            elif op == "tree":
                batch = x[None, :] if x.ndim == 1 else x
                rows = []
                for row in batch:
                    idx = 0
                    while "scores" not in node["tree"][idx]:
                        t = node["tree"][idx]
                        idx = t["left"] if row[t["feature"]] <= t["threshold"] else t["right"]
                    rows.append(constants[node["tree"][idx]["scores"]])
                value = np.stack(rows)
                if x.ndim == 1: value = value[0]
            else:
                if op == "log" and np.any(x <= 0): raise PlanError("log domain")
                if op == "log1p" and np.any(x <= -1): raise PlanError("log1p domain")
                if op == "sqrt" and np.any(x < 0): raise PlanError("sqrt domain")
                value = {"abs": np.abs, "exp": np.exp, "log": np.log, "log1p": np.log1p,
                         "sqrt": np.sqrt, "cos": np.cos, "tanh": np.tanh}[op](x)
        if not np.all(np.isfinite(value)):
            raise PlanError("nonfinite intermediate")
        vals[node["id"]] = value
    return vals[document["output"]]


def evaluate(plan, X, *, backend="vectorized"):
    """Evaluate only the fixed supported graph; no fitting or callbacks occur."""
    plan = validate_plan_object(plan)
    if backend not in {"scalar", "vectorized"}:
        raise PlanError("unsupported backend")
    import numpy as np
    if type(X) not in (list, tuple, np.ndarray):
        raise PlanError("input must be a plain numeric array")
    if isinstance(X, np.ndarray) and X.dtype.kind not in "fiu":
        raise PlanError("input dtype must be numeric")
    x = np.asarray(X, dtype=np.float64)
    if x.ndim != 2 or x.shape[1] != plan.input_dim or x.shape[0] == 0 or not np.all(np.isfinite(x)):
        raise PlanError("input shape or finite support mismatch")
    doc = json.loads(plan.encoded)
    try:
        out = _run(doc, x, np) if backend == "vectorized" else np.stack([_run(doc, row, np) for row in x])
    except (FloatingPointError, OverflowError) as exc:
        raise PlanError("nonfinite arithmetic; no fallback") from exc
    if out.shape != (len(x), plan.class_count) or not np.all(np.isfinite(out)) or np.any(out < 0) or np.any(out > 1):
        raise PlanError("invalid output probabilities")
    if np.any(np.abs(out.sum(axis=1) - 1) > 1e-6):
        raise PlanError("probability row sum mismatch")
    return out
