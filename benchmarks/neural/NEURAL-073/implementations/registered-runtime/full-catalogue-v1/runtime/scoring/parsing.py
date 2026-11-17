"""Bounded streaming UTF-8 JSONL parser; never opens paths or evaluates code."""
import json
from .core import CLASSES, QualificationError, probability_vector

BYTE_CAP = 16 * 1024 * 1024
LINE_CAP = 8 * 1024


class _DuplicateKeys(ValueError):
    pass


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKeys("duplicate JSON object key")
        result[key] = value
    return result


def _constant(value):
    raise ValueError("nonfinite JSON constant")


def parse_jsonl(stream, expected_ids, *, classes=CLASSES, byte_cap=BYTE_CAP, line_cap=LINE_CAP):
    """Parse an explicit binary stream with bounded buffer and bounded diagnostics.

    Caps may only be lowered for engineering controls. A non-newline-terminated EOF
    row is retained when it is complete JSON (the final JSONL newline is optional).
    A row cut by the global cap is rejected, even if its prefix happens to be JSON.
    Read at most cap+1 bytes; the lookahead byte is never parsed. Overlong lines are
    drained with bounded memory. I/O failures are infrastructure exceptions, not
    converted to candidate errors. Candidate timeout/crash is represented by EOF
    on its durably captured stream, supplied by the owner controller.
    """
    expected = tuple(expected_ids)
    if (len(set(expected)) != len(expected) or any(not isinstance(x, str) or not x for x in expected)
            or not expected or type(classes) is not int or classes < 2
            or type(byte_cap) is not int or not 0 < byte_cap <= BYTE_CAP
            or type(line_cap) is not int or not 0 < line_cap <= LINE_CAP):
        raise QualificationError("invalid parser contract")
    values = dict.fromkeys(expected)
    failures = {case: "missing" for case in expected}
    seen = set()
    counters = {"lines": 0, "malformed": 0, "unknown_id": 0, "duplicate_known_id": 0,
                "invalid_known_row": 0, "overlong_line": 0, "truncated_at_byte_cap": 0}
    samples = []

    def incident(reason, line_no):
        counters[reason] += 1
        if len(samples) < 64:
            samples.append({"line": line_no, "reason": reason})

    def line(body, overlong=False, truncated=False):
        counters["lines"] += 1
        number = counters["lines"]
        if overlong:
            incident("overlong_line", number)
            return
        if truncated:
            incident("truncated_at_byte_cap", number)
            return
        try:
            obj = json.loads(body.decode("utf-8"), object_pairs_hook=_object, parse_constant=_constant)
        except (UnicodeError, ValueError, RecursionError):
            incident("malformed", number)
            return
        if not isinstance(obj, dict) or not isinstance(obj.get("case_id"), str):
            incident("malformed", number)
            return
        case = obj["case_id"]
        if case not in values:
            incident("unknown_id", number)
            return
        if case in seen:
            values[case] = None
            failures[case] = "duplicate_known_id"
            incident("duplicate_known_id", number)
            return
        seen.add(case)
        try:
            if set(obj) != {"case_id", "probabilities"} or not isinstance(obj.get("probabilities"), list):
                raise QualificationError("exact output fields required")
            vector = probability_vector(obj["probabilities"], classes)
        except QualificationError:
            failures[case] = "invalid_vector_or_fields"
            incident("invalid_known_row", number)
        else:
            values[case] = list(vector)
            failures.pop(case, None)

    received = 0
    buffer = bytearray()
    overlong = False
    exceeded = False
    while received <= byte_cap:
        request = min(8192, byte_cap + 1 - received)
        if not request:
            break
        chunk = stream.read(request)
        if not isinstance(chunk, bytes) or len(chunk) > request:
            raise QualificationError("binary stream violated bounded read contract")
        if not chunk:
            break
        remaining = byte_cap - received
        admitted = chunk[:max(0, remaining)]
        received += len(chunk)
        for byte in admitted:
            if byte == 10:
                line(bytes(buffer), overlong)
                buffer.clear()
                overlong = False
            elif not overlong:
                if len(buffer) == line_cap:
                    overlong = True
                    buffer.clear()
                else:
                    buffer.append(byte)
        if received > byte_cap:
            exceeded = True
            break
    if buffer or overlong:
        line(bytes(buffer), overlong, truncated=exceeded)
    return {"probabilities": values, "failures": failures, "incidents": counters,
            "incident_samples": samples, "incident_samples_capped_at": 64,
            "stream_bytes_read": received, "accepted_stream_bytes": min(received, byte_cap),
            "byte_cap": byte_cap, "line_cap": line_cap, "output_budget_violation": exceeded,
            "valid_cases": sum(v is not None for v in values.values()), "expected_cases": len(expected),
            "termination": "bounded_captured_stream_end"}


def bind_submission(parsed, opaque_to_private, *, expected_private_ids, expected_mapping_digest):
    """Trusted bijection into stable private IDs, before repeated-panel scoring.

    This returns a new result and never mutates the original parser receipt. Source
    membership and the mapping's authority remain the trusted exporter's duty.
    The mapping is never exported to candidate processes.
    """
    from ..core.custody import digest, require_digest
    require_digest(expected_mapping_digest)
    private_ids = tuple(expected_private_ids)
    probabilities = parsed["probabilities"]
    if (len(private_ids) != len(set(private_ids)) or not private_ids or
            any(not isinstance(x, str) or not x for x in private_ids) or
            set(opaque_to_private.values()) != set(private_ids) or
            parsed["expected_cases"] != len(probabilities) or
            set(opaque_to_private) != set(probabilities) or
            any(not isinstance(k, str) or not k or not isinstance(v, str) or not v
                for k, v in opaque_to_private.items()) or
            len(set(opaque_to_private.values())) != len(opaque_to_private)):
        raise QualificationError("complete unique opaque-to-private bijection required")
    if digest(opaque_to_private) != expected_mapping_digest:
        raise QualificationError("trusted export mapping digest mismatch")
    if set(parsed["failures"]) - set(probabilities):
        raise QualificationError("parser failure IDs outside expected support")
    return {**parsed, "probabilities": {opaque_to_private[k]: v for k, v in probabilities.items()},
            "failures": {opaque_to_private[k]: v for k, v in parsed["failures"].items()},
            "private_mapping_digest": digest(opaque_to_private),
            "parser_receipt_digest": digest(parsed), "mapping_role": "trusted_private_only"}
