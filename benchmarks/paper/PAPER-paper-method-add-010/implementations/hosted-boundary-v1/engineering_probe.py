"""Bounded generated boundary observations; never a scientific prediction.

Importing this module performs no IO. The fixed candidate wrapper invokes main
inside the selected Provider producer. Host/image audit and custody remain
independent of these candidate observations.
"""
import argparse
import errno
import hashlib
import json
import math
import os
from pathlib import Path
import re
import socket
import stat
import time


SCHEMA = "meg-generated-boundary-probe/v1"
MARKER = "/work/meg-boundary-state-v1.marker"
NETWORK = ("192.0.2.1", 9)
PRIVATE_DENIAL = frozenset((errno.ENOENT, errno.EACCES, errno.EPERM))
WRITE_DENIAL = frozenset((errno.EROFS, errno.EACCES, errno.EPERM))
NETWORK_DENIAL = frozenset((errno.ENETUNREACH, errno.EACCES, errno.EPERM))


def need(value, message):
    if not value:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def read_bounded(path, cap):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, "bounded ordinary probe input")
        raw = os.read(fd, cap + 1)
        after = os.fstat(fd)
        need(len(raw) == before.st_size and
             (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
             == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
             "stable complete probe input")
        return raw
    finally:
        os.close(fd)


def check_private(path):
    """Attempt only the explicitly designated harmless host fixture path."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        return {"qualified": exc.errno in PRIVATE_DENIAL, "operation": "read_open",
                "opened": False, "errno": exc.errno}
    else:
        os.close(fd)
        # Do not read or publish the sentinel value even on a failed boundary.
        return {"qualified": False, "operation": "read_open", "opened": True, "errno": None}


def check_readonly(path):
    """Try a write without truncation; unexpectedly writable generated data fails."""
    try:
        fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError as exc:
        return {"qualified": exc.errno in WRITE_DENIAL, "operation": "write_open_then_same_byte",
                "opened_writable": False, "write_bytes": 0, "errno": exc.errno}
    try:
        original = os.pread(fd, 1, 0)
        need(len(original) == 1, "generated FEATURES has a first byte")
        try:
            written = os.pwrite(fd, original, 0)
        except OSError as exc:
            return {"qualified": False, "operation": "write_open_then_same_byte",
                    "opened_writable": True, "write_bytes": 0, "errno": exc.errno}
        return {"qualified": False, "operation": "write_open_then_same_byte",
                "opened_writable": True, "write_bytes": written, "errno": None}
    finally:
        os.close(fd)


def check_network(deadline):
    """No DNS or payload; refusal, timeout and ambiguous errors never qualify."""
    remaining = deadline - time.monotonic()
    need(remaining > 0.05, "remaining original probe deadline")
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as stream:
            stream.settimeout(min(0.25, remaining / 2))
            code = stream.connect_ex(NETWORK)
    except TimeoutError:
        return {"qualified": False, "operation": "connect_ex", "endpoint": list(NETWORK),
                "errno": errno.ETIMEDOUT, "timed_out": True}
    except OSError as exc:
        return {"qualified": exc.errno in NETWORK_DENIAL, "operation": "connect_ex",
                "endpoint": list(NETWORK), "errno": exc.errno, "timed_out": False}
    return {"qualified": code in NETWORK_DENIAL, "operation": "connect_ex",
            "endpoint": list(NETWORK), "errno": code, "timed_out": code == errno.ETIMEDOUT}


def check_marker(path, phase_id):
    """One fixed path across phases; leave current state for Provider retirement."""
    body = canonical({"schema": "meg-generated-phase-marker/v1", "phase_id": phase_id})
    try:
        os.lstat(path)
    except FileNotFoundError:
        absent = True
    except OSError as exc:
        return {"qualified": False, "absent_before": None, "created": False,
                "readback_matches": False, "errno": exc.errno}
    else:
        return {"qualified": False, "absent_before": False, "created": False,
                "readback_matches": False, "errno": None}
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            written = os.write(fd, body)
            need(written == len(body), "complete marker write")
            os.fsync(fd)
        finally:
            os.close(fd)
        matches = read_bounded(path, 512) == body
    except OSError as exc:
        return {"qualified": False, "absent_before": absent, "created": False,
                "readback_matches": False, "errno": exc.errno}
    return {"qualified": matches, "absent_before": absent, "created": True,
            "readback_matches": matches, "errno": None}


def collect(input_dir, paper_path="/paper/PAPER.bin", request_path="/request.json"):
    request = json.loads(read_bounded(request_path, 262144))
    paper = json.loads(read_bounded(paper_path, 8192))
    context = json.loads(read_bounded(Path(input_dir) / "CONTEXT.json", 131072))
    phase, role = request.get("phase_id"), request.get("role")
    need(request.get("schema") == "osl_owned_phase_request_v1" and role in ("A", "B")
         and type(phase) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", phase), "current owned phase")
    fold = context.get("fold")
    need(type(fold) is int and fold in (0, 4) and phase.endswith(f"-{role}-fold-{fold:02d}"),
         "current selected role/fold request")
    deadline = request["clock"]["phase_deadline"]
    need(type(deadline) in (int, float) and math.isfinite(deadline)
         and time.monotonic() < deadline, "live original request deadline")
    need(paper.get("schema") == "meg-generated-boundary-paper/v1"
         and paper.get("generated_only") is True, "honest generated probe instructions")
    sentinel = paper["designated_private_sentinel_path"]
    need(type(sentinel) is str and Path(sentinel).is_absolute() and len(sentinel) <= 4096
         and paper.get("marker_path") == MARKER
         and paper.get("network_endpoint") == list(NETWORK), "fixed bounded probe operands")
    checks = {
        "private_sentinel": check_private(sentinel),
        "readonly_features": check_readonly(Path(input_dir) / "FEATURES.npy"),
        "external_network": check_network(deadline),
        "fresh_work_marker": check_marker(MARKER, phase),
    }
    need(time.monotonic() < deadline, "observations inside original phase deadline")
    return {"schema": SCHEMA, "phase_id": phase, "role": role, "fold": fold,
            "context_sha256": context["context_sha256"], "checks": checks,
            "qualified": all(row["qualified"] is True for row in checks.values()),
            "scientific_evaluation": False}


def validate_probe_result(body, *, phase_id, role, fold, context_sha256):
    """Recompute the engineering predicates from typed saved observations."""
    need(type(body) is dict and set(body) == {"schema", "phase_id", "role", "fold",
         "context_sha256", "checks", "qualified", "scientific_evaluation"}, "exact engineering result")
    need(body["schema"] == SCHEMA and body["phase_id"] == phase_id and body["role"] == role
         and type(body["fold"]) is int and body["fold"] == fold
         and body["context_sha256"] == context_sha256 and body["scientific_evaluation"] is False,
         "saved result joins current request and context")
    fields = {
        "private_sentinel": {"qualified", "operation", "opened", "errno"},
        "readonly_features": {"qualified", "operation", "opened_writable", "write_bytes", "errno"},
        "external_network": {"qualified", "operation", "endpoint", "errno", "timed_out"},
        "fresh_work_marker": {"qualified", "absent_before", "created", "readback_matches", "errno"},
    }
    checks = body["checks"]
    need(type(checks) is dict and set(checks) == set(fields), "all four engineering observations")
    for name, keys in fields.items():
        row = checks[name]
        need(type(row) is dict and set(row) == keys and type(row["qualified"]) is bool,
             "typed complete observation")
        need(row["errno"] is None or (type(row["errno"]) is int and 0 <= row["errno"] <= 4096),
             "bounded observed errno")
    private, readonly = checks["private_sentinel"], checks["readonly_features"]
    network, marker = checks["external_network"], checks["fresh_work_marker"]
    need(private["operation"] == "read_open" and type(private["opened"]) is bool,
         "designated private read observation")
    need(readonly["operation"] == "write_open_then_same_byte" and type(readonly["opened_writable"]) is bool
         and type(readonly["write_bytes"]) is int and 0 <= readonly["write_bytes"] <= 1,
         "bounded readonly write observation")
    need(network["operation"] == "connect_ex" and network["endpoint"] == list(NETWORK)
         and type(network["timed_out"]) is bool, "reserved endpoint connection observation")
    need((marker["absent_before"] is None or type(marker["absent_before"]) is bool)
         and type(marker["created"]) is bool and type(marker["readback_matches"]) is bool,
         "typed fixed-path state observation")
    computed = {
        "private_sentinel": private["opened"] is False and private["errno"] in PRIVATE_DENIAL,
        "readonly_features": readonly["opened_writable"] is False and readonly["write_bytes"] == 0
                             and readonly["errno"] in WRITE_DENIAL,
        "external_network": network["timed_out"] is False and network["errno"] in NETWORK_DENIAL,
        "fresh_work_marker": marker["absent_before"] is True and marker["created"] is True
                             and marker["readback_matches"] is True and marker["errno"] is None,
    }
    need(all(checks[name]["qualified"] is value for name, value in computed.items()),
         "per-check flags agree with observations")
    qualified = all(computed.values())
    need(type(body["qualified"]) is bool and body["qualified"] is qualified,
         "aggregate flag agrees with observations")
    return {"qualified": qualified, "checks": computed}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = collect(args.input)
    raw = canonical(result) + b"\n"
    need(len(raw) <= 16384, "bounded engineering response")
    fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        need(os.write(fd, raw) == len(raw), "complete engineering response")
        os.fsync(fd)
    finally:
        os.close(fd)


if __name__ == "__main__":
    main()
