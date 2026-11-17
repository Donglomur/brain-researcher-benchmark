"""Anonymous frozen training artifact and stdlib-only inference.

The accepted feature mathematics is imported unchanged. No model fitting or
scientific runtime import occurs here. This artifact never carries held labels,
participant/session keys, training loss traces, or held trajectory lengths.
"""
import json
import math
from consumer import ContractError, validate_observation, probability_vector
from reference import design, absolute_probabilities, Uniform, ContextCounts, RidgeSoftmax

SCHEMA = "hybrid-frozen-statistical-artifact-v1"
MAX_BYTES = 65536


def finite_number(x):
    return type(x) in (float, int) and math.isfinite(x)


def validate_artifact(a):
    if type(a) is not dict or a.get("schema") != SCHEMA:
        raise ContractError("frozen artifact schema")
    kind = a.get("kind")
    fields = {"uniform": {"schema", "kind"},
              "context_counts": {"schema", "kind", "global_counts", "contexts"},
              "ridge": {"schema", "kind", "mean", "scale", "weights"}}
    if kind not in fields or set(a) != fields[kind]:
        raise ContractError("exact artifact fields; no evaluator metadata")
    if kind == "context_counts":
        def counts(v):
            if type(v) is not list or len(v) != 4 or any(not finite_number(x) or x < 1 for x in v):
                raise ContractError("four positive smoothed context counts")
        counts(a["global_counts"])
        if type(a["contexts"]) is not list or len(a["contexts"]) > 12:
            raise ContractError("finite context table")
        keys = set()
        for row in a["contexts"]:
            if type(row) is not list or len(row) != 3 or type(row[0]) is not bool or type(row[1]) is not int or not 0 <= row[1] <= 5:
                raise ContractError("context key")
            key = (row[0], row[1])
            if key in keys:
                raise ContractError("duplicate context")
            keys.add(key); counts(row[2])
    elif kind == "ridge":
        for name in ("mean", "scale"):
            if type(a[name]) is not list or len(a[name]) != 25 or not all(finite_number(v) for v in a[name]):
                raise ContractError("25 finite normalization coefficients")
        if a["mean"][0] != 0 or a["scale"][0] != 1 or any(v <= 0 for v in a["scale"]):
            raise ContractError("training normalization and intercept convention")
        w = a["weights"]
        if type(w) is not list or len(w) != 25 or any(type(row) is not list or len(row) != 4 or not all(finite_number(v) for v in row) for row in w):
            raise ContractError("finite25x4 all-weight ridge artifact")
    return a


def from_model(model):
    if isinstance(model, Uniform):
        a = {"schema": SCHEMA, "kind": "uniform"}
    elif isinstance(model, ContextCounts):
        a = {"schema": SCHEMA, "kind": "context_counts", "global_counts": list(model.global_counts),
             "contexts": [[first, bucket, list(v)] for (first, bucket), v in sorted(model.by_context.items())]}
    elif isinstance(model, RidgeSoftmax):
        a = {"schema": SCHEMA, "kind": "ridge", "mean": model.mean.tolist(),
             "scale": model.scale.tolist(), "weights": model.weights.tolist()}
    else:
        raise ContractError("explicit supported fixed reference family")
    return validate_artifact(a)


def encode_artifact(a):
    body = (json.dumps(validate_artifact(a), sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()
    if len(body) > MAX_BYTES:
        raise ContractError("whole artifact bound")
    return body


def decode_artifact(body):
    if type(body) is not bytes or len(body) > MAX_BYTES:
        raise ContractError("artifact bytes")
    def unique(items):
        out = {}
        for k, v in items:
            if k in out:
                raise ContractError("duplicate artifact key")
            out[k] = v
        return out
    return validate_artifact(json.loads(body, object_pairs_hook=unique,
        parse_constant=lambda value: (_ for _ in ()).throw(ContractError("nonfinite artifact"))))


def predict_artifact(a, x):
    validate_observation(x); kind = a["kind"]
    if kind == "uniform":
        return (.25,) * 4
    if kind == "context_counts":
        key = ContextCounts.context(x)
        v = next((row[2] for row in a["contexts"] if (row[0], row[1]) == key), a["global_counts"])
        return absolute_probabilities(tuple(z / math.fsum(v) for z in v), x)
    z = tuple((value - mean) / scale for value, mean, scale in zip(design(x), a["mean"], a["scale"]))
    logits = [math.fsum(z[i] * a["weights"][i][j] for i in range(25)) for j in range(4)]
    top = max(logits); exp = [math.exp(value - top) for value in logits]; total = math.fsum(exp)
    return absolute_probabilities(tuple(value / total for value in exp), x)
