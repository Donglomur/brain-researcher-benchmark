"""Cleanup never replaces the primary failure or skips terminal custody."""
import os
import signal
from .protocol import write_new


def cleanup(processes, streams=(), selector=None, stop_container=None, killpg=None):
    killpg = os.killpg if killpg is None else killpg
    steps, errors, residual = [], [], []
    def attempt(operation, action):
        try:
            value = action()
            steps.append({"operation": operation, "result": value})
            return value, True
        except BaseException as error:
            entry = {"operation": operation, "type": type(error).__name__, "message": str(error)}
            errors.append(entry)
            steps.append(entry)
            return None, False
    if stop_container is not None:
        attempt("stop-owned-container", stop_container)
    for process in processes:
        pid = getattr(process, "pid", None)
        status, polled = attempt("poll-owned-process", process.poll)
        if not polled or status is None:
            _, killed = attempt("kill-owned-process-group", lambda p=pid: killpg(p, signal.SIGKILL))
        else:
            killed = True
        code, waited = attempt("wait-owned-process", lambda p=process: p.wait(timeout=10))
        if not waited or not killed:
            residual.append({"pid": pid, "termination": "unknown", "observed_exit_code": code})
    if selector is not None:
        attempt("close-selector", selector.close)
    for index, stream in enumerate(streams):
        if stream is not None:
            attempt(f"close-stream-{index}", stream.close)
    return {"steps": steps, "errors": errors, "residual_processes": residual,
            "termination": "unknown" if residual else "observed-exited",
            "custody_complete": not errors}


def terminal(path, record, meter):
    """Best effort write, explicitly return any failure to retain END itself."""
    try:
        return {"written": True, "pin": write_new(path, record, meter), "error": None}
    except BaseException as error:
        # A failing filesystem cannot be guaranteed to retain a receipt. Return
        # the structured original record to the caller; never turn this into OK.
        return {"written": False, "pin": None,
                "error": {"type": type(error).__name__, "message": str(error)},
                "unwritten_terminal_record": record}
