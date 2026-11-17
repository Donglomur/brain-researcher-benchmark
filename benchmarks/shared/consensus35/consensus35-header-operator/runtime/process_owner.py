"""Bounded capture and closure for one newly owned trusted child process group.

This module makes no process, runtime or source-data observation on import.
The caller selects exact executable/source operands and supplies the original
cleanup horizon plus a separately bound process-group closer and hard-wall fuse.
"""
from __future__ import annotations

import hashlib
import math
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time


class ProcessOwnerError(ValueError):
    pass


def _need(condition, reason):
    if not condition:
        raise ProcessOwnerError(reason)


def _finite_time(value):
    return type(value) in (int, float) and math.isfinite(value)


def _selected_path(value, *, directory=False):
    _need(isinstance(value, (str, os.PathLike)), "selected path type")
    path = Path(value)
    _need(path.is_absolute() and ".." not in path.parts, "absolute selected path without traversal")
    for ancestor in reversed(path.parents):
        info = ancestor.lstat()
        _need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode),
              "ordinary selected directory ancestry")
    if directory:
        info = path.lstat()
        _need(stat.S_ISDIR(info.st_mode) and not stat.S_ISLNK(info.st_mode), "ordinary working directory")
    else:
        try:
            path.lstat()
        except FileNotFoundError:
            pass
        else:
            raise ProcessOwnerError("capture output already exists")
    return path


def run_owned(argv, cwd, env, until, stdout_path, stderr_path, closer, *,
              work_until=None, stream_cap=65536, signals=None,
              on_spawn=None, on_closed=None, start_gate=None):
    """Run one selected child; return evidence, never turn forced closure into success.

    Argument errors raise before capture creation. Operational errors are retained
    in the returned receipt. Each stream retains at most ``stream_cap + 1`` bytes;
    the extra byte is an overflow witness, and its hash is a prefix hash only.
    The supplied closer is called once in finally for every safely owned child.
    ``on_closed(child)`` requires explicit reaping and group-absence evidence.
    A gated controller must block on stdin before opening inputs or spawning work;
    gate bytes are delivered only after ``on_spawn`` registers its new group.
    """
    return _run(argv, cwd, env, until, stdout_path, stderr_path, closer,
                work_until=work_until, stream_cap=stream_cap, signals=signals,
                on_spawn=on_spawn, on_closed=on_closed, start_gate=start_gate, group_mode=True)


def run_in_controller(argv, cwd, env, until, stdout_path, stderr_path, *,
                      work_until=None, stream_cap=65536, signals=None):
    """Run one trusted stage inside the outer owner's already registered group.

    Only a controller that is its own group leader may call this function. The
    direct child inherits that group; its direct cleanup receipt makes no claim
    about group absence. The outer owner remains responsible for group closure.
    """
    _need(os.getpid() > 1 and os.getpid() == os.getpgrp(), "caller must be the owned controller group leader")
    receipt = _run(argv, cwd, env, until, stdout_path, stderr_path, None,
                   work_until=work_until, stream_cap=stream_cap, signals=signals,
                   on_spawn=None, on_closed=None, start_gate=None, group_mode=False)
    receipt.update(controller_pid=os.getpid(), controller_group_id=os.getpgrp())
    return receipt


def _close_direct(child, until):
    """Terminate/reap only this Popen child; never signal or inspect its group."""
    started = time.monotonic()
    horizons = (min(until, started + 2), min(until, started + 4))
    events, errors, sent = [], [], []

    def observe(label, operation):
        try:
            value = operation()
            events.append({"operation": label, "status": "observed", "value": value})
            return value
        except ProcessLookupError:
            events.append({"operation": label, "status": "already_absent"})
        except BaseException as exc:
            errors.append({"operation": label, "type": type(exc).__name__, "reason": str(exc)[:256]})
        return None

    code = observe("initial_direct_child_poll", child.poll)
    for sig, operation, horizon in ((signal.SIGTERM, child.terminate, horizons[0]),
                                     (signal.SIGKILL, child.kill, horizons[1])):
        if code is None and time.monotonic() < until:
            def deliver(operation=operation, sig=sig):
                operation()
                sent.append(sig.name)
            observe("send_direct_" + sig.name, deliver)
        if code is None:
            code = observe("reap_after_" + sig.name,
                           lambda horizon=horizon: child.wait(timeout=max(0, horizon - time.monotonic())))
        if code is not None:
            break
    final_code = observe("final_direct_child_poll", child.poll)
    if final_code is None:
        final_code = observe("final_nonblocking_reap", lambda: child.wait(timeout=0))
    return {"scope": "DIRECT_CHILD_IN_OUTER_OWNED_GROUP", "child_id": child.pid,
            "exit_code": final_code, "reaped": final_code is not None,
            "events": events, "errors": errors, "signals_sent": sent,
            "original_cleanup_deadline": until, "stage_deadlines": list(horizons)}


def _run(argv, cwd, env, until, stdout_path, stderr_path, closer, *,
         work_until, stream_cap, signals, on_spawn, on_closed, start_gate, group_mode):
    """Shared capture engine with explicit outer-group versus direct-stage closure."""
    started = time.monotonic()
    _need(type(argv) in (list, tuple) and argv and
          all(type(value) is str and "\x00" not in value for value in argv), "explicit nonempty argv")
    _need(Path(argv[0]).is_absolute(), "absolute selected executable")
    _need(type(env) is dict and all(type(key) is str and key and "=" not in key and "\x00" not in key and
                                  type(value) is str and "\x00" not in value for key, value in env.items()),
          "explicit string environment")
    _need(_finite_time(until), "finite original cleanup horizon")
    _need(work_until is None or _finite_time(work_until), "finite work horizon")
    _need(type(stream_cap) is int and 0 < stream_cap <= 65536, "stream cap must be 1..65536 bytes")
    _need(signals is None or type(signals) is list, "signal recorder must be a list")
    _need(not group_mode or callable(getattr(closer, "close_owned_group", None)), "selected process-group closer")
    _need(on_spawn is None or callable(on_spawn), "spawn callback")
    _need(on_closed is None or callable(on_closed), "closed callback")
    _need(start_gate is None or type(start_gate) is bytes and 1 <= len(start_gate) <= 4096,
          "start gate must contain 1..4096 bytes")
    _need(start_gate is None or group_mode and on_spawn is not None,
          "gated launch requires a registration callback")
    signal_record = [] if signals is None else signals
    work_deadline = until - 4.0 if work_until is None else min(until - 4.0, work_until)
    _need(started < work_deadline, "original horizon must reserve at least four cleanup seconds")
    cwd = _selected_path(cwd, directory=True)
    paths = {"stdout": _selected_path(stdout_path), "stderr": _selected_path(stderr_path)}
    _need(paths["stdout"] != paths["stderr"], "distinct fresh capture files")
    _need(all(path.parent == cwd for path in paths.values()), "captures must be directly inside owned working directory")

    errors = []
    child = None
    safely_owned = False
    closure = None
    closure_valid = False
    selector = None
    capture_fds = {}
    streams = {name: {"path": str(path), "bytes": 0, "received_bytes_at_least": 0,
                      "eof": False, "overflow": False, "limit_bytes": stream_cap,
                      "retention_limit_bytes": stream_cap + 1}
               for name, path in paths.items()}
    hashes = {name: hashlib.sha256() for name in paths}
    natural_exit_observed = False
    spawn_callback_completed = on_spawn is None
    closed_callback_completed = False
    gate_delivered = None if start_gate is None else False
    gate_bytes_sent = 0

    def error(stage, exc):
        errors.append({"stage": stage, "type": type(exc).__name__, "message": str(exc)[:1024]})

    def interrupted():
        if signal_record:
            raise ProcessOwnerError("signal received during owned operation")

    def capture(name, body):
        view = memoryview(body)
        while view:
            interrupted()
            _need(time.monotonic() < work_deadline, "work deadline during capture")
            amount = os.write(capture_fds[name], view)
            _need(amount > 0, "capture write made no progress")
            hashes[name].update(view[:amount])
            streams[name]["bytes"] += amount
            view = view[amount:]

    try:
        for name, path in paths.items():
            capture_fds[name] = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        interrupted()
        _need(time.monotonic() < work_deadline, "work horizon expired before spawn")
        child = subprocess.Popen(list(argv), cwd=str(cwd), env=dict(env), shell=False,
                                 stdin=subprocess.DEVNULL if start_gate is None else subprocess.PIPE,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=group_mode)
        safely_owned = (type(child.pid) is int and child.pid > 1 and child.pid != os.getpid() and
                        (not group_mode or child.pid != os.getpgrp()))
        _need(safely_owned, "unsafe newly spawned child identity")
        if on_spawn is not None:
            on_spawn(child)
            spawn_callback_completed = True
        if start_gate is not None:
            interrupted()
            _need(time.monotonic() < work_deadline, "work horizon expired before gate delivery")
            # This is a fresh empty pipe and at most 4096 bytes. Nonblocking mode
            # also makes unexpected pipe backpressure a bounded failed launch.
            os.set_blocking(child.stdin.fileno(), False)
            while gate_bytes_sent < len(start_gate):
                interrupted()
                _need(time.monotonic() < work_deadline, "work horizon expired during gate delivery")
                amount = os.write(child.stdin.fileno(), start_gate[gate_bytes_sent:])
                _need(amount > 0, "gate write made no progress")
                gate_bytes_sent += amount
            child.stdin.close()
            gate_delivered = True
            _need(time.monotonic() < work_deadline, "work horizon expired after gate delivery")
        selector = selectors.DefaultSelector()
        for name, pipe in (("stdout", child.stdout), ("stderr", child.stderr)):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, name)
        while selector.get_map() or child.poll() is None:
            interrupted()
            _need(time.monotonic() < work_deadline, "owned child work deadline exceeded")
            if not selector.get_map():
                # Closing both pipes does not establish process exit.
                time.sleep(min(.01, max(0., work_deadline - time.monotonic())))
                continue
            events = selector.select(min(.05, max(0., work_deadline - time.monotonic())))
            for selected, _ in events:
                name = selected.data
                stream = streams[name]
                remaining = stream_cap + 1 - stream["received_bytes_at_least"]
                _need(remaining > 0, "stream overflow witness already observed")
                try:
                    body = os.read(selected.fileobj.fileno(), min(8192, remaining))
                except BlockingIOError:
                    continue
                if not body:
                    stream["eof"] = True
                    selector.unregister(selected.fileobj)
                    continue
                stream["received_bytes_at_least"] += len(body)
                stream["overflow"] = stream["received_bytes_at_least"] > stream_cap
                capture(name, body)
                if stream["overflow"]:
                    raise ProcessOwnerError(name + " exceeded complete stream cap")
        natural_exit_observed = child.poll() == 0
        _need(time.monotonic() < work_deadline, "work horizon expired before exit and EOF admission")
        _need(natural_exit_observed, "owned child exited nonzero")
    except BaseException as exc:
        error("operation", exc)
    finally:
        if child is not None:
            if safely_owned:
                try:
                    closure = closer.close_owned_group(child, until) if group_mode else _close_direct(child, until)
                    _need(type(closure) is dict, "invalid closure receipt")
                    required = {"exit_code", "reaped", "errors", "signals_sent", "original_cleanup_deadline"}
                    required |= {"process_group_absent", "group_id"} if group_mode else {"scope", "child_id"}
                    _need(required <= set(closure), "incomplete closure receipt")
                    _need(type(closure["errors"]) is list and type(closure["signals_sent"]) is list,
                          "invalid closure error/signal fields")
                    _need(type(closure["reaped"]) is bool, "invalid closure reap field")
                    _need(closure["exit_code"] is None or type(closure["exit_code"]) is int,
                          "invalid closure exit code")
                    _need(closure["reaped"] == (closure["exit_code"] is not None),
                          "inconsistent closure reap observation")
                    if group_mode:
                        _need(type(closure["process_group_absent"]) is bool, "invalid group absence field")
                        _need(type(closure["group_id"]) is int and closure["group_id"] == child.pid,
                              "closure names a different process group")
                    else:
                        _need(closure["scope"] == "DIRECT_CHILD_IN_OUTER_OWNED_GROUP" and
                              type(closure["child_id"]) is int and closure["child_id"] == child.pid and
                              "process_group_absent" not in closure, "invalid direct-child closure scope")
                    _need(closure["original_cleanup_deadline"] == until,
                          "closer changed original cleanup horizon")
                    closure_valid = True
                    if closure["errors"]:
                        error("closure_report", ProcessOwnerError("selected closer retained errors"))
                    if closure["reaped"] is True and (not group_mode or closure["process_group_absent"] is True):
                        if on_closed is not None:
                            try:
                                on_closed(child)
                                closed_callback_completed = True
                            except BaseException as exc:
                                error("on_closed", exc)
                        else:
                            closed_callback_completed = True
                except BaseException as exc:
                    error("closer", exc)
            else:
                error("closer", ProcessOwnerError("unsafe identity; group closure unresolved"))
        if selector is not None:
            try:
                selector.close()
            except BaseException as exc:
                error("selector_close", exc)
        if child is not None:
            for name in ("stdin", "stdout", "stderr"):
                pipe = getattr(child, name, None)
                if pipe is not None:
                    try:
                        pipe.close()
                    except BaseException as exc:
                        error(name + "_pipe_close", exc)
        for name, fd in capture_fds.items():
            try:
                os.fsync(fd)
                os.fchmod(fd, 0o400)
            except BaseException as exc:
                error(name + "_capture_finish", exc)
            finally:
                try:
                    os.close(fd)
                except BaseException as exc:
                    error(name + "_capture_close", exc)

    finished = time.monotonic()
    if finished >= until:
        error("cleanup_deadline", ProcessOwnerError("original cleanup horizon expired before receipt admission"))
    closed = (closure_valid and closure.get("reaped") is True and
              (not group_mode or closure.get("process_group_absent") is True and closure["group_id"] == child.pid))
    for name, stream in streams.items():
        stream["sha256"] = hashes[name].hexdigest()
        stream["created"] = name in capture_fds
        stream["complete"] = (stream["created"] and stream["eof"] and not stream["overflow"] and
                              stream["bytes"] == stream["received_bytes_at_least"])
        stream["hash_scope"] = "complete_stream" if stream["complete"] else "retained_prefix_only"
    complete = (child is not None and safely_owned and natural_exit_observed and
                spawn_callback_completed and closed_callback_completed and closed and
                (start_gate is None or gate_delivered is True) and
                not errors and not signal_record and closure.get("exit_code") == 0 and
                closure.get("errors") == [] and closure.get("signals_sent") == [] and
                all(stream["complete"] for stream in streams.values()))
    receipt = {"schema": "owned-trusted-child-functional-receipt-v1", "complete": bool(complete),
            "argv": list(argv), "cwd": str(cwd), "pid": None if child is None else child.pid,
            "new_session": child is not None and group_mode,
            "closure_scope": "OUTER_OWNED_PROCESS_GROUP" if group_mode else "DIRECT_CHILD_IN_OUTER_OWNED_GROUP",
            "work_deadline_monotonic": work_deadline, "original_cleanup_deadline_monotonic": until,
            "elapsed_seconds": finished - started, "streams": streams,
            "closure": closure, "errors": errors,
            "signals_received": list(signal_record[:64]), "natural_exit_observed": natural_exit_observed,
            "spawn_callback_completed": spawn_callback_completed,
            "closed_callback_completed": closed_callback_completed,
            "gate_required": start_gate is not None, "gate_delivered": gate_delivered,
            "gate_bytes_sent": gate_bytes_sent}
    if group_mode:
        receipt.update(contained=closed, safely_owned_group=safely_owned)
    else:
        receipt.update(direct_child_closed=closed, safely_owned_direct_child=safely_owned)
    return receipt
