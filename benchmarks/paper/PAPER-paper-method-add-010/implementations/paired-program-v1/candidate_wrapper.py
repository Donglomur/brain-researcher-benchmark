"""Fixed candidate ABI inside an independently owned Provider producer.

This wrapper does not sandbox Python or establish descendant absence. The
Provider owns the process namespace, mounts, limits, capture and whole-producer
retirement. No scientific values or private targets are interpreted here.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import subprocess
import time


REQUEST_CAP = 262144
RESULT_CAP = 1048576
MANIFEST_CAP = 4096


def need(condition, message):
    if not condition:
        raise ValueError(message)


def pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       allow_nan=False) + "\n").encode("utf-8")


def decode(body):
    def unique(rows):
        value = {}
        for key, item in rows:
            need(key not in value, "Duplicate request key")
            value[key] = item
        return value
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, "Finite JSON required"))


def signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def capture(path, cap, *, dir_fd=None):
    """Capture bounded ordinary file bytes without following a final link."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                 dir_fd=dir_fd)
    with os.fdopen(fd, "rb") as handle:
        before = os.fstat(handle.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, "Bounded singly linked regular file")
        body = handle.read(cap + 1)
        after = os.fstat(handle.fileno())
        need(signature(before) == signature(after) and len(body) == before.st_size,
             "Captured file changed")
    current = os.stat(path, dir_fd=dir_fd, follow_symlinks=False)
    need(signature(current) == signature(before), "Captured path changed")
    return body, signature(before)


def request_limits(request, now):
    need(type(request) is dict
         and request.get("schema") == "osl_owned_phase_request_v1",
         "Exact owned phase request")
    phase = request.get("phase_id")
    need(type(phase) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,96}", phase),
         "Bounded phase identity")
    clock = request.get("clock")
    need(type(clock) is dict and set(clock) == {"origin", "phase_deadline"},
         "Original monotonic clock")
    need(all(type(v) in (int, float) and math.isfinite(v) for v in clock.values())
         and 0 <= clock["origin"] <= now < clock["phase_deadline"],
         "Live original phase deadline; no refreshed allowance")
    resources = request.get("resources")
    need(type(resources) is dict, "Bound output resources")
    keys = ("max_file_bytes", "max_output_bytes", "manifest_bytes", "cleanup_seconds")
    need(all(type(resources.get(k)) is int and 0 < resources[k] <= 2**63 - 1
             for k in keys), "Positive bounded output resource integers")
    need(resources["manifest_bytes"] <= resources["max_file_bytes"]
         <= resources["max_output_bytes"], "Nested output ceilings")
    need(request.get("output") == {"kind": "generic", "manifest": "OUTPUTS.json"},
         "Exact generic output envelope")
    return clock["phase_deadline"], resources


def directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    info = os.fstat(fd)
    need(stat.S_ISDIR(info.st_mode), "Ordinary output directory")
    return fd, (info.st_dev, info.st_ino)


def unchanged_directory(path, fd, original):
    live = os.stat(path, follow_symlinks=False)
    owned = os.fstat(fd)
    need(stat.S_ISDIR(live.st_mode)
         and (live.st_dev, live.st_ino) == original
         and (owned.st_dev, owned.st_ino) == original,
         "Output directory identity changed")


def run(*, _generated=None):
    """Run fixed paths; the explicit fixture seam never certifies isolation.

    `_generated` selects only absolute generated fixture paths and an existing
    interpreter. Production CLI supplies no seam or configuration arguments.
    """
    paths = {"request": "/request.json", "program": "/program/submission.py",
             "input": "/input", "output": "/output",
             "python": "/usr/local/bin/python"}
    if _generated is not None:
        need(type(_generated) is dict and set(_generated) == set(paths),
             "Explicit complete generated fixture binding")
        need(all(type(v) is str and Path(v).is_absolute()
                 for v in _generated.values()), "Absolute generated fixture paths")
        paths = dict(_generated)
    raw, request_identity = capture(paths["request"], REQUEST_CAP)
    request = decode(raw)
    end, limits = request_limits(request, time.monotonic())
    output_fd, output_identity = directory(paths["output"])
    child = None
    try:
        need(not os.listdir(output_fd), "Output must initially be empty")
        argv = [paths["python"], "-I", "-B", paths["program"], "--input",
                paths["input"], "--output", str(Path(paths["output"]) / "RESULT.json")]
        remaining = end - time.monotonic()
        need(remaining > 0, "Original phase deadline before candidate launch")
        # Keep a small direct-child reap interval inside this same deadline.
        # The Provider's producer clock remains independently authoritative;
        # this does not renew it or claim whole-descendant cleanup.
        cleanup_reserve = min(1.0, remaining / 10, limits["cleanup_seconds"])
        candidate_end = end - cleanup_reserve
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                 close_fds=True, start_new_session=False)
        try:
            code = child.wait(timeout=max(0, candidate_end - time.monotonic()))
        except BaseException:
            # Kill only this exact direct child. Provider containment, not a
            # wrapper-level process-group assertion, retires any descendants.
            if child.poll() is None:
                child.kill()
                try:
                    child.wait(timeout=max(0, end - time.monotonic()))
                except subprocess.TimeoutExpired:
                    pass
            raise
        need(code == 0, "Candidate must exit successfully")
        need(time.monotonic() < end, "Original phase deadline after candidate exit")
        unchanged_directory(paths["output"], output_fd, output_identity)
        need(set(os.listdir(output_fd)) == {"RESULT.json"},
             "Exactly one candidate result; no extras or directories")
        result, result_identity = capture("RESULT.json",
            min(limits["max_file_bytes"], RESULT_CAP), dir_fd=output_fd)
        after_raw, after_identity = capture(paths["request"], REQUEST_CAP)
        need(after_raw == raw and after_identity == request_identity,
             "Request bytes and identity must remain unchanged")
        manifest = {"schema": "osl_transport_output_manifest_v1",
                    "phase_id": request["phase_id"],
                    "request_sha256": pin(raw)["sha256"],
                    "files": {"RESULT.json": pin(result)}}
        body = encoded(manifest)
        need(len(body) <= min(limits["manifest_bytes"], MANIFEST_CAP)
             and len(result) + len(body) <= limits["max_output_bytes"],
             "Complete result and manifest fit original resource ceilings")
        need(time.monotonic() < end, "Original phase deadline before publication")
        fd = os.open("OUTPUTS.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                     os.O_NOFOLLOW, 0o444, dir_fd=output_fd)
        with os.fdopen(fd, "wb") as handle:
            handle.write(body)
            handle.flush()
            os.fchmod(handle.fileno(), 0o444)
            os.fsync(handle.fileno())
        unchanged_directory(paths["output"], output_fd, output_identity)
        need(set(os.listdir(output_fd)) == {"RESULT.json", "OUTPUTS.json"},
             "No late output additions")
        final_result, final_identity = capture("RESULT.json",
            min(limits["max_file_bytes"], RESULT_CAP), dir_fd=output_fd)
        final_request, final_request_identity = capture(paths["request"], REQUEST_CAP)
        need(final_result == result and final_identity == result_identity,
             "Result changed during manifest publication")
        need(final_request == raw and final_request_identity == request_identity,
             "Request changed during publication")
        need(time.monotonic() < end, "Publication remains inside original deadline")
        return manifest
    finally:
        os.close(output_fd)


def main():
    run()


if __name__ == "__main__":
    main()
