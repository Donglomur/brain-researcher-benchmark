"""Strict owner-side capture of one candidate's312 output probability vectors."""
from dataclasses import dataclass
import json
import math
import re

from morse_codec import require, ViewError, read_regular, sha256


@dataclass(frozen=True)
class Prediction:
    id: str
    probabilities: tuple


@dataclass(frozen=True)
class Capture:
    captured_rows: tuple
    payload_sha256: str
    payload_bytes: int
    canonical_sha256: str
    canonical_bytes: bytes


def _alias(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
            "candidate identifier must be64hex")
    return value


def _canonical(rows):
    value = [{"id": r.id, "probabilities": list(r.probabilities)} for r in rows]
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def capture_predictions(path, expected_query_aliases, *, max_bytes):
    require(type(expected_query_aliases) in (list, tuple, set, frozenset), "explicit expected alias collection")
    expected = {_alias(v) for v in expected_query_aliases}
    require(len(expected_query_aliases) == len(expected) == 312, "exact312 distinct query aliases")
    body = read_regular(path, max_bytes)
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, "duplicate candidate JSON key")
            out[k] = v
        return out
    def constant(value):
        raise ViewError("nonfinite candidate JSON constant")
    try:
        payload = json.loads(body, object_pairs_hook=pairs, parse_constant=constant)
    except (ValueError, UnicodeError) as exc:
        raise ViewError("candidate output is not strict JSON") from exc
    require(type(payload) is list and len(payload) == 312, "candidate output must have312 rows")
    seen, rows = set(), []
    for row in payload:
        require(type(row) is dict and set(row) == {"id", "probabilities"}, "candidate row fields")
        alias = _alias(row["id"])
        require(alias in expected and alias not in seen, "unknown/duplicate candidate alias")
        seen.add(alias)
        probs = row["probabilities"]
        require(type(probs) is list and len(probs) == 26, "exact26 probabilities")
        require(all(type(v) in (int, float) for v in probs), "probabilities must be real JSON numbers")
        try:
            converted = tuple(float(v) for v in probs)
        except (ValueError, OverflowError) as exc:
            raise ViewError("probability cannot be represented as float64") from exc
        require(all(math.isfinite(v) and 0 <= v <= 1 for v in converted), "probability bounds/finite")
        require(abs(math.fsum(converted) - 1.0) <= 1e-6, "probability simplex")
        rows.append(Prediction(alias, converted))
    require(seen == expected, "candidate query coverage")
    rows = tuple(sorted(rows, key=lambda r: r.id))
    canonical = _canonical(rows)
    return Capture(rows, sha256(body), len(body), sha256(canonical), canonical)


def restore_predictions(capture, private_inverse):
    """Translate captured query IDs using an owner-only complete inverse."""
    require(type(capture) is Capture and type(capture.captured_rows) is tuple
            and len(capture.captured_rows) == 312, "validated complete capture required")
    require(type(private_inverse) is dict and len(private_inverse) == 9984, "full owner inverse required")
    canonical = _canonical(capture.captured_rows)
    require(canonical == capture.canonical_bytes and sha256(canonical) == capture.canonical_sha256,
            "capture identity changed")
    expected = {a for a, r in private_inverse.items() if r.get("role") == "query"}
    require(len(expected) == 312 and {r.id for r in capture.captured_rows} == expected,
            "capture/private query coverage")
    output = []
    for row in capture.captured_rows:
        private = private_inverse[row.id]
        require(private["role"] == "query", "training alias cannot be scored as query")
        output.append({"id": _alias(private["canonicalid"]), "probabilities": list(row.probabilities)})
    require(len({r["id"] for r in output}) == 312, "canonical query identity collision")
    return sorted(output, key=lambda r: r["id"])
