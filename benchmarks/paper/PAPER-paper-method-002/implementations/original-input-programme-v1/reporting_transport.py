"""Bounded reporting transport for the two Jaxley generated input suites only.

This module imports no scientific package and has no public command dispatcher.
It does not provide runtime admission or enforce an RSS/CPU memory allocation.
"""

import hashlib
import json
import os
import selectors
import signal
import stat
import subprocess
import sys
import time

MAX_RESULT_BYTES = 65536
MAX_DIAGNOSTIC_BYTES = 65536
MAX_STDOUT_BYTES = 32768
MAX_SOURCE_BYTES = 65536
WORKER_SECONDS = 165.0
MAX_ERROR_BYTES = 4096


def require(condition, message):
    if not condition:
        raise ValueError(message)


def bounded_error(error):
    raw = (type(error).__name__ + ": " + str(error)).encode("utf-8", "replace")
    return raw[:MAX_ERROR_BYTES - 4].decode("utf-8", "replace")


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_size,
            st.st_mtime_ns, st.st_ctime_ns)


def _directory(path):
    """Open every absolute path component without following symbolic links."""
    value = os.fspath(path)
    require(type(value) is str and value.startswith("/"), "absolute directory required")
    parts = value.split("/")[1:]
    require(all(part not in ("", ".", "..") for part in parts) or value == "/",
            "noncanonical directory")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open("/", flags)
    try:
        for part in ([] if value == "/" else parts):
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd
    except BaseException:
        os.close(fd)
        raise


def read_source(root, relative_name, expected_bytes, expected_sha256):
    """Authenticate one fixed adjacent source and return the held bytes."""
    require(type(relative_name) is str and relative_name not in ("", ".", "..")
            and "/" not in relative_name and "\\" not in relative_name,
            "one source filename required")
    require(type(expected_bytes) is int and 0 < expected_bytes <= MAX_SOURCE_BYTES,
            "source extent bound")
    require(type(expected_sha256) is str and len(expected_sha256) == 64
            and all(ch in "0123456789abcdef" for ch in expected_sha256), "source digest")
    directory = _directory(root)
    fd = None
    try:
        fd = os.open(relative_name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                and before.st_size == expected_bytes, "source mode/link/extent")
        chunks, total = [], 0
        while total <= expected_bytes:
            part = os.read(fd, min(8192, expected_bytes + 1 - total))
            if not part:
                break
            chunks.append(part)
            total += len(part)
        body = b"".join(chunks)
        require(_identity(before) == _identity(os.fstat(fd)), "source changed during read")
        require(len(body) == expected_bytes and hashlib.sha256(body).hexdigest() == expected_sha256,
                "source bytes/digest")
        return body
    finally:
        if fd is not None:
            os.close(fd)
        os.close(directory)


def open_artifacts(path):
    """Create one entirely absent leaf; return its held directory descriptor."""
    value = os.fspath(path)
    require(type(value) is str and os.path.isabs(value), "absolute artifact leaf required")
    parent, leaf = os.path.split(value)
    require(leaf not in ("", ".", ".."), "artifact leaf required")
    directory = _directory(parent)
    try:
        os.mkdir(leaf, 0o700, dir_fd=directory)
        return os.open(leaf, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
    finally:
        os.close(directory)


def _encode(value, limit):
    body = (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")
    require(len(body) <= limit, "result byte bound")
    return body


def _write(fd, body):
    offset = 0
    while offset < len(body):
        count = os.write(fd, body[offset:])
        require(count > 0, "short output write")
        offset += count


def write_worker_report(fd, report):
    """The entry worker writes only to its separate inherited report pipe."""
    require(type(fd) is int and fd > 2 and stat.S_ISFIFO(os.fstat(fd).st_mode),
            "inherited result pipe required")
    try:
        _write(fd, _encode(report, MAX_RESULT_BYTES))
    finally:
        os.close(fd)


def trace_observations(error, function):
    """Observed labels are never advertised as completed controls on failure."""
    frame = error.__traceback__
    labels = []
    while frame is not None:
        if function is not None and frame.tb_frame.f_code is function.__code__:
            candidate = frame.tb_frame.f_locals.get("checks", [])
            if type(candidate) is list and len(candidate) <= 18836:
                labels = [item for item in candidate if type(item) is str]
        frame = frame.tb_next
    return {"trace_observed_check_labels": [item for item in labels if item != "mask-cell"],
            "trace_observed_mask_cell_labels": labels.count("mask-cell"),
            "trace_labels_are_completed_controls": False}


def _decode(body):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "duplicate result key")
            value[key] = item
        return value
    def bad_number(value):
        raise ValueError("nonfinite result number:" + value)
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad_number)


def _validate_report(report, expected_ids):
    require(type(report) is dict and report.get("status") in ("PASS", "FAIL"), "worker result status")
    if report["status"] == "PASS":
        require(report.get("controls") == list(expected_ids), "complete ordered control roster")
        require(type(report.get("scientific_result")) is dict, "scientific result object required")
    else:
        require(report.get("controls") == [], "failure must not publish passed controls")
        labels = report.get("trace_observed_check_labels", [])
        require(type(labels) is list and labels == list(expected_ids[:len(labels)]),
                "unconfirmed trace labels must be an exact roster prefix")
        require(report.get("trace_labels_are_completed_controls", False) is False,
                "partial trace cannot confirm controls")
        mask_count = report.get("trace_observed_mask_cell_labels", 0)
        require(type(mask_count) is int and 0 <= mask_count <= 18815, "observed mask label bound")
        require(type(report.get("error")) is str and len(report["error"].encode()) <= MAX_ERROR_BYTES,
                "bounded failure reason required")


class _Cancelled(RuntimeError):
    pass


def _cancel(signum, frame):
    raise _Cancelled("report transport signal " + str(signum))


def _cleanup(process):
    """Bounded direct-child cleanup; child remains in the outer owned group."""
    previous = {sig: signal.signal(sig, signal.SIG_IGN) for sig in (signal.SIGTERM, signal.SIGINT)}
    error = None
    try:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2.0)
    except Exception as exc:
        error = bounded_error(exc)
    finally:
        for sig, handler in previous.items():
            signal.signal(sig, handler)
    return error


def transport(command, artifact_dir, expected_ids, *, timeout_seconds=WORKER_SECONDS):
    """Run one of the two fixed entry workers; keep diagnostics out of stdout.

    The private Python callable is also exercised by synthetic stdlib transport
    fixtures. Neither public suite CLI accepts a command, roster or fixture mode.
    Invalid/preexisting artifact paths raise before any worker starts.
    """
    require(type(expected_ids) in (list, tuple) and 0 < len(expected_ids) <= 35
            and all(type(item) is str and 0 < len(item) <= 160 for item in expected_ids)
            and len(set(expected_ids)) == len(expected_ids), "fixed unique control roster")
    success_stdout = _encode({"controls": list(expected_ids)}, MAX_STDOUT_BYTES)
    require(type(timeout_seconds) in (int, float) and 0 < timeout_seconds <= WORKER_SECONDS,
            "finite worker deadline")
    require(type(command) in (list, tuple) and command and all(type(arg) is str for arg in command),
            "fixed entry command")
    directory = open_artifacts(artifact_dir)
    diagnostics_fd = result_fd = read_fd = write_fd = None
    process = selector = None
    previous = {}
    diagnostics_retained = diagnostics_observed = result_observed = 0
    report_body = bytearray()
    failure = None
    worker_report = None
    worker_report_validated = False
    cleanup_error = None
    started = time.monotonic()
    try:
        diagnostics_fd = os.open("DIAGNOSTICS.log", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory)
        result_fd = os.open("RESULT.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                            0o600, dir_fd=directory)
        try:
            for sig in (signal.SIGTERM, signal.SIGINT):
                previous[sig] = signal.signal(sig, _cancel)
            read_fd, write_fd = os.pipe()
            # No new session/group: the maintained outer runner can kill both
            # entry and worker together even if the entry receives SIGKILL.
            process = subprocess.Popen(list(command) + ["--worker-report-fd", str(write_fd)],
                                       stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, pass_fds=(write_fd,))
            os.close(write_fd)
            write_fd = None
            selector = selectors.DefaultSelector()
            selector.register(process.stdout, selectors.EVENT_READ, "diagnostics")
            selector.register(read_fd, selectors.EVENT_READ, "result")
            deadline = started + timeout_seconds
            while selector.get_map():
                require(time.monotonic() < deadline, "worker deadline exceeded")
                for key, _ in selector.select(min(0.05, max(0.0, deadline - time.monotonic()))):
                    part = os.read(key.fd, 4096)
                    if not part:
                        selector.unregister(key.fileobj)
                        continue
                    if key.data == "diagnostics":
                        diagnostics_observed += len(part)
                        kept = part[:MAX_DIAGNOSTIC_BYTES - diagnostics_retained]
                        _write(diagnostics_fd, kept)
                        diagnostics_retained += len(kept)
                        require(diagnostics_observed <= MAX_DIAGNOSTIC_BYTES, "diagnostic overflow")
                    else:
                        result_observed += len(part)
                        report_body.extend(part[:MAX_RESULT_BYTES - len(report_body)])
                        require(result_observed <= MAX_RESULT_BYTES, "worker result overflow")
            require(time.monotonic() < deadline, "worker deadline exceeded")
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
            worker_report = _decode(bytes(report_body))
            _validate_report(worker_report, expected_ids)
            worker_report_validated = True
            require(process.returncode == 0 and worker_report["status"] == "PASS",
                    "worker did not complete successfully")
        except Exception as exc:
            failure = bounded_error(exc)
        finally:
            cleanup_error = _cleanup(process)
            if cleanup_error is not None:
                failure = "worker cleanup failed: " + cleanup_error
            if selector is not None:
                selector.close()
            if process is not None and process.stdout is not None:
                process.stdout.close()
            for fd in (read_fd, write_fd):
                if fd is not None:
                    os.close(fd)
            read_fd = write_fd = None
            for sig, handler in previous.items():
                signal.signal(sig, handler)
            previous = {}
        report = {"schema": "jaxley-input-report-transport-v1", "status": "FAIL" if failure else "PASS",
                  "controls": [] if failure else list(expected_ids),
                  "expected_controls": list(expected_ids),
                  "unconfirmed_controls": list(expected_ids) if failure else [],
                  "worker_exit": None if process is None else process.returncode,
                  "error": failure, "worker_result": worker_report,
                  "worker_result_validated": worker_report_validated,
                  "diagnostics": {"file": "DIAGNOSTICS.log", "retained_bytes": diagnostics_retained,
                                  "observed_bytes": diagnostics_observed,
                                  "overflow": diagnostics_observed > MAX_DIAGNOSTIC_BYTES},
                  "worker_report_observed_bytes": result_observed,
                  "resource_authority": False}
        try:
            encoded = _encode(report, MAX_RESULT_BYTES)
        except Exception as exc:
            failure = bounded_error(exc)
            report.update(status="FAIL", controls=[], unconfirmed_controls=list(expected_ids),
                          error=failure, worker_result=None)
            encoded = _encode(report, MAX_RESULT_BYTES)
        _write(result_fd, encoded)
        os.fsync(diagnostics_fd)
        os.fsync(result_fd)
        if failure is None:
            sys.stdout.write(success_stdout.decode("utf-8"))
            sys.stdout.flush()
            return 0
        return 1
    finally:
        for fd in (diagnostics_fd, result_fd):
            if fd is not None:
                os.close(fd)
        os.close(directory)
