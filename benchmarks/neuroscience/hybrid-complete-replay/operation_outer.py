"""One complete selected Hybrid replay, with outer ownership and recovery.

Source-only until root provides an exact fresh admission binding. The old
reference-fit worker is never dispatched. No retry or partial-cohort success.
"""
import argparse
import types
import hashlib
import json
import os
from pathlib import Path
import platform
import selectors
import signal
import stat
import subprocess
import sys
import time


def _verified_source_binding(here):
    """Read the literal accepted helper once and execute only its captured bytes."""
    if "source_binding" in sys.modules:
        raise ValueError("fresh source_binding module namespace required")
    path = Path(here) / "source_binding.py"
    if not path.is_absolute() or ".." in path.parts or any(x.is_symlink() for x in (path, *path.parents)):
        raise ValueError("ordinary bootstrap path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != 4147:
            raise ValueError("bootstrap extent/type")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(4148)
        stamp = lambda info: (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
                              info.st_size, info.st_mtime_ns, info.st_ctime_ns)
        if stamp(before) != stamp(os.fstat(fd)) or stamp(before) != stamp(path.lstat()):
            raise ValueError("bootstrap changed")
        if len(raw) != 4147 or hashlib.sha256(raw).hexdigest() != "1079a68cb275a35543f02dff2ad973ef2ae2e89b85c72fab9263d00eee89c3ce":
            raise ValueError("bootstrap identity")
    finally:
        os.close(fd)
    module = types.ModuleType("source_binding")
    module.__file__ = str(path)
    sys.modules["source_binding"] = module
    try:
        exec(compile(raw, str(path), "exec"), module.__dict__)
    except BaseException:
        if sys.modules.get("source_binding") is module:
            del sys.modules["source_binding"]
        raise
    return module


def worker_argv(plan, here, lock_sha, deadline):
    return [plan["venv_entry"]["path"], "-I", "-B", str(here / "operation_worker.py"),
            "--lock-sha256", lock_sha, "--work-deadline", repr(deadline)]


def main():
    started = time.monotonic()
    ap = argparse.ArgumentParser()
    ap.add_argument("--lock-sha256", required=True)
    args = ap.parse_args()
    here = Path(__file__).absolute().parent
    binding = _verified_source_binding(here)
    plan, lock, bodies, delivery, sources, owner, modules = binding.load(args.lock_sha256)
    contract, reuse = modules["result_contract"], modules["reuse_delivery"]
    deadline = started + plan["outer_seconds"]
    work_deadline = started + plan["worker_seconds"]
    binding.need(plan["outer_seconds"] - plan["worker_seconds"] >= 600,
                 "original independent cleanup reserve")
    binding.need(sys.version_info[:3] == (3, 11, 6) and sys.platform == "darwin" and
                 platform.machine() == "arm64" and os.path.realpath(sys.executable) == plan["base_entry"]["path"],
                 "exact selected host interpreter")
    read_bytes = sum(map(len, bodies.values()))
    def read(path, cap):
        nonlocal read_bytes
        path = Path(path)
        info = path.lstat()
        binding.need(0 <= info.st_size <= cap and read_bytes + info.st_size <= 512 * 1048576,
                     "complete parent source/runtime read admission")
        # Runtime verifier supplies its own expected identities. This bounded
        # reader additionally enforces ordinary stable complete file reads.
        delivery.ordinary(path)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            before = os.fstat(fd)
            binding.need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= cap,
                         "ordinary single-link runtime file")
            with os.fdopen(fd, "rb", closefd=False) as f:
                body = f.read(before.st_size + 1)
            binding.need(len(body) == before.st_size and delivery.stamp(before) ==
                         delivery.stamp(os.fstat(fd)) == delivery.stamp(path.lstat()), "stable complete runtime read")
        finally:
            os.close(fd)
        read_bytes += len(body)
        return body
    for pin in (plan["base_entry"], plan["venv_entry"], plan["runtime_checker"], plan["runtime_receipt"]):
        body = read(pin["path"], pin["bytes"])
        binding.need((len(body), hashlib.sha256(body).hexdigest()) == (pin["bytes"], pin["sha256"]),
                     "exact existing runtime component")
    checker_path = Path(plan["runtime_checker"]["path"])
    runtime = binding.module("selected_existing_runtime_checker", checker_path, bodies[str(checker_path)])
    runtime_receipt = json.loads(read(plan["runtime_receipt"]["path"], plan["runtime_receipt"]["bytes"]))
    # This source package is not execution authority. Root must select the exact
    # union, full cohort, time horizon and complete disk reservation explicitly.
    admission = json.loads(read(plan["capacity_binding"], 65536))
    required = {"source_lock_sha256": args.lock_sha256, "positive": True,
        "full_operation_selected": True, "episodes": 4884, "decisions": 163135, "new_fits": 0,
        "host_memory_reserved_bytes": 2 * 1024**3, "vm_memory_reserved_bytes": 1024**3,
        "output_reserved_bytes": plan["private_output_cap_bytes"], "worker_seconds": plan["worker_seconds"],
        "outer_seconds": plan["outer_seconds"], "operation_token": plan["operation_token"],
        "managed_read_reserved_bytes": plan["resources"]["whole_explicit_read_ceiling_bytes"]}
    binding.need(all(admission.get(k) == v and type(admission.get(k)) is type(v) for k, v in required.items()),
                 "exact fresh root-selected complete-operation admission")
    age = time.time() - admission["observed_unix_seconds"]
    binding.need(0 <= age <= 300, "fresh capacity observation")
    output, capture = Path(plan["output"]), Path(plan["caller"])
    for root in (output, capture):
        delivery.ordinary(root)
        binding.need(not os.path.lexists(root) and all(x.is_dir() for x in root.parents), "fresh ordinary output namespace")
    before_runtime = runtime.verify_runtime_identity(Path(plan["venv"]), runtime_receipt, read)
    endpoint = sources.modules["endpoint_guard"].authenticate_endpoint_binary(plan)
    read_bytes += endpoint["bytes"]
    binding.need(read_bytes <= 512 * 1048576, "complete parent read ceiling")
    capture.mkdir(mode=0o700)
    output.mkdir(mode=0o700)
    (output / "empty-docker-config").mkdir(mode=0o700)
    received, old = [], {}
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        old[sig] = signal.signal(sig, lambda signum, frame: received.append(signum))
    argv = worker_argv(plan, here, args.lock_sha256, work_deadline)
    binding.emit(capture / "REQUEST.json", {"argv": argv, "cwd": str(here), "attempts": 1,
        "source_lock_sha256": args.lock_sha256, "original_deadline": deadline,
        "original_work_deadline": work_deadline, "fresh_capacity": admission, "endpoint": endpoint})
    child = closure = recovery = after_runtime = None
    error = None
    streams, eof = {"stdout": bytearray(), "stderr": bytearray()}, set()
    selector = selectors.DefaultSelector()
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": plan["operator_home"], "TMPDIR": str(output),
           "LANG": "C", "LC_ALL": "C", "PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[name] = "1"
    try:
        child = subprocess.Popen(argv, cwd=here, env=env, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        binding.emit(capture / "OWNED_GROUP.json", {"pid": child.pid, "pgid": child.pid,
                                                    "direct_new_session": True, "argv": argv})
        for label, pipe in (("stdout", child.stdout), ("stderr", child.stderr)):
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, label)
        while selector.get_map():
            binding.need(not received and time.monotonic() < work_deadline, "original work horizon or signal")
            for key, _ in selector.select(.1):
                label = key.data
                body = os.read(key.fileobj.fileno(), min(8192, 65536 - len(streams[label]) + 1))
                if not body:
                    eof.add(label)
                    selector.unregister(key.fileobj)
                    continue
                room = 65536 - len(streams[label])
                streams[label].extend(body[:room])
                binding.need(len(body) <= room, "complete caller stream cap")
        child.wait(timeout=max(0, work_deadline - time.monotonic()))
        binding.need(child.returncode == 0, "complete worker natural zero exit")
    except BaseException as exc:
        error = {"type": type(exc).__name__, "reason": str(exc)[:2048]}
    finally:
        selector.close()
        if child is not None:
            try:
                closure = owner.close_owned(child, min(deadline - 120, time.monotonic() + 12))
            except BaseException as exc:
                error = error or {"type": type(exc).__name__, "reason": "worker group closure: " + str(exc)}
            for pipe in (child.stdout, child.stderr):
                pipe.close()
        try:
            controller_closed = child is None or (closure is not None and closure["reaped"] and
                closure["process_group_absent"] and not closure["errors"])
            recovery = sources.harness.recover_operation(plan, sources.runner_root, output, capture,
                                                         deadline, controller_closed)
        except BaseException as exc:
            error = error or {"type": type(exc).__name__, "reason": "independent recovery: " + str(exc)}
        try:
            after_runtime = runtime.verify_runtime_identity(Path(plan["venv"]), runtime_receipt, read)
            sources.check()
            binding.recheck(lock)
        except BaseException as exc:
            error = error or {"type": type(exc).__name__, "reason": "whole source/runtime closure: " + str(exc)}
        for name, body in streams.items():
            with (capture / (name + ".txt")).open("xb") as f:
                f.write(body)
        try:
            worker = json.loads(read(output / "RESULT.json", 1048576))
            contract.validate(worker, args.lock_sha256)
            participant = json.loads(binding.exact(worker["participant_result"]["path"], worker["participant_result"], 16 * 1048576))
            binding.need(participant["source_closure"] == sources.closure and
                participant["reference_sha256"] == delivery.REFERENCE_PIN[1] and
                participant["outer_recovery_still_required"] is True and
                participant["participant_result"]["score"] == worker["participant_summary"] and
                len(participant["participant_result"]["whole_trial_artifact_mapping_private"]) == 4884,
                "complete participant result pin and population")
            reference = delivery.Snapshot(plan["references"]["path"], delivery.REFERENCE_PIN, 2 * 1048576)
            historical = sources.export._json(reference.body, 2 * 1048576)
            contract.reconcile_score(worker["participant_summary"], historical["scores"]["family_train_selected"])
            key = binding.exact(worker["curator_key"]["path"], worker["curator_key"], 32)
            reuse.require_reuse(sources, worker["reuse_receipt"]["path"], worker["reuse_receipt"],
                                worker["delivery_manifest"], key,
                                artifact_locations=plan.get("historical_artifact_locations")).check()
            reference.check()
        except BaseException as exc:
            error = error or {"type": type(exc).__name__, "reason": "complete result reconciliation: " + str(exc)}
        output_bytes = 0
        try:
            for root in (output, capture):
                for directory, dirs, files in os.walk(root, followlinks=False):
                    binding.need(not any((Path(directory) / n).is_symlink() for n in dirs), "no output directory aliases")
                    for name in files:
                        info = (Path(directory) / name).lstat()
                        binding.need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, "ordinary private output")
                        output_bytes += info.st_size
            binding.need(output_bytes + 3 * 1048576 <= plan["private_output_cap_bytes"], "complete receipt-inclusive disk admission")
        except BaseException as exc:
            error = error or {"type": type(exc).__name__, "reason": "whole retained output: " + str(exc)}
        okay = (error is None and not received and closure is not None and closure["exit_code"] == 0 and
            closure["reaped"] and closure["process_group_absent"] and not closure["errors"] and
            not closure["signals_sent"] and recovery is not None and recovery["complete"] and
            before_runtime == after_runtime and eof == {"stdout", "stderr"})
        outcome = {"schema": "hybrid-complete-no-refit-outer-outcome-v1", "status": "COMPLETE" if okay else "FAILED_PRESERVED",
            "error": error, "closure": closure, "recovery_complete": bool(recovery and recovery["complete"]),
            "runtime_before": before_runtime, "runtime_after": after_runtime,
            "bounded_runtime_reader_plus_initial_union_and_endpoint_bytes": read_bytes,
            "read_counter_excludes": "Additional exact source snapshots/rechecks and separately capped result/reuse reads; see READ_BOUNDS.json for the complete conservative managed-I/O derivation.",
            "output_bytes_before_final_receipt": output_bytes, "closure_receipt_reservation_bytes": 3 * 1048576,
            "signals_received": received, "EOF": sorted(eof), "elapsed_seconds": time.monotonic() - started,
            "source_lock_sha256": args.lock_sha256, "attempts": 1, "retries": 0, "new_fits": 0, "scientific_count_delta": 0}
        try:
            terminal_code = contract.finish(outcome, okay, deadline, received, capture, binding.emit)
        finally:
            for sig, handler in old.items():
                signal.signal(sig, handler)
    return terminal_code


if __name__ == "__main__":
    raise SystemExit(main())
