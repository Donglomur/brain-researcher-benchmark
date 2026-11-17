"""Shared, source-owned validation and native-clock arithmetic.

No data discovery, model execution or implicit authorization. Callers own the
information boundary and access gate. A pin identifies this exact module.
"""
import hashlib
import json
import math
from pathlib import Path


class ContractError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise ContractError(message)


def finite_number(value, name="number"):
    need(type(value) in (int, float), name + ": numeric value, not bool")
    try:
        result = float(value)
    except (ValueError, OverflowError):
        raise ContractError(name + ": finite representable number")
    need(math.isfinite(result), name + ": finite number")
    return result


def integer(value, name="integer", minimum=0):
    need(type(value) is int and value >= minimum, name + ": integer in range")
    return value


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def _bad_constant(value):
    raise ContractError("Nonfinite JSON constant: " + value)


def strict_json_loads(body, max_bytes=1048576):
    need(type(body) is bytes and len(body) <= max_bytes, "Bounded JSON bytes")
    try:
        result = json.loads(body.decode("utf-8"), object_pairs_hook=_pairs,
                            parse_constant=_bad_constant)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise ContractError("Invalid UTF-8 JSON") from error
    # JSON's exponent parser can overflow even without a NaN/Infinity literal.
    def walk(value):
        if type(value) is float:
            need(math.isfinite(value), "Nonfinite parsed JSON number")
        elif type(value) is dict:
            for item in value.values():
                walk(item)
        elif type(value) is list:
            for item in value:
                walk(item)
    walk(result)
    return result


def canonical_json_bytes(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False, ensure_ascii=False) + "\n").encode("utf-8")


def sha256(body):
    need(type(body) is bytes, "Hash bytes only")
    return hashlib.sha256(body).hexdigest()


def object_sha256(value):
    return sha256(canonical_json_bytes(value))


def exact_keys(value, required, optional=()):
    need(type(value) is dict, "Object required")
    need(set(required) <= set(value), "Missing keys: " + str(set(required) - set(value)))
    need(set(value) <= set(required) | set(optional), "Unexpected keys")


def unique_records(rows, keys):
    need(type(rows) is list, "Record list required")
    result = {}
    for row in rows:
        need(type(row) is dict and all(k in row for k in keys), "Missing record key")
        key = tuple(row[k] for k in keys)
        try:
            need(key not in result, "Duplicate record key: " + str(key))
            result[key] = row
        except TypeError as error:
            raise ContractError("Record keys must be scalar/hashable") from error
    return result


def safe_member(root, relative):
    need(type(relative) is str and relative, "Relative member required")
    member = Path(relative)
    need(not member.is_absolute() and all(x not in ("", ".", "..") for x in member.parts),
         "Unsafe member path")
    root = Path(root).absolute()
    candidate = root / member
    need(not root.is_symlink(), "Symlink root")
    cursor = root
    for part in member.parts:
        cursor = cursor / part
        need(not cursor.is_symlink(), "Symlink member")
    need(candidate.resolve().is_relative_to(root.resolve()), "Escaped member")
    return candidate


def read_member(root, relative, max_bytes):
    path = safe_member(root, relative)
    need(path.is_file() and path.stat().st_size <= max_bytes, "Bounded regular member")
    with path.open("rb") as stream:
        body = stream.read(max_bytes + 1)
    need(len(body) <= max_bytes, "Member grew beyond limit")
    return body


def member_pin(root, relative, max_bytes=1048576):
    body = read_member(root, relative, max_bytes)
    return {"path": relative, "bytes": len(body), "sha256": sha256(body)}


def verify_pin(root, pin, max_bytes=1048576):
    exact_keys(pin, ["path", "bytes", "sha256"])
    integer(pin["bytes"], "pinned bytes")
    need(pin["bytes"] <= max_bytes, "Pinned size exceeds bound")
    body = read_member(root, pin["path"], max_bytes)
    need(len(body) == pin["bytes"] and sha256(body) == pin["sha256"], "Pin mismatch")
    return body


def native_interval_weights(times, start, end, max_gap, valid=None):
    """Integral weights for piecewise-linear native samples, excluding gaps.

    Each accepted adjacent segment is intersected with [start,end]. Segments
    spanning a missing sample or exceeding max_gap never bridge a gap.
    No edge extrapolation, artificial sample insertion or zero filling occurs.
    """
    need(type(times) is list and len(times) >= 2, "At least two native timestamps")
    t = [finite_number(x, "timestamp") for x in times]
    need(all(b > a for a, b in zip(t, t[1:])), "Strictly increasing clock")
    start, end, max_gap = [finite_number(x) for x in (start, end, max_gap)]
    need(end > start and max_gap > 0, "Positive interval and gap bound")
    if valid is None:
        valid = [True] * len(t)
    need(type(valid) is list and len(valid) == len(t)
         and all(type(x) is bool for x in valid), "Explicit sample-validity mask")
    weights = [0.0] * len(t)
    coverage = 0.0
    segments = []
    for i, (a, b) in enumerate(zip(t, t[1:])):
        if not (valid[i] and valid[i + 1]) or b - a > max_gap:
            continue
        left, right = max(a, start), min(b, end)
        if right <= left:
            continue
        u, v = (left - a) / (b - a), (right - a) / (b - a)
        right_weight = (b - a) * (v * v - u * u) / 2
        left_weight = right - left - right_weight
        weights[i] += left_weight
        weights[i + 1] += right_weight
        coverage += right - left
        segments.append({"left_index": i, "right_index": i + 1,
                         "left": left, "right": right})
    return {"weights": weights, "covered_seconds": coverage,
            "requested_seconds": end - start, "segments": segments}


def native_integral(times, values, start, end, max_gap, valid=None):
    need(type(values) is list and len(values) == len(times), "Native values shape")
    values = [finite_number(x, "sample") for x in values]
    support = native_interval_weights(times, start, end, max_gap, valid)
    support["integral"] = math.fsum(w * x for w, x in zip(support["weights"], values))
    support["mean"] = (support["integral"] / support["covered_seconds"]
                       if support["covered_seconds"] > 0 else None)
    return support


def native_error(times, truth, prediction, start, end, max_gap, valid=None):
    """Trapezoid integration of sampled squared/absolute/signed errors.

    This is trapezoid quadrature of error samples, not the analytic integral
    of a squared linearly interpolated residual. Report that convention.
    """
    need(len(times) == len(truth) == len(prediction), "Native prediction shape")
    residual = [finite_number(p, "prediction") - finite_number(y, "truth")
                for y, p in zip(truth, prediction)]
    support = native_interval_weights(times, start, end, max_gap, valid)
    covered = support["covered_seconds"]
    need(covered > 0, "No observed integration support")
    weights = support["weights"]
    return {"mse": math.fsum(w * e * e for w, e in zip(weights, residual)) / covered,
            "mae": math.fsum(w * abs(e) for w, e in zip(weights, residual)) / covered,
            "bias": math.fsum(w * e for w, e in zip(weights, residual)) / covered,
            "covered_seconds": covered, "requested_seconds": support["requested_seconds"],
            "quadrature": "trapezoid_of_sample_errors_no_gap_bridging"}


def receipt(kind, input_pins, output_pins, previous=None, **fields):
    need(type(kind) is str and kind, "Receipt kind")
    return {"schema": "reward_process_receipt_v1", "kind": kind,
            "inputs": input_pins, "outputs": output_pins,
            "previous_receipt_sha256": None if previous is None else object_sha256(previous),
            **fields}


def verify_receipt_link(current, previous):
    need(current.get("schema") == "reward_process_receipt_v1", "Receipt schema")
    expected = None if previous is None else object_sha256(previous)
    need(current.get("previous_receipt_sha256") == expected, "Receipt chain mismatch")
    return True
