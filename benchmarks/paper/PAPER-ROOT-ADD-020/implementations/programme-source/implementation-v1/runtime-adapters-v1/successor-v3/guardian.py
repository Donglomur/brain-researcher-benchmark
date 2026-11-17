"""Container PID1 guardian; import is inert, executable entry requires a request.

The external image qualification must install this exact file, Python and worker
in a private PID namespace. The guardian never signals a process/group. It waits
for its worker and adopted descendants to exit naturally. Reaching ECHILD is
necessary; main-worker exit alone is insufficient. A deadline/interruption or
output overflow produces sticky failure even if later wait statuses are zero.

The independent host observer additionally verifies Docker events and qualified
kernel counters; this envelope alone cannot certify isolation or logical I/O.
"""
from __future__ import annotations

import argparse
import base64
import ctypes
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import selectors
import signal
import stat
import subprocess
import time


class GuardianError(RuntimeError):
    pass


def need(value, message):
    if not value:
        raise GuardianError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def hash_file(path, extent):
    """Image/view paths are exact regular files; all symlink components refused."""
    p = PurePosixPath(path)
    need(p.is_absolute() and str(p) == path and ".." not in p.parts, "Unsafe file path")
    need(type(extent) is int and 0 <= extent <= 1 << 34, "Unbounded file extent")
    parent = os.open("/", os.O_RDONLY | os.O_DIRECTORY); fd = None
    try:
        for part in p.parts[1:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent); parent = next_fd
        fd = os.open(p.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_size == extent, "Exact regular file extent required")
        h = hashlib.sha256(); count = 0
        while count < extent:
            chunk = os.read(fd, min(65536, extent - count)); need(chunk, "Premature EOF")
            h.update(chunk); count += len(chunk)
        need(os.read(fd, 1) == b"", "File grew")
        after = os.fstat(fd)
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
             == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "File changed")
        return h.hexdigest()
    finally:
        if fd is not None:
            os.close(fd)
        os.close(parent)


def validate_request(request):
    keys = {"schema", "nonce", "phase_id", "binding_digest", "implementation_digest", "origin_ns", "deadline_ns",
            "argv", "guardian_sha256", "worker_sha256", "guardian_bytes", "worker_bytes", "mounts",
            "input_digest", "model_digest", "source_digest", "limits", "worker_path", "python_path", "result_path"}
    need(type(request) is dict and set(request) == keys and request["schema"] == "paper020_guardian_request_v1",
         "Exact guardian request schema required")
    need(type(request["nonce"]) is str and re.fullmatch(r"[0-9a-f]{48}", request["nonce"]), "Invalid nonce")
    for key in ("binding_digest", "implementation_digest", "guardian_sha256", "worker_sha256", "input_digest", "source_digest"):
        need(type(request[key]) is str and re.fullmatch(r"[0-9a-f]{64}", request[key]), "Invalid digest")
    need(request["model_digest"] is None or (type(request["model_digest"]) is str and re.fullmatch(r"[0-9a-f]{64}", request["model_digest"])), "Invalid model digest")
    for key in ("origin_ns", "deadline_ns", "guardian_bytes", "worker_bytes"):
        need(type(request[key]) is int and request[key] > 0, "Positive integer required")
    need(request["deadline_ns"] > request["origin_ns"], "Deadline precedes origin")
    for key in ("phase_id", "python_path", "worker_path", "result_path"):
        need(type(request[key]) is str and 0 < len(request[key].encode()) <= 4096
             and not any(ord(c) < 32 or ord(c) == 127 for c in request[key]), "Unsafe string")
    need(request["result_path"] == "/scratch/output/result.json", "Exact bounded output path required")
    argv = request["argv"]
    need(type(argv) is list and 4 <= len(argv) <= 64
         and argv[:4] == [request["python_path"], "-I", "-B", request["worker_path"]], "Pinned isolated Python worker invocation required")
    for arg in argv:
        need(type(arg) is str and 0 < len(arg.encode()) <= 4096
             and not any(ord(c) < 32 or ord(c) == 127 for c in arg), "Unsafe worker argv")
    mounts = request["mounts"]
    need(type(mounts) is list and 0 < len(mounts) <= 128, "Bounded exact view required")
    for mount in mounts:
        need(type(mount) is dict and set(mount) == {"path", "bytes", "sha256", "role"}
             and type(mount["path"]) is str and mount["path"].startswith("/paper020-view/")
             and mount["role"] in {"source", "input", "request", "model"}, "Malformed immutable view")
        p = PurePosixPath(mount["path"])
        need(str(p) == mount["path"] and ".." not in p.parts
             and type(mount["bytes"]) is int and 0 <= mount["bytes"] <= 1 << 34
             and type(mount["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", mount["sha256"]), "Malformed mount binding")
    need(len({m["path"] for m in mounts}) == len(mounts), "Duplicate mount")
    required_limits = {"memory_bytes", "scratch_bytes", "pids", "cpus", "stdout_bytes", "stderr_bytes", "trace_bytes",
                       "read_bytes", "write_bytes", "retained_bytes", "live_bytes"}
    need(type(request["limits"]) is dict and set(request["limits"]) == required_limits
         and all(type(v) is int and v > 0 for v in request["limits"].values()), "Exact positive resource limits required")
    need(all(v <= (1 << 63) - 1 for v in request["limits"].values())
         and request["limits"]["stdout_bytes"] * 4 + request["limits"]["stderr_bytes"] <= request["limits"]["memory_bytes"]
         and request["limits"]["trace_bytes"] >= request["limits"]["stdout_bytes"] + 4096,
         "Profile must bound complete encoded output, copies and logs")


class LinuxOperations:
    """Real operations selected only by executable main; no production calls in tests."""
    def __init__(self):
        self.selector = selectors.DefaultSelector()
        self.child = None
        self.interrupted = False

    def clock(self):
        return time.monotonic_ns()

    def prepare(self):
        need(os.getpid() == 1, "Guardian must be private namespace PID1")
        libc = ctypes.CDLL(None, use_errno=True)
        need(libc.prctl(36, 1, 0, 0, 0) == 0, "PR_SET_CHILD_SUBREAPER failed")
        # Same-UID worker access to /proc/1/{mem,fd/*} must not expose the
        # guardian's terminal channel or mutable address space.
        need(libc.prctl(4, 0, 0, 0, 0) == 0, "PR_SET_DUMPABLE protection failed")
        def interrupt(signum, _frame):
            self.interrupted = True
        for signum in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            signal.signal(signum, interrupt)

    def verify(self, request):
        need(hash_file(os.path.abspath(__file__), request["guardian_bytes"]) == request["guardian_sha256"], "Guardian source changed")
        need(hash_file(request["worker_path"], request["worker_bytes"]) == request["worker_sha256"], "Worker source changed")
        for mount in request["mounts"]:
            need(hash_file(mount["path"], mount["bytes"]) == mount["sha256"], "View seal changed")

    def spawn(self, argv):
        self.child = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd="/scratch", env={"PATH": "/usr/bin:/bin", "LC_ALL": "C", "HOME": "/scratch", "TMPDIR": "/scratch",
                                  "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"},
            shell=False, close_fds=True)
        for name, stream in (("stdout", self.child.stdout), ("stderr", self.child.stderr)):
            os.set_blocking(stream.fileno(), False)
            self.selector.register(stream, selectors.EVENT_READ, name)
        return self.child.pid

    def read(self, timeout):
        chunks = []
        for key, _ in self.selector.select(timeout):
            chunk = os.read(key.fileobj.fileno(), 65536)
            if chunk:
                chunks.append((key.data, chunk))
            else:
                self.selector.unregister(key.fileobj); key.fileobj.close()
        return chunks, not self.selector.get_map()

    def reap(self):
        statuses = []
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                return statuses, True
            if pid == 0:
                return statuses, False
            code = os.waitstatus_to_exitcode(status)
            statuses.append((pid, code))
            if self.child is not None and pid == self.child.pid:
                self.child.returncode = code  # It was reaped here; Popen must not wait again.

    def output(self, request):
        """Collect only bounded regular manifest/blob files after ECHILD.

        result.json is opaque to this process layer; the owner validates its
        typed array schema after independent natural closure. Blobs use exact
        SHA-256 basenames; no arbitrary result-manifest path is followed.
        """
        root = "/scratch/output"; maximum = request["limits"]["stdout_bytes"]
        rootfd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        files = {}; total = 0
        try:
            names = os.listdir(rootfd)
            need(len(names) <= 512 and "result.json" in names, "Bounded result manifest required")
            def read_one(name):
                nonlocal total
                need(name == "result.json" or re.fullmatch(r"[0-9a-f]{64}\.bin", name), "Unexpected output filename")
                fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=rootfd)
                try:
                    before = os.fstat(fd)
                    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
                         and before.st_size <= maximum - total, "Unsafe or oversized output file")
                    body = bytearray()
                    while len(body) < before.st_size:
                        chunk = os.read(fd, min(65536, before.st_size - len(body))); need(chunk, "Output EOF")
                        body.extend(chunk)
                    need(os.read(fd, 1) == b"", "Output grew")
                    after = os.fstat(fd)
                    need((before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                         == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), "Output changed")
                    sha = hashlib.sha256(body).hexdigest()
                    need(name == "result.json" or name == sha + ".bin", "Content-addressed output digest mismatch")
                    total += len(body)
                    files[name] = bytes(body)
                finally:
                    os.close(fd)
            read_one("result.json")
            def pairs(items):
                result = {}
                for key, value in items:
                    need(key not in result, "Duplicate manifest key"); result[key] = value
                return result
            manifest = json.loads(files["result.json"].decode(), object_pairs_hook=pairs,
                parse_constant=lambda _: (_ for _ in ()).throw(GuardianError("Nonfinite manifest")))
            need(type(manifest) is dict and set(manifest) == {"schema", "root", "blobs"}
                 and manifest["schema"] == "paper020_wire_manifest_v1" and type(manifest["blobs"]) is dict,
                 "Exact wire manifest required")
            expected = {"result.json"}
            for sha, record in manifest["blobs"].items():
                need(type(sha) is str and re.fullmatch(r"[0-9a-f]{64}", sha)
                     and type(record) is dict and set(record) == {"file", "bytes", "sha256"}
                     and record["sha256"] == sha and record["file"] == sha + ".bin"
                     and type(record["bytes"]) is int and record["bytes"] >= 0, "Malformed output blob binding")
                expected.add(record["file"])
            need(set(names) == expected, "Undeclared or missing output files")
            for sha, record in manifest["blobs"].items():
                read_one(record["file"])
                need(len(files[record["file"]]) == record["bytes"], "Manifest/blob extent mismatch")
            encoded = canonical({"manifest_base64": base64.b64encode(files["result.json"]).decode(),
                                 "blobs_base64": {sha: base64.b64encode(files[sha + ".bin"]).decode() for sha in manifest["blobs"]}})
            need(len(encoded) <= maximum, "Encoded output bundle exceeds stdout limit")
            return encoded
        finally:
            os.close(rootfd)

    def finish(self):
        for key in list(self.selector.get_map().values()):
            key.fileobj.close()
        self.selector.close()


def run_guardian(request, ops):
    """Deterministic state machine; tests supply RAM operations, never subprocesses."""
    validate_request(request)
    failures = []; stdout = bytearray(); stderr = bytearray(); reaped = []
    main_pid = None; main_code = None; empty = eof = False; payload = b""
    def clock_guard():
        now = ops.clock()
        need(type(now) is int and request["origin_ns"] <= now < request["deadline_ns"], "Original strict deadline exceeded")
        return now
    try:
        clock_guard(); ops.prepare(); ops.verify(request); clock_guard()
        main_pid = ops.spawn(request["argv"])
        need(type(main_pid) is int and main_pid > 1, "Owned child identifier required")
        while True:
            now = clock_guard()
            need(not ops.interrupted, "Guardian interrupted")
            chunks, eof = ops.read(min(.01, (request["deadline_ns"] - now) / 1e9))
            for name, chunk in chunks:
                need(name in ("stdout", "stderr") and type(chunk) is bytes, "Invalid child pipe event")
                target = stdout if name == "stdout" else stderr
                cap = request["limits"][name + "_bytes"]
                remaining = cap - len(target); target.extend(chunk[:remaining])
                need(len(chunk) <= remaining, "Child pipe bound exceeded")
            statuses, empty = ops.reap()
            for pid, code in statuses:
                need(type(pid) is int and type(code) is int and len(reaped) < 4096, "Reap evidence bound")
                reaped.append((pid, code))
                if pid == main_pid:
                    need(main_code is None, "Duplicate main wait")
                    main_code = code
                if code != 0:
                    failures.append("nonzero_descendant")
            clock_guard()
            if empty and eof:
                need(main_code is not None, "ECHILD without observed main exit")
                break
        # A naturally reaped nonzero worker may have written a complete failure
        # artifact. Retain its bound bytes without erasing any nonzero status.
        # Timeout/interruption/unknown descendants never reach this branch.
        need(main_code is not None and not ops.interrupted, "Observed child closure required for output custody")
        ops.verify(request); clock_guard()
        payload = ops.output(request); need(type(payload) is bytes and len(payload) <= request["limits"]["stdout_bytes"], "Output bundle bound")
        clock_guard()
    except BaseException as exc:
        failures.append(type(exc).__name__ + ":" + str(exc)[:256])
    finally:
        ops.finish()
    finished = ops.clock()
    if not (type(finished) is int and request["origin_ns"] <= finished < request["deadline_ns"]):
        failures.append("final_original_deadline")
    complete = not failures and empty and eof and main_code == 0
    bundle = json.loads(payload) if payload else {}
    manifest_hash = hashlib.sha256(base64.b64decode(bundle["manifest_base64"], validate=True)).hexdigest() if payload else None
    terminal = {"schema": "paper020_guardian_terminal_v1", **{k: request[k] for k in
        ("nonce", "phase_id", "binding_digest", "implementation_digest", "origin_ns", "deadline_ns", "input_digest", "model_digest", "source_digest",
         "worker_sha256", "guardian_sha256")}, "finished_ns": finished,
        "natural_complete": complete, "all_descendants_closed": complete, "exit_code": main_code,
        "descendants_reaped": empty and eof and main_code is not None,
        "all_wait_statuses_zero": bool(reaped) and all(code == 0 for _, code in reaped),
        "reaped_count": len(reaped), "reap_digest": digest(reaped), "mounts_digest": digest(request["mounts"]),
        "output_bundle": bundle, "stdout_sha256": hashlib.sha256(payload).hexdigest(), "result_manifest_sha256": manifest_hash,
        "worker_stdout_bytes": len(stdout), "worker_stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "worker_stderr_bytes": len(stderr), "worker_stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "failures": failures}
    if len(canonical(terminal)) + 1 > request["limits"]["trace_bytes"]:
        terminal["natural_complete"] = terminal["all_descendants_closed"] = False
        terminal["failures"].append("terminal_trace_bound")
        terminal["output_bundle"] = {}; terminal["stdout_sha256"] = hashlib.sha256(b"").hexdigest()
    return terminal


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-base64", required=True)
    args = parser.parse_args(argv)
    need(len(args.config_base64) < 120000, "Request byte cap")
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, "Duplicate request key"); result[key] = value
        return result
    request = json.loads(base64.b64decode(args.config_base64, validate=True).decode(), object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(GuardianError("Nonfinite request")))
    terminal = run_guardian(request, LinuxOperations())
    encoded = canonical(terminal) + b"\n"
    need(len(encoded) <= request["limits"]["trace_bytes"], "Terminal exceeds bound")
    # All child pipes are drained/closed first. Exactly one guardian record is emitted.
    offset = 0
    while offset < len(encoded):
        offset += os.write(1, encoded[offset:])
    return 0 if terminal["natural_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
