"""Reviewed donor source functions plus owned-group descendant closure correction."""
import hashlib
import os
import signal
import stat
import time

def signal_recorder(received):
    def record(signum, frame):
        if len(received) < 64:
            received.append(signum)
    return record


def close_owned(child, deadline, clock=time.monotonic, send=os.killpg, pause=time.sleep):
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

    def group_presence(label):
        try:
            send(child.pid, 0)
            events.append({'operation':label,'status':'present'})
            return True
        except ProcessLookupError:
            events.append({'operation':label,'status':'absent'})
            return False
        except BaseException as exc:
            errors.append({'operation':label,'type':type(exc).__name__,'message':str(exc)[:512]})
            return None

    for sig, allowance in ((signal.SIGTERM, 5), (signal.SIGKILL, 5)):
        polled, code = attempt("poll_before_" + sig.name, child.poll)
        present = group_presence('probe_before_' + sig.name)
        # The detached Popen leader identifies the exclusively owned group.
        # Reaped leader and absent group are different facts: native substages
        # may survive a worker crash and must also be closed.
        if not polled or code is None or present is not False:
            delivered, _ = attempt("send_" + sig.name, lambda sig=sig: send(child.pid, sig))
            if delivered:
                sent.append(sig.name)
            if not polled or code is None:
                attempt("wait_after_" + sig.name,
                        lambda allowance=allowance: child.wait(timeout=max(0, min(allowance, deadline - clock()))))
            stop = min(deadline, clock() + allowance)
            for _ in range(250):
                if group_presence('probe_after_' + sig.name) is False or clock() >= stop:
                    break
                attempt('pause_after_' + sig.name, lambda: pause(min(0.02, max(0, stop-clock()))))
    _, code = attempt("final_poll", child.poll)
    # Reaping and group absence are separate observations even after failed kill/wait.
    if code is None:
        _, code = attempt("final_nonblocking_reap", lambda: child.wait(timeout=0))
    absent = group_presence('final_group_probe') is False
    return {"exit_code": code, "reaped": code is not None, "process_group_absent": absent,
            "events": events, "errors": errors, "signals_sent": sent}


def exact_source(path, descriptor):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != descriptor["bytes"]:
            raise ValueError("ordinary exact caller source")
        if before.st_size > 1048576:
            raise ValueError("caller source bound")
        body = bytearray()
        while len(body) < before.st_size:
            part = os.read(fd, min(65536, before.st_size - len(body)))
            if not part:
                raise ValueError("caller source EOF")
            body.extend(part)
        if os.read(fd, 1):
            raise ValueError("caller source tail")
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        if any(getattr(before, k) != getattr(after, k) for k in fields):
            raise ValueError("caller source changed")
        if hashlib.sha256(body).hexdigest() != descriptor["sha256"]:
            raise ValueError("caller source identity")
        return bytes(body)
    finally:
        os.close(fd)

