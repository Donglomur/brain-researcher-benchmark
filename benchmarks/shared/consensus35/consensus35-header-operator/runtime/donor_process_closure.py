"""Reused complete process-group close primitive; separately reviewed source."""
import os
import signal
import time

def close_owned(child, deadline, clock=time.monotonic, send=os.killpg):
    """Cleanup known-owned process; every later observation survives earlier errors."""
    events, errors, sent = [], [], []
    def attempt(label, fn):
        try:
            value = fn()
            events.append({"operation": label, "status": "observed", "value": value})
            return True, value
        except ProcessLookupError:
            events.append({"operation": label, "status": "already_absent"})
            return False, None
        except BaseException as exc:
            errors.append({"operation": label, "type": type(exc).__name__, "message": str(exc)[:512]})
            return False, None

    for sig, allowance in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        polled, code = attempt("poll_before_" + sig.name, child.poll)
        if not polled or code is None:
            delivered, _ = attempt("send_" + sig.name, lambda sig=sig: send(child.pid, sig))
            if delivered:
                sent.append(sig.name)
            attempt("wait_after_" + sig.name,
                    lambda allowance=allowance: child.wait(timeout=max(0, min(allowance, deadline - clock()))))
    _, code = attempt("final_poll", child.poll)
    # Reaping and group absence are separate observations even after failed kill/wait.
    if code is None:
        _, code = attempt("final_nonblocking_reap", lambda: child.wait(timeout=0))
    absent = False
    try:
        send(child.pid, 0)
        events.append({"operation": "final_group_probe", "status": "present"})
    except ProcessLookupError:
        absent = True
        events.append({"operation": "final_group_probe", "status": "absent"})
    except BaseException as exc:
        errors.append({"operation": "final_group_probe", "type": type(exc).__name__, "message": str(exc)[:512]})
    return {"exit_code": code, "reaped": code is not None, "process_group_absent": absent,
            "events": events, "errors": errors, "signals_sent": sent}


def close_owned_group(child, deadline, clock=time.monotonic, send=os.killpg, pause=time.sleep):
    """Close one known new-session group even after its direct parent exited.

    Both stage deadlines are fixed at entry and bounded by the caller's original
    absolute deadline. Reap, signal and final group observations are independent.
    An inability to observe a group is never an observation of its absence.
    """
    started = clock()
    stage_deadlines = (min(deadline, started+2), min(deadline, started+4))
    events, errors, sent = [], [], []
    def observe(label, fn):
        try:
            value = fn(); events.append({"operation": label, "status": "observed", "value": value})
            return True, value
        except ProcessLookupError:
            events.append({"operation": label, "status": "already_absent"})
            return False, None
        except BaseException as exc:
            errors.append({"operation": label, "type": type(exc).__name__, "reason": str(exc)[:256]})
            return None, None
    def probe(label):
        outcome, _ = observe(label, lambda: send(child.pid, 0))
        return outcome is False
    _, code = observe("initial_direct_child_poll", child.poll)
    absent = probe("initial_group_probe")
    for sig, horizon in zip((signal.SIGTERM, signal.SIGKILL), stage_deadlines):
        if not absent and clock() < deadline:
            delivered, _ = observe("send_"+sig.name, lambda sig=sig: send(child.pid, sig))
            if delivered is True:
                sent.append(sig.name)
        # A failed signal or probe never skips the independent direct reap.
        _, code = observe("reap_after_"+sig.name,
            lambda horizon=horizon: child.wait(timeout=max(0, horizon-clock())))
        absent = probe("group_probe_after_"+sig.name)
        while not absent and clock() < horizon:
            pause(min(0.05, max(0, horizon-clock())))
            absent = probe("group_wait_after_"+sig.name)
        if absent and code is not None:
            break
    _, final_code = observe("final_direct_child_poll", child.poll)
    if final_code is None:
        _, final_code = observe("final_nonblocking_reap", lambda: child.wait(timeout=0))
    absent = probe("final_independent_group_probe")
    return {"exit_code": final_code, "reaped": final_code is not None,
            "group_id": child.pid, "process_group_absent": absent, "events": events,
            "errors": errors, "signals_sent": sent, "original_cleanup_deadline": deadline,
            "stage_deadlines": list(stage_deadlines)}
