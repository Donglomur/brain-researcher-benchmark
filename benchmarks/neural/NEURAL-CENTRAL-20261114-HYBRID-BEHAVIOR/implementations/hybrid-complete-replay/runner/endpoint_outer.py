"""One selected Hybrid construction, adapted from the accepted finite caller.

Full pre/post runtime identity, original absolute worker horizon, owned-group
closure and independent exact container recovery. No installation or retry.
"""
import argparse
import hashlib
import importlib.util
import json
import os
import platform
from pathlib import Path
import resource
import selectors
import signal
import stat
import subprocess
import sys
import time


def main():
    started = time.monotonic(); ap = argparse.ArgumentParser(); ap.add_argument("--lock-sha256", required=True); args = ap.parse_args()
    here = Path(__file__).absolute().parent; raw = (here / "SOURCE_LOCK.json").read_bytes()
    if hashlib.sha256(raw).hexdigest() != args.lock_sha256: raise RuntimeError("selected whole source lock")
    lock = json.loads(raw); read_bytes = len(raw)
    def read(path, cap):
        nonlocal read_bytes
        path = Path(path)
        if any(x.is_symlink() for x in (path, *path.parents)): raise RuntimeError("ordinary selected path")
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as f:
            before = os.fstat(f.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > cap: raise RuntimeError("ordinary bounded complete file")
            if read_bytes + before.st_size > 512 * 1024**2: raise RuntimeError("parent explicit source/runtime bound")
            b = f.read(cap + 1); after = os.fstat(f.fileno()); read_bytes += len(b)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if stamp(before) != stamp(after) or len(b) != before.st_size: raise RuntimeError("stable complete source/runtime read")
        return b
    source_before = {}
    for name, pin in lock["files"].items():
        if Path(name).name != name: raise RuntimeError("flat selected source")
        b = read(here / name, pin["bytes"])
        if (len(b), hashlib.sha256(b).hexdigest()) != (pin["bytes"], pin["sha256"]): raise RuntimeError("source pin")
        source_before[name] = pin["sha256"]
    plan = json.loads((here / "PLAN.json").read_bytes()); plan["source_lock_sha256"] = args.lock_sha256
    deadline = started + plan["outer_seconds"]
    if sys.version_info[:3] != (3, 11, 6) or sys.platform != "darwin" or platform.machine() != "arm64": raise RuntimeError("selected host interpreter")
    if os.path.realpath(sys.executable) != plan["base_entry"]["path"]: raise RuntimeError("exact caller interpreter path")
    for pin in (plan["base_entry"], plan["venv_entry"], plan["runtime_checker"], plan["runtime_receipt"]):
        b = read(pin["path"], pin["bytes"])
        if hashlib.sha256(b).hexdigest() != pin["sha256"]: raise RuntimeError("exact existing runtime component")
    sys.path.insert(0, str(here))
    from owner_core import close_owned
    from endpoint_guard import authenticate_endpoint_binary
    from transport_harness import recover_operation
    from reference_workflow import emit
    spec = importlib.util.spec_from_file_location("selected_existing_runtime_checker", plan["runtime_checker"]["path"])
    runtime = importlib.util.module_from_spec(spec); spec.loader.exec_module(runtime)
    receipt = json.loads(read(plan["runtime_receipt"]["path"], plan["runtime_receipt"]["bytes"]))
    output = Path(plan["output"]); capture = Path(plan["caller"])
    for root in (output, capture):
        if os.path.lexists(root) or any(x.is_symlink() or not x.is_dir() for x in root.parents): raise RuntimeError("fresh ordinary namespaces")
    capture.mkdir(mode=0o700); output.mkdir(mode=0o700); (output / "empty-docker-config").mkdir(mode=0o700)
    before_runtime = runtime.verify_runtime_identity(Path(plan["venv"]), receipt, read)
    endpoint = authenticate_endpoint_binary(plan)
    read_bytes += endpoint["bytes"]
    if read_bytes > 512 * 1024**2: raise RuntimeError("complete parent source/runtime read admission")
    # Root's selected resource binding must name the exact same proposal and
    # reserve host2GiB plus the serial participant container1GiB before dispatch.
    # No capacity is inferred from a past operation or an image's mere existence.
    capacity = json.loads(read(plan["capacity_binding"], 65536))
    if capacity.get("source_lock_sha256") != args.lock_sha256 or capacity.get("host_memory_reserved_bytes") != 2 * 1024**3 or capacity.get("vm_memory_reserved_bytes") != 1024**3 or capacity.get("positive") is not True:
        raise RuntimeError("exact fresh root-selected host/VM resource binding")
    age = time.time() - capacity["observed_unix_seconds"]
    if not 0 <= age <= 300: raise RuntimeError("fresh resource observation age")
    signals = []; old = {}
    def record(signum, frame): signals.append(signum)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP): old[sig] = signal.signal(sig, record)
    argv = [plan["venv_entry"]["path"], "-I", "-B", str(here / "endpoint_worker.py"), "--lock-sha256", args.lock_sha256]
    emit(capture / "REQUEST.json", {"argv": argv, "source_lock_sha256": args.lock_sha256, "attempts": 1,
                                   "original_deadline": deadline, "fresh_capacity": capacity, "endpoint": endpoint})
    child = None; closure = None; recovery = None; error = None; after_runtime = None
    streams = {"stdout": bytearray(), "stderr": bytearray()}; eof = set(); selector = selectors.DefaultSelector()
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": plan["operator_home"], "TMPDIR": str(output),
           "LANG": "C", "LC_ALL": "C", "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"): env[k] = "1"
    try:
        child = subprocess.Popen(argv, cwd=here, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        emit(capture / "OWNED_GROUP.json", {"pid": child.pid, "pgid": child.pid, "direct_new_session": True, "argv": argv})
        for label, pipe in (("stdout", child.stdout), ("stderr", child.stderr)):
            os.set_blocking(pipe.fileno(), False); selector.register(pipe, selectors.EVENT_READ, label)
        while selector.get_map():
            if signals or time.monotonic() >= deadline - 60: raise RuntimeError("original whole construction deadline or signal")
            for key, _ in selector.select(.1):
                label = key.data; b = os.read(key.fileobj.fileno(), min(8192, 65536 - len(streams[label]) + 1))
                if not b: eof.add(label); selector.unregister(key.fileobj); continue
                room = 65536 - len(streams[label]); streams[label].extend(b[:room])
                if len(b) > room: raise RuntimeError("complete caller stream cap")
        child.wait(timeout=max(0, deadline - 60 - time.monotonic()))
        if child.returncode != 0: raise RuntimeError("construction worker did not complete")
    except BaseException as exc:
        error = {"type": type(exc).__name__, "reason": str(exc)[:2048]}
    finally:
        selector.close()
        if child is not None:
            try: closure = close_owned(child, min(deadline - 40, time.monotonic() + 12))
            except BaseException as exc: error = error or {"type": type(exc).__name__, "reason": "group closure: " + str(exc)}
            for pipe in (child.stdout, child.stderr): pipe.close()
        try:
            controller_closed = child is None or (closure is not None and closure["reaped"] and closure["process_group_absent"] and not closure["errors"])
            recovery = recover_operation(plan, here, output, capture, deadline, controller_closed)
        except BaseException as exc: error = error or {"type": type(exc).__name__, "reason": "independent episode recovery: " + str(exc)}
        try: after_runtime = runtime.verify_runtime_identity(Path(plan["venv"]), receipt, read)
        except BaseException as exc: error = error or {"type": type(exc).__name__, "reason": "runtime postcheck: " + str(exc)}
        try:
            for name, pin in lock["files"].items():
                b = read(here / name, pin["bytes"])
                if hashlib.sha256(b).hexdigest() != source_before[name]: raise RuntimeError("source changed during operation")
        except BaseException as exc: error = error or {"type": type(exc).__name__, "reason": "source closure: " + str(exc)}
        for name, b in streams.items():
            with (capture / (name + ".txt")).open("xb") as f: f.write(b)
        worker = None
        try:
            b = read(output / "RESULT.json", 1048576); worker = json.loads(b)
            if worker["status"] != "COMPLETE_PREFIX_AND_TRAIN_ONLY_STATISTICAL_REFERENCES" or worker["source_lock_sha256"] != args.lock_sha256:
                raise RuntimeError("complete worker result identity/status")
            if worker["controls"]["control_count"] != 22 or worker["controls"]["real_container_episodes"] != 17 or worker["episodes_registered"] != 17 or worker["all_registered_episodes_closed"] is not True:
                raise RuntimeError("complete new control workload and containment")
            if worker["reference_result"]["complete_outer_folds"] != 80 or worker["reference_result"]["inner_ridge_fits"] != 720 or worker["reference_result"]["final_ridge_fits"] != 80:
                raise RuntimeError("complete trusted reference fit population")
            for score in worker["reference_result"]["scores"].values():
                if (score["participants"], score["sessions"], score["trials"], score["decisions"]) != (20, 80, 4884, 163135):
                    raise RuntimeError("complete scientific score population")
        except BaseException as exc: error = error or {"type": type(exc).__name__, "reason": "worker receipt: " + str(exc)}
        output_bytes = 0
        try:
            for root in (output, capture):
                for directory, dirs, files in os.walk(root, followlinks=False):
                    if any((Path(directory) / n).is_symlink() for n in dirs): raise RuntimeError("private output directory alias")
                    for n in files:
                        f = Path(directory) / n; s = f.lstat()
                        if not stat.S_ISREG(s.st_mode) or s.st_nlink != 1: raise RuntimeError("ordinary complete private output")
                        output_bytes += s.st_size
            if output_bytes + 1048576 > plan["private_output_cap_bytes"]: raise RuntimeError("complete receipt-inclusive output admission")
        except BaseException as exc: error = error or {"type": type(exc).__name__, "reason": "whole output retention: " + str(exc)}
        okay = error is None and not signals and closure is not None and closure["exit_code"] == 0 and closure["reaped"] and closure["process_group_absent"] and not closure["errors"] and not closure["signals_sent"] and recovery is not None and recovery["complete"] and before_runtime == after_runtime and eof == {"stdout", "stderr"}
        result = {"schema": "hybrid-endpoint-whole-outer-outcome-v1", "status": "COMPLETE" if okay else "FAILED_PRESERVED",
            "error": error, "closure": closure, "recovery_complete": recovery["complete"] if recovery else False,
            "runtime_before": before_runtime, "runtime_after": after_runtime, "explicit_parent_reads": read_bytes,
            "output_bytes_before_final_receipt": output_bytes, "closure_receipt_reservation_bytes": 1048576,
            "signals_received": signals, "EOF": sorted(eof), "elapsed_seconds": time.monotonic() - started,
            "source_lock_sha256": args.lock_sha256, "attempts": 1, "retries": 0, "scientific_count_delta": 0}
        emit(capture / "OUTCOME.json", result)
        for sig, handler in old.items(): signal.signal(sig, handler)
    print(json.dumps({"status": result["status"], "no_retry": True}))
    return 0 if okay else 1


if __name__ == "__main__":
    raise SystemExit(main())
