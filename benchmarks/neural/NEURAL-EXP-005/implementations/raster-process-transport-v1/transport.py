"""Fresh local participant processes for the accepted Helsinki raster interface.

The wire contains only existing typed Session responses. This is NOT a filesystem,
network or remote-provider sandbox. The caller must independently admit those
boundaries before using authentic data or attributing results to native perception.
"""

import base64
import hashlib
import json
import math
import os
from pathlib import Path
import select
import signal
import struct
import subprocess
import tempfile
import time
import types
import uuid


COLLECTOR_SHA256 = "1a3a89bfb968dec66c13f5a06cea6e16f58428025b9ec753da16c0cfaf61a472"
ENVIRONMENT = {"LANG": "C", "LC_ALL": "C", "PYTHONDONTWRITEBYTECODE": "1",
               "OMP_NUM_THREADS": "1", "OPENBLAS_NUM_THREADS": "1",
               "MKL_NUM_THREADS": "1", "VECLIB_MAXIMUM_THREADS": "1",
               "NUMEXPR_NUM_THREADS": "1"}
DESCRIPTION_FIELDS = frozenset(("schema", "binding", "sample_count", "montage",
    "sample_clock", "units", "duration_seconds", "prediction_interval_seconds",
    "quality_flags", "maximum_page_samples", "maximum_page_channels",
    "representation", "quality_flag_interpretation"))
FRAME_FIELDS = frozenset(("schema", "binding", "mime_type", "png_base64", "png_sha256",
    "width", "height", "selection", "clipped_sample_counts", "source_samples_visited_per_channel"))
ANSWER_FIELDS = frozenset(("schema", "accepted", "case_id", "input_sha256"))
LIMIT_FIELDS = frozenset(("wall_seconds", "max_actions", "max_action_bytes",
    "max_stdout_bytes", "max_response_bytes", "max_wire_bytes"))
CLEANUP_RESERVE_SECONDS = 0.5


class TransportError(ValueError):
    def __init__(self, code, evidence=None):
        super().__init__(code)
        self.code = code
        self.evidence = evidence


def require(condition, code):
    if not condition:
        raise TransportError(code)


def _load_collector():
    path = Path(__file__).resolve().parent.parent / "raster-collection-v1" / "collector.py"
    body = path.read_bytes()
    require(hashlib.sha256(body).hexdigest() == COLLECTOR_SHA256, "collector_source_changed")
    module = types.ModuleType("_helsinki_process_bound_collector")
    module.__file__ = str(path)
    exec(compile(body, str(path), "exec"), module.__dict__)
    return module


collector = _load_collector()


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                      allow_nan=False).encode("ascii")


def _digest(value):
    return hashlib.sha256(_json(value)).hexdigest()


def _limits(value):
    require(type(value) is dict and set(value) == LIMIT_FIELDS, "exact_limits_required")
    result = dict(value)
    wall = result["wall_seconds"]
    require(type(wall) in (int, float) and math.isfinite(wall) and 1 <= wall <= 60,
            "wall_limit_outside_1_to_60_seconds")
    caps = {"max_actions": 4096, "max_action_bytes": 16384,
            "max_stdout_bytes": 16777216, "max_response_bytes": 8388608,
            "max_wire_bytes": 268435456}
    for name, cap in caps.items():
        require(type(result[name]) is int and 1 <= result[name] <= cap, "invalid_" + name)
    require(result["max_stdout_bytes"] >= result["max_action_bytes"] and
            result["max_wire_bytes"] >= result["max_response_bytes"], "inconsistent_byte_limits")
    return result


def _decode_action(body):
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate_json_key")
            result[key] = value
        return result
    def constant(_value):
        raise TransportError("nonfinite_json_number")
    try:
        value = json.loads(body.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as exc:
        if isinstance(exc, TransportError):
            raise
        raise TransportError("malformed_json_action") from None
    require(type(value) is dict, "object_action_required")
    return value


def _response(value, binding):
    """Fail closed on schema expansion; do not serialize an arbitrary host object."""
    require(type(value) is dict, "nonobject_host_response")
    schema = value.get("schema")
    if schema == "helsinki-raster-description-v1":
        require(set(value) == DESCRIPTION_FIELDS and value["binding"] == binding and
                set(value["binding"]) == collector.BINDING_FIELDS, "description_schema_changed")
        require(set(value["sample_clock"]) == {"first_tick", "step_ticks", "ticks_per_second"},
                "clock_schema_changed")
    elif schema == "helsinki-raster-frame-v1":
        require(set(value) == FRAME_FIELDS and value["binding"] == binding and
                set(value["binding"]) == collector.BINDING_FIELDS, "frame_schema_changed")
        require(set(value["selection"]) == {"start_sample", "stop_sample", "channels",
                "units_per_division"} and value["mime_type"] == "image/png", "frame_selection_changed")
        try:
            png = base64.b64decode(value["png_base64"], validate=True)
        except (ValueError, TypeError):
            raise TransportError("invalid_png_encoding") from None
        require(png.startswith(b"\x89PNG\r\n\x1a\n") and
                hashlib.sha256(png).hexdigest() == value["png_sha256"], "invalid_png_commitment")
    elif schema == "helsinki-raster-answer-receipt-v1":
        require(set(value) == ANSWER_FIELDS and value["accepted"] is True and
                value["case_id"] == binding["case_id"] and
                value["input_sha256"] == binding["input_sha256"], "answer_receipt_changed")
    else:
        raise TransportError("unknown_host_response_schema")
    return _json(value) + b"\n"


def _remaining(deadline):
    remaining = deadline - time.monotonic()
    require(remaining > 0, "participant_deadline")
    return remaining


def _wait(fd, *, write, deadline):
    while True:
        try:
            ready = select.select([] if write else [fd], [fd] if write else [], [],
                                  _remaining(deadline))
        except InterruptedError:
            continue
        require(bool(ready[1] if write else ready[0]), "participant_deadline")
        return


class _Wire:
    def __init__(self, proc, deadline, limits):
        self.proc, self.deadline, self.limits = proc, deadline, limits
        self.stdout_bytes = self.wire_bytes = self.actions = self.png_frames = 0
        self.transcript = hashlib.sha256()
        self.events = []

    def _record(self, direction, body):
        self.transcript.update(direction + struct.pack(">Q", len(body)) + body)

    def send(self, response, binding):
        body = _response(response, binding)
        require(len(body) <= self.limits["max_response_bytes"], "response_byte_limit")
        require(self.wire_bytes + len(body) <= self.limits["max_wire_bytes"], "wire_byte_limit")
        offset = 0
        while offset < len(body):
            _wait(self.proc.stdin.fileno(), write=True, deadline=self.deadline)
            try:
                count = os.write(self.proc.stdin.fileno(), memoryview(body)[offset:])
            except BlockingIOError:
                continue
            except BrokenPipeError:
                raise TransportError("participant_closed_input") from None
            offset += count
        self.wire_bytes += len(body)
        self._record(b"H", body)
        event = {"direction": "host_to_participant", "schema": response["schema"],
                 "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
        if response["schema"] == "helsinki-raster-frame-v1":
            event["png_sha256"] = response["png_sha256"]
            self.png_frames += 1
        self.events.append(event)

    def _read(self):
        _wait(self.proc.stdout.fileno(), write=False, deadline=self.deadline)
        try:
            body = os.read(self.proc.stdout.fileno(), 4096)
        except BlockingIOError:
            return self._read()
        self.stdout_bytes += len(body)
        require(self.stdout_bytes <= self.limits["max_stdout_bytes"], "stdout_byte_limit")
        return body

    def action(self):
        require(self.actions < self.limits["max_actions"], "action_limit")
        body = bytearray()
        while True:
            chunk = self._read()
            require(bool(chunk), "participant_eof_before_answer")
            body.extend(chunk)
            require(len(body) <= self.limits["max_action_bytes"], "action_byte_limit")
            if b"\n" in body:
                line, tail = bytes(body).split(b"\n", 1)
                require(not tail, "multiple_or_extra_frames")
                action = _decode_action(line)
                self.actions += 1
                self._record(b"P", bytes(body))
                self.events.append({"direction": "participant_to_host", "bytes": len(body),
                                    "sha256": hashlib.sha256(body).hexdigest()})
                return action

    def finish(self):
        self.proc.stdin.close()
        # Any byte after the first final answer, including whitespace, fails.
        require(self._read() == b"", "output_after_final_answer")
        try:
            code = self.proc.wait(timeout=_remaining(self.deadline))
        except subprocess.TimeoutExpired:
            raise TransportError("participant_deadline") from None
        require(code == 0, "participant_nonzero_exit")


def _group_state(pgid):
    try:
        os.killpg(pgid, 0)
        return "present"
    except ProcessLookupError:
        return "absent"
    except OSError:
        # Some exit races yield EPERM rather than ESRCH. Unknown is never absence.
        return "unknown"


def _cleanup(proc, deadline):
    """Only the process group created by this Popen(start_new_session=True)."""
    result = {"termination_requested": False, "leader_reaped": False,
              "owned_group_absent": False, "exit_code": None, "group_probe_unavailable": False,
              "leader_termination_requested": False, "leader_termination_error": None}
    if proc is None:
        return result
    # Reap an already exited leader before probing its group; an exiting zombie
    # can otherwise provoke EPERM on macOS. Still handle unavailable observations.
    proc.poll()
    state = _group_state(proc.pid)
    result["group_probe_unavailable"] = state == "unknown"
    if state == "present":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            result["termination_requested"] = True
        except ProcessLookupError:
            pass
        except OSError:
            result["group_probe_unavailable"] = True
    # A failed group observation must not leave our still-live Popen child alive.
    # This signals only that owned leader. Descendants/group remain separately
    # unknown until a later observation actually establishes group absence.
    if result["group_probe_unavailable"] and proc.poll() is None:
        try:
            proc.kill()
            result["leader_termination_requested"] = True
        except ProcessLookupError:
            pass
        except OSError as exc:
            result["leader_termination_error"] = type(exc).__name__
    try:
        proc.wait(timeout=max(0, deadline - time.monotonic()))
        result["leader_reaped"] = True
    except subprocess.TimeoutExpired:
        pass
    state = _group_state(proc.pid)
    while state != "absent" and time.monotonic() < deadline:
        result["group_probe_unavailable"] |= state == "unknown"
        time.sleep(min(0.005, max(0, deadline - time.monotonic())))
        state = _group_state(proc.pid)
    result["owned_group_absent"] = state == "absent"
    result["exit_code"] = proc.returncode
    for stream in (proc.stdin, proc.stdout):
        if stream is not None and not stream.closed:
            stream.close()
    return result


def run_case(owner, packet, *, argv, limits, scratch_root):
    """Execute one next frozen case; commit only after a clean bounded lifecycle.

    All arguments and returned evidence are operator-only. No environment, shell,
    extra FD, pickle, roster, raw packet or collector is sent to the participant.
    A transport failure leaves the current collector case uncommitted and blocks
    complete export; this function does not silently retry, skip or relabel it.
    """
    limits = _limits(limits)
    require(type(argv) in (tuple, list) and len(argv) > 0 and
            all(type(x) is str and x and "\x00" not in x for x in argv) and
            Path(argv[0]).is_absolute(), "absolute_frozen_argv_required")
    argv = tuple(argv)
    root = Path(scratch_root).resolve(strict=True)
    require(root.is_dir(), "scratch_root_required")
    session = owner.open_case(packet)
    description = session.act({"action": "describe"})
    binding = description["binding"]
    _response(description, binding)
    started = time.monotonic()
    deadline = started + limits["wall_seconds"]
    proc = wire = None
    failure = None
    evidence = {"schema": "helsinki-raster-process-receipt-v1", "task_id": "NEURAL-EXP-005",
        "launch_id": uuid.uuid4().hex, "binding": binding, "argv_sha256": _digest(argv),
        "environment_sha256": _digest(ENVIRONMENT), "limits": limits,
        "fresh_exec": False, "empty_cwd_at_launch": False, "pid": None,
        "parent_pid": os.getpid(), "process_group_id": None, "session_id": None,
        "collector_committed": False, "scratch_removed": False}
    try:
        with tempfile.TemporaryDirectory(prefix="helsinki-case-", dir=str(root)) as case_dir:
            evidence["empty_cwd_at_launch"] = not any(Path(case_dir).iterdir())
            os.chmod(case_dir, 0o700)
            proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, cwd=case_dir, env=dict(ENVIRONMENT),
                shell=False, close_fds=True, pass_fds=(), start_new_session=True, bufsize=0)
            evidence.update(fresh_exec=True, pid=proc.pid,
                process_group_id=os.getpgid(proc.pid), session_id=os.getsid(proc.pid))
            require(evidence["process_group_id"] == proc.pid and evidence["session_id"] == proc.pid,
                    "fresh_owned_session_not_observed")
            for stream in (proc.stdin, proc.stdout):
                os.set_blocking(stream.fileno(), False)
            wire = _Wire(proc, deadline - CLEANUP_RESERVE_SECONDS, limits)
            try:
                wire.send(description, binding)
                while True:
                    action = wire.action()
                    try:
                        response = session.act(action)
                    except (collector.viewer.ViewError, TypeError, OverflowError):
                        raise TransportError("invalid_typed_action") from None
                    wire.send(response, binding)
                    if response["schema"] == "helsinki-raster-answer-receipt-v1":
                        break
                wire.finish()
                require(_group_state(proc.pid) == "absent", "residual_participant_process_group")
            finally:
                evidence["cleanup"] = _cleanup(proc, deadline)
        evidence["scratch_removed"] = not Path(case_dir).exists()
    except (TransportError, OSError, ValueError) as exc:
        failure = exc.code if isinstance(exc, TransportError) else "participant_or_scratch_lifecycle_error"
        if "cleanup" not in evidence:
            evidence["cleanup"] = _cleanup(proc, deadline)
        if "case_dir" in locals():
            evidence["scratch_removed"] = not Path(case_dir).exists()
    evidence["wall_seconds"] = time.monotonic() - started
    if wire is not None:
        evidence.update(actions=wire.actions, png_frames=wire.png_frames,
            participant_stdout_bytes=wire.stdout_bytes, host_wire_bytes=wire.wire_bytes,
            wire_sha256=wire.transcript.hexdigest(), wire_events=wire.events)
    if failure is None and not (evidence["cleanup"]["leader_reaped"] and
            evidence["cleanup"]["owned_group_absent"] and evidence["scratch_removed"]):
        failure = "cleanup_not_qualified"
    if failure is None:
        evidence["commit_receipt"] = owner.commit_current()
        evidence["collector_committed"] = True
        evidence["status"] = "committed"
        return evidence
    evidence.update(status="failed", failure=failure)
    raise TransportError(failure, evidence)
