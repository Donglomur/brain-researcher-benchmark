"""Offline authenticated relay with bounded, explicitly untrusted computation reports.

Only the trusted host selects provider/configuration and authenticates model
actions. Generated Python/R executes inside this existing candidate container.
Its report cannot establish trusted resource usage or scientific compliance.
"""
import base64
import hashlib
import hmac
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
import tempfile
import time

FRAME_CAP = 2 * 1024 * 1024
CANDIDATE_CWD = "/output"
CHILD_ENV = {"PATH": "/usr/local/bin:/usr/bin:/bin", "LANG": "C.UTF-8",
             "HOME": "/tmp", "TMPDIR": "/tmp", "OPENBLAS_NUM_THREADS": "1",
             "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}

def need(ok, why):
    if not ok:
        raise ValueError(why)

def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()

def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()

def parse(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, "duplicate_key")
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
        parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite")))

def read():
    body = sys.stdin.buffer.readline(FRAME_CAP + 1)
    need(body.endswith(b"\n") and len(body) <= FRAME_CAP, "bounded_complete_frame")
    return parse(body)

class ComputationFailure(ValueError):
    pass

def compute_need(ok, code):
    if not ok:
        raise ComputationFailure(code)

def finite_positive(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0

def positive_int(value, cap):
    return type(value) is int and 0 < value <= cap

def process_group_absent(process):
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        return True
    return False

def compute(payload):
    """Run exactly one selected source body, owning only its group and source file.

    Local observations are candidate-reported and untrusted. Generated code may
    attempt to escape its process group; only outer container closure is the
    authoritative containment boundary. No provider credential is present.
    """
    need(type(payload) is dict and set(payload) ==
         {"action_sha256", "action", "limits", "host_remaining_seconds"}, "compute_payload_fields")
    action = payload["action"]
    need(type(action) is dict and set(action) == {"compute"}, "compute_action_fields")
    spec = action["compute"]
    need(type(spec) is dict and set(spec) == {"language", "source"} and
         spec["language"] in ("python", "r") and type(spec["source"]) is str, "compute_language_source")
    need(payload["action_sha256"] == digest(action), "compute_action_identity")
    limits = payload["limits"]
    need(type(limits) is dict and set(limits) == {"seconds", "source_bytes", "stdout_bytes", "stderr_bytes"},
         "compute_limit_fields")
    need(finite_positive(limits["seconds"]) and finite_positive(payload["host_remaining_seconds"]) and
         positive_int(limits["source_bytes"], 131072) and
         positive_int(limits["stdout_bytes"], 131072) and positive_int(limits["stderr_bytes"], 65536),
         "finite_compute_limits")
    body = spec["source"].encode("utf-8")
    need(0 < len(body) <= limits["source_bytes"], "complete_compute_source_cap")
    started = time.monotonic()
    allowance = min(limits["seconds"], payload["host_remaining_seconds"])
    end = started + allowance
    # Cleanup is inside the selected call and original host remainder, never an
    # additional call allowance. The host still owns its unchanged hard deadline.
    cleanup_reserve = min(1.0, allowance / 4)
    work_end = end - cleanup_reserve
    process = None
    selector = None
    directory = None
    source_path = None
    source_fd = None
    created_source = False
    streams = {}
    eof = {"stdout": False, "stderr": False}
    retained = {"stdout": bytearray(), "stderr": bytearray()}
    observed = {"stdout": 0, "stderr": 0}
    errors = []
    returncode = None
    absent = None

    def error(phase, value):
        errors.append({"phase": phase, "class": type(value).__name__,
                       "code": str(value) if type(value) is ComputationFailure else "owned_operation_failed"})

    def attempt(phase, operation):
        try:
            return operation()
        except BaseException as value:
            error(phase, value)
            return None

    def working():
        compute_need(time.monotonic() < work_end, "original_compute_work_deadline")

    try:
        working()
        directory = Path(tempfile.mkdtemp(prefix="neural006-compute-", dir="/tmp"))
        source_path = directory / ("analysis.py" if spec["language"] == "python" else "analysis.R")
        source_fd = os.open(source_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        created_source = True
        offset = 0
        while offset < len(body):
            working()
            count = os.write(source_fd, body[offset:offset + 65536])
            compute_need(count > 0, "source_short_write")
            offset += count
        # Retire each close action before attempting it; no failed close retry.
        owned_fd, source_fd = source_fd, None
        os.close(owned_fd)
        working()
        if spec["language"] == "python":
            compute_need(bool(sys.executable) and Path(sys.executable).is_absolute(), "absolute_python_executable")
            argv = [sys.executable, "-I", "-B", str(source_path)]
        else:
            argv = ["/usr/bin/Rscript", "--vanilla", str(source_path)]
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, cwd=CANDIDATE_CWD, env=dict(CHILD_ENV),
            start_new_session=True, close_fds=True)
        selector = selectors.DefaultSelector()
        for stream, name in ((process.stdout, "stdout"), (process.stderr, "stderr")):
            streams[stream] = name
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        while selector.get_map():
            working()
            for key, _ in selector.select(min(.05, max(0.0, work_end - time.monotonic()))):
                stream = key.fileobj
                name = streams[stream]
                cap = limits[name + "_bytes"]
                # Read only the unused retained extent plus one overflow probe.
                size = min(65536, cap - len(retained[name]) + 1)
                compute_need(size > 0, name + "_read_reservation")
                try:
                    block = os.read(stream.fileno(), size)
                except BlockingIOError:
                    continue
                observed[name] += len(block)
                retained[name].extend(block[:max(0, cap - len(retained[name]))])
                compute_need(observed[name] <= cap, name + "_byte_cap")
                if not block:
                    selector.unregister(stream)
                    eof[name] = True
        working()
        returncode = process.wait(timeout=max(0.0, work_end - time.monotonic()))
        absent = process_group_absent(process)
        compute_need(absent is True, "residual_child_group")
    except BaseException as value:
        error("compute_body", value)
    finally:
        # Every cleanup is attempted even when an earlier cleanup failed.
        if source_fd is not None:
            owned_fd, source_fd = source_fd, None
            attempt("source_close", lambda: os.close(owned_fd))
        if process is not None:
            probe = attempt("group_probe", lambda: process_group_absent(process))
            if probe is not True:
                def kill():
                    try:
                        os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                attempt("group_kill", kill)
            attempt("child_reap", lambda: process.wait(timeout=max(0.0, end - time.monotonic())))
            returncode = attempt("child_final_poll", process.poll)
            absent = attempt("group_final_probe", lambda: process_group_absent(process))
            if absent is not True:
                error("group_closure", ComputationFailure("child_group_absence_unresolved"))
        if selector is not None:
            attempt("selector_close", selector.close)
        if process is not None:
            for name, stream in (("stdout", process.stdout), ("stderr", process.stderr)):
                if stream is not None:
                    attempt(name + "_close", stream.close)
        if created_source:
            attempt("source_remove", source_path.unlink)
        if directory is not None:
            attempt("source_directory_remove", directory.rmdir)
        if time.monotonic() >= end:
            error("final_horizon", ComputationFailure("original_compute_horizon_expired"))
    elapsed = time.monotonic() - started
    closed = process is not None and absent is True and all(eof.values()) and type(returncode) is int
    status = "infrastructure_failed"
    if not errors and closed:
        status = "complete" if returncode == 0 else "analysis_failed"
    stdout, stderr = bytes(retained["stdout"]), bytes(retained["stderr"])
    return {"schema": "neural006-candidate-computation-v1",
        "action_sha256": payload["action_sha256"], "language": spec["language"],
        "source_sha256": hashlib.sha256(body).hexdigest(), "status": status, "returncode": returncode,
        "stdout_base64": base64.b64encode(stdout).decode("ascii"),
        "stderr_base64": base64.b64encode(stderr).decode("ascii"),
        "stdout_observed_bytes": observed["stdout"], "stderr_observed_bytes": observed["stderr"],
        "stdout_retained_bytes": len(stdout), "stderr_retained_bytes": len(stderr),
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(), "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "stdout_eof": eof["stdout"], "stderr_eof": eof["stderr"],
        "group_absent": absent, "elapsed_seconds": elapsed, "errors": errors,
        "observation_trust": "candidate_reported_untrusted"}

def run_compute(action, limits, host_remaining_seconds):
    """Stable computation entry; caller supplies already selected, task-only operands."""
    return compute({"action_sha256": digest(action), "action": action, "limits": limits,
                    "host_remaining_seconds": host_remaining_seconds})

def main():
    opened = read()
    need(type(opened) is dict and set(opened) ==
         {"event", "session_id", "key_hex", "initial_sha256", "frame_bytes"} and
         opened["event"] == "neural006_broker_open_v1" and opened["frame_bytes"] == FRAME_CAP, "trusted_broker_open")
    key = bytes.fromhex(opened["key_hex"])
    need(len(key) == 32, "session_key")
    session = opened["session_id"]
    sequence = 0
    previous = digest(opened)
    kind, payload = "next_action", {}
    while True:
        sequence += 1
        request = {"schema": "neural006-model-duplex-v1", "session_id": session, "sequence": sequence,
                   "kind": kind, "payload": payload, "previous_sha256": previous}
        request["mac"] = hmac.new(key, canonical(request), hashlib.sha256).hexdigest()
        raw = canonical(request)
        need(len(raw) <= FRAME_CAP, "frame_cap")
        sys.stdout.buffer.write(raw)
        sys.stdout.buffer.flush()
        previous = digest(request)
        reply = read()
        sequence += 1
        need(type(reply) is dict and set(reply) ==
             {"schema", "session_id", "sequence", "kind", "payload", "previous_sha256", "mac"}, "reply_fields")
        unsigned = {name: value for name, value in reply.items() if name != "mac"}
        need(reply["schema"] == "neural006-model-duplex-v1" and reply["session_id"] == session and
             reply["sequence"] == sequence and reply["previous_sha256"] == previous and
             type(reply["mac"]) is str and hmac.compare_digest(reply["mac"],
                 hmac.new(key, canonical(unsigned), hashlib.sha256).hexdigest()), "reply_identity")
        previous = digest(reply)
        if kind == "next_action":
            if reply["kind"] == "compute":
                payload = compute(reply["payload"])
                kind = "compute_result"
            else:
                need(reply["kind"] == "model_action" and type(reply["payload"]) is dict and
                     set(reply["payload"]) == {"action_sha256"}, "one_model_action")
                kind, payload = "apply_action", {"action_sha256": reply["payload"]["action_sha256"]}
        elif kind == "compute_result":
            need(reply["kind"] == "compute_feedback" and type(reply["payload"]) is dict and
                 set(reply["payload"]) == {"reply_sha256", "finished"} and
                 reply["payload"]["finished"] is False, "one_compute_feedback")
            kind, payload = "next_action", {}
        else:
            need(reply["kind"] in ("tool_result", "terminal") and type(reply["payload"]) is dict and
                 set(reply["payload"]) == {"reply_sha256", "finished"} and
                 reply["payload"]["finished"] is (reply["kind"] == "terminal"), "one_authorized_reply")
            if reply["kind"] == "terminal":
                return 0
            kind, payload = "next_action", {}

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        sys.stderr.write(type(error).__name__ + ": relay_failed\n")
        raise SystemExit(1)
