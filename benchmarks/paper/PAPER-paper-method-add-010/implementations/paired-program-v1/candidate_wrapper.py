"""Fixed candidate ABI inside an independently owned Provider producer.

This wrapper does not sandbox Python or establish descendant absence. The
Provider owns the process namespace, mounts, limits, capture and whole-producer
retirement. No scientific values or private targets are interpreted here.
"""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import selectors
import stat
import subprocess
import time


REQUEST_CAP = 262144
RESULT_CAP = 1048576
MANIFEST_CAP = 4096
CHILD_PREFIX_BYTES = 512
CHILD_DRAIN_CHUNK = 65536
WRAPPER_TRACE_BYTES = 768
DIAGNOSTIC_ENVELOPE_CAP = 3584
OUTPUT_DIRECTORY_METADATA_CAP = 512
OUTPUT_DIRECTORY_NAME_BYTES = 32
OUTPUT_DIRECTORY_MARKER = b"\noutput_directory="


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


def _diagnostic_state():
    return {"child_returncode": None, "streams": {
        name: {"prefix": bytearray(), "observed_bytes": 0,
               "counter_saturated": False, "truncated": False, "eof": False}
        for name in ("stdout", "stderr")}}


def _drain_child(child, candidate_end, state):
    """Drain while the direct child runs; retained-prefix exhaustion is not failure.

    The Provider still owns the whole producer namespace and its clock. We do
    not wait for descendant-held pipe EOF after the direct child has exited.
    """
    selector = selectors.DefaultSelector()
    def consume(key):
        try:
            block = os.read(key.fileobj.fileno(), CHILD_DRAIN_CHUNK)
        except BlockingIOError:
            return
        row = state["streams"][key.data]
        if not block:
            row["eof"] = True
            selector.unregister(key.fileobj)
            return
        count = row["observed_bytes"] + len(block)
        row["counter_saturated"] |= count > 2**63 - 1
        row["observed_bytes"] = min(count, 2**63 - 1)
        room = CHILD_PREFIX_BYTES - len(row["prefix"])
        row["prefix"].extend(block[:room])
        row["truncated"] |= len(block) > room
        # Excess bytes are deliberately discarded, with no byte-volume gate.
    try:
        for name in ("stdout", "stderr"):
            stream = getattr(child, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        while child.poll() is None:
            remaining = candidate_end - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(child.args, 0)
            if not selector.get_map():
                time.sleep(min(.01, remaining))
                continue
            for key, _ in selector.select(min(.05, remaining)):
                consume(key)
        state["child_returncode"] = child.returncode
        # One bounded, nonblocking sweep catches already buffered tail bytes.
        # Open descendant writers never become a new prediction-admission gate.
        for key in list(selector.get_map().values()):
            consume(key)
        return child.returncode
    finally:
        selector.close()
        for name in ("stdout", "stderr"):
            stream = getattr(child, name)
            if stream is not None:
                stream.close()


def _output_directory_metadata(output_fd, original_identity):
    """Bounded later observation through the checked fd; never read entry contents."""
    value = {"v": 1, "dir": None, "entries": [], "more": None,
             "race": "unknown", "truncated": False, "unknown": False, "errors": []}
    before = None
    try:
        before = os.fstat(output_fd)
        value["dir"] = [before.st_dev, before.st_ino, before.st_mode]
    except BaseException:
        value["unknown"] = True; value["errors"].append("before")
    try:
        with os.scandir(output_fd) as entries:
            for _ in range(2):
                try:
                    entry = next(entries)
                except StopIteration:
                    value["more"] = False
                    break
                name = os.fsencode(entry.name)
                clipped = len(name) > OUTPUT_DIRECTORY_NAME_BYTES
                row = [base64.b64encode(name[:OUTPUT_DIRECTORY_NAME_BYTES]).decode("ascii"),
                       clipped, "?", None, None, None]
                value["truncated"] |= clipped
                try:
                    info = os.stat(entry.name, dir_fd=output_fd, follow_symlinks=False)
                    row[2] = ("f" if stat.S_ISREG(info.st_mode) else "d" if stat.S_ISDIR(info.st_mode)
                              else "l" if stat.S_ISLNK(info.st_mode) else "o")
                    row[3:] = [info.st_dev, info.st_ino, info.st_mode]
                except BaseException:
                    value["unknown"] = True; value["errors"].append("entry")
                value["entries"].append(row)
            else:
                try:
                    next(entries)  # One probe only; no metadata read for this entry.
                    value["more"] = True; value["truncated"] = True
                except StopIteration:
                    value["more"] = False
    except BaseException:
        value["unknown"] = True; value["errors"].append("scan")
    try:
        after = os.fstat(output_fd)
        if before is not None:
            stable = (stat.S_ISDIR(before.st_mode) and stat.S_ISDIR(after.st_mode)
                      and (before.st_dev, before.st_ino) == original_identity
                      and (after.st_dev, after.st_ino) == original_identity
                      and signature(before) == signature(after))
            value["race"] = "not_observed" if stable else "changed"
    except BaseException:
        value["unknown"] = True; value["errors"].append("after")
    raw = encoded(value)
    if len(raw) > OUTPUT_DIRECTORY_METADATA_CAP:
        # Keep valid complete JSON rather than slicing encoded metadata.
        raw = encoded({"v": 1, "dir": None, "entries": [], "more": None,
                       "race": "unknown", "truncated": True, "unknown": True,
                       "errors": ["metadata_cap"]})
    return raw


def _emit_diagnostic(state, error):
    """One bounded private failure envelope; successful runs emit no progress."""
    kind = type(error).__name__.encode("ascii", "replace")[:64].decode("ascii")
    message = error.args[0][:192] if error.args and type(error.args[0]) is str else ""
    lines = [kind + ": " + message]
    tb = error.__traceback__
    for _ in range(8):
        if tb is None:
            break
        code = tb.tb_frame.f_code
        lines.append(code.co_filename[-128:] + ":" + str(tb.tb_lineno) + ":" + code.co_name[:64])
        tb = tb.tb_next
    trace = "\n".join(lines).encode("utf-8", "replace")[:WRAPPER_TRACE_BYTES]
    metadata = state.get("output_directory_metadata")
    if metadata is not None:
        need(type(metadata) is bytes and len(metadata) <= OUTPUT_DIRECTORY_METADATA_CAP,
             "Bounded private directory metadata")
        suffix = OUTPUT_DIRECTORY_MARKER + metadata
        trace = trace[:WRAPPER_TRACE_BYTES - len(suffix)] + suffix
    streams = {}
    for name, row in state["streams"].items():
        prefix = bytes(row["prefix"])
        streams[name] = {"observed_bytes": row["observed_bytes"],
            "counter_saturated": row["counter_saturated"], "retained_bytes": len(prefix),
            "prefix_base64": base64.b64encode(prefix).decode("ascii"),
            "truncated": row["truncated"], "eof": row["eof"]}
    raw = encoded({"schema": "meg_private_wrapper_diagnostics_v1",
        "child_returncode": state["child_returncode"], "streams": streams,
        "wrapper_traceback_bytes": len(trace),
        "wrapper_traceback_base64": base64.b64encode(trace).decode("ascii"),
        "diagnostic_only": True, "candidate_artifact": False})
    need(len(raw) <= DIAGNOSTIC_ENVELOPE_CAP, "Bounded trusted diagnostic envelope")
    need(os.write(2, raw) == len(raw), "Complete private diagnostic envelope write")


def _run(*, _generated=None, _diagnostic):
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
        # Child progress never enters the bounded outer CLI attachment directly.
        # Drain and discard excess inside this same producer's resource bounds.
        child = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 close_fds=True, start_new_session=False, bufsize=0)
        try:
            code = _drain_child(child, candidate_end, _diagnostic)
        except BaseException:
            # Kill only this exact direct child. Provider containment, not a
            # wrapper-level process-group assertion, retires any descendants.
            if child.poll() is None:
                child.kill()
                try:
                    child.wait(timeout=max(0, end - time.monotonic()))
                except subprocess.TimeoutExpired:
                    pass
            _diagnostic["child_returncode"] = child.returncode
            raise
        need(code == 0, "Candidate must exit successfully")
        need(time.monotonic() < end, "Original phase deadline after candidate exit")
        unchanged_directory(paths["output"], output_fd, output_identity)
        result_entries = set(os.listdir(output_fd))
        if result_entries != {"RESULT.json"}:
            try:
                _diagnostic["output_directory_metadata"] = _output_directory_metadata(output_fd, output_identity)
            except BaseException:
                _diagnostic["output_directory_metadata"] = encoded({"v": 1, "entries": [],
                    "more": None, "race": "unknown", "truncated": True, "unknown": True,
                    "errors": ["unavailable"]})
        need(result_entries == {"RESULT.json"},
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


def run(*, _generated=None):
    """Unchanged public ABI; failure diagnostics are private, bounded and optional."""
    state = _diagnostic_state()
    try:
        return _run(_generated=_generated, _diagnostic=state)
    except BaseException as error:
        try:
            _emit_diagnostic(state, error)
        except BaseException as diagnostic_error:
            # Never replace the candidate/contract failure with a logging error.
            error.add_note("Private diagnostic emission failed: " + type(diagnostic_error).__name__[:96])
        raise


def main(*, _generated=None):
    try:
        run(_generated=_generated)
    except BaseException:
        # run() already emitted the bounded trusted traceback envelope. Avoid an
        # uncapped duplicate interpreter traceback on the outer attachment.
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
