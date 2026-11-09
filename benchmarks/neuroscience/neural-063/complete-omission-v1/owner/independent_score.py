"""Independent high-precision score reconstruction; no primary scorer calls.

Hierarchy is reconstructed directly as nested Decimal means and square roots.
Only a later authorized E02 invocation may use authentic targets.
"""
from decimal import Decimal, localcontext
import math
from .io import ContractError


def _d(value):
    if type(value) not in (int, float):
        raise ContractError("independent score requires finite numbers")
    try:
        binary64 = float(value)
    except OverflowError:
        raise ContractError("independent operand exceeds finite binary64") from None
    if not math.isfinite(binary64):
        raise ContractError("nonfinite independent operand")
    # Match input admission's binary64 semantics while performing the independent
    # hierarchy, squaring, averaging and roots in high precision.
    return Decimal.from_float(binary64)


def _typed(value):
    if not value.is_finite() or value < 0:
        raise ContractError("invalid independent absolute error")
    try:
        x = float(value)
    except OverflowError:
        x = math.inf
    return {"status": "finite", "value": x} if math.isfinite(x) else {"status": "positive_infinity", "value": None}


def reconstruct(predictions, rows, scale, expected_mice=19):
    if not rows or set(predictions) != {r["id"] for r in rows}:
        raise ContractError("independent full prediction/target set mismatch")
    if len({r["id"] for r in rows}) != len(rows):
        raise ContractError("independent duplicate event")
    groups = {}
    session_owner, experiment_owner = {}, {}
    with localcontext() as ctx:
        ctx.prec = 96
        sd = _d(scale)
        if sd <= 0:
            raise ContractError("independent scale must be positive")
        for row in rows:
            m, s, e = row["mouse"], row["session"], row["experiment"]
            if session_owner.setdefault(s, m) != m or experiment_owner.setdefault(e, (m, s)) != (m, s):
                raise ContractError("independent inconsistent hierarchy")
            p, y = predictions[row["id"]], row["target"]
            if len(p) != 3 or len(y) != 3:
                raise ContractError("independent three-bin requirement")
            error = sum((_d(a) - _d(b)) ** 2 for a, b in zip(p, y)) / Decimal(3)
            groups.setdefault(m, {}).setdefault(s, {}).setdefault(e, []).append(error)
        if len(groups) != expected_mice:
            raise ContractError("independent complete mouse panel required")
        per_mouse_decimal = {}
        for mouse, sessions in groups.items():
            sm = []
            for experiments in sessions.values():
                em = [sum(errors) / Decimal(len(errors)) for errors in experiments.values()]
                sm.append(sum(em) / Decimal(len(em)))
            mse = sum(sm) / Decimal(len(sm))
            per_mouse_decimal[mouse] = mse.sqrt() / sd
        primary = sum(per_mouse_decimal.values()) / Decimal(expected_mice)
        return {"primary": _typed(primary),
                "per_mouse": {m: _typed(v) for m, v in sorted(per_mouse_decimal.items())},
                "precision_decimal_digits": 96, "events": len(rows), "mice": expected_mice}


def compare(primary, independent, tolerance=1e-8):
    if set(primary["per_mouse"]) != set(independent["per_mouse"]):
        raise ContractError("independent mouse set mismatch")
    pairs = [("primary", primary["primary"], independent["primary"])]
    pairs += [(m, primary["per_mouse"][m], independent["per_mouse"][m])
              for m in sorted(primary["per_mouse"])]
    discrepancies = []
    for ident, a, b in pairs:
        if a["status"] != b["status"]:
            raise ContractError("independent absolute status disagreement: " + ident)
        if a["status"] == "positive_infinity":
            discrepancies.append({"id": ident, "status": "matching_positive_infinity", "difference": None})
            continue
        difference = abs(a["value"] - b["value"])
        bound = tolerance * max(1.0, abs(b["value"]))
        if not math.isfinite(difference) or difference > bound:
            raise ContractError("independent absolute score disagreement: " + ident)
        discrepancies.append({"id": ident, "status": "finite_agreement",
                              "difference": difference, "bound": bound})
    return discrepancies
