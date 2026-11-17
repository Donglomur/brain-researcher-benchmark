"""Concrete bounded trusted-stage child runner; untrusted roles have another layer.

The runtime component must separately isolate model/tool/candidate/report roles.
This controller is not described as that isolation. It enforces its own finite
worker process limits, captures exit/resources and leaves interrupted claims.
"""
from __future__ import annotations

import hashlib
import hmac
import math
import os
from pathlib import Path
import resource
import selectors
import subprocess
import sys
import time

from .io import Artifact, ArtifactStore, ByteMeter, ContractError, canonical, capture, decode
from .model import StageContext, StageResult
from .workflow import dispatch_worker, verify_implementation
from .contract import load_contract
from .deadline import check as check_deadline
from .process import creation_parent, bind_parent_death
from .containment import Guardian, profile as containment_profile, enter as enter_cgroup


class WorkerFailure(ContractError):
    def __init__(self, message, usage):
        super().__init__(message)
        self.usage = usage


def _limit_child(limits, expected_parent, group):
    bind_parent_death(expected_parent)
    enter_cgroup(group)
    os.setsid()
    cpu = limits["cpu_core_seconds"]
    resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
    resource.setrlimit(resource.RLIMIT_AS, (limits["ram_bytes"], limits["ram_bytes"]))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    cpus = limits["device_manifest"].get("trusted_worker_cpu_ids")
    if not isinstance(cpus, list) or not cpus or any(type(c) is not int or c < 0 for c in cpus):
        raise ContractError("concrete trusted-worker CPU affinity required")
    if not hasattr(os, "sched_setaffinity"):
        raise ContractError("qualified Linux worker affinity required")
    os.sched_setaffinity(0, set(cpus))


def bounded_runner(spec, admitted):
    """Only called after authorize_stage; never launched by source inspection."""
    check_deadline(admitted["deadline"])
    stage, root, limits = spec["stage"], Path(spec["output_root"]), admitted["limits"]
    transport = ArtifactStore(root, ByteMeter(4_000_000, limits["journal_bytes"] // 8))
    transport.mkdir("transport")
    secret = os.urandom(32)  # one invocation transport capability, not issuer key
    worker_limits = dict(limits)
    guard_plan = containment_profile(limits)
    cleanup = spec["parameters"].get("runtime_profile", {}) if spec["stage"] in {"D00","D01","Q00","Q01","Q02","Q03","N00"} else {}
    cleanup_read = cleanup.get("cleanup_read_bytes", 0)
    cleanup_write = cleanup.get("cleanup_write_bytes", 0)
    cleanup_wall = cleanup.get("cleanup_wall_seconds", 0)
    worker_limits["read_bytes"] -= guard_plan["guardian_read_bytes"] + cleanup_read
    worker_limits["write_bytes"] -= guard_plan["guardian_write_bytes"] + cleanup_write
    worker_limits["wall_seconds"] -= 2 * guard_plan["guardian_wall_seconds"] + cleanup_wall + 9
    worker_limits["cpu_core_seconds"] -= guard_plan["guardian_cpu_seconds"]
    worker_limits["ram_bytes"] -= guard_plan["guardian_ram_bytes"]
    if (min(worker_limits[k] for k in ("read_bytes", "wall_seconds", "cpu_core_seconds", "ram_bytes")) <= 0
            or worker_limits["write_bytes"] <= worker_limits["journal_bytes"]):
        raise ContractError("guardian/cleanup reserves leave no complete worker allocation")
    # Reserve the bounded parent read of the final child result as well.
    worker_limits["read_bytes"] -= admitted["proof_read_bytes"] + limits["journal_bytes"] * 3 // 8
    if worker_limits["read_bytes"] <= 0:
        raise ContractError("preflight/result reserve leaves no admitted worker read capacity")
    worker_limits["monotonic_deadline"] = min(time.monotonic() + worker_limits["wall_seconds"],
        admitted["deadline"]["stage_deadline"] - 2 * guard_plan["guardian_wall_seconds"] - cleanup_wall - 9)
    worker_limits["attempt_expires_at"] = spec["attempt_expires_at"]
    if worker_limits["monotonic_deadline"] <= time.monotonic():
        raise ContractError("admission/setup exhausted worker lifetime before creation")
    context = {"schema": "neural063_trusted_worker_context_v1",
               "qualification": admitted["qualification"], "stage": stage,
               "attempt": spec["attempt"], "root": str(root),
               "inputs": spec["inputs"], "parameters": spec["parameters"],
               "prerequisites": admitted["receipts"], "receipt_refs": spec["completions"],
               "limits": worker_limits,
               "contract_pins": admitted["contract"]["pins"],
               "implementation": admitted["implementation"].object(),
               "operation": "authorized_scientific_stage"}
    body = canonical(context)
    signed = {"context": context, "mac": hmac.new(secret, body, hashlib.sha256).hexdigest()}
    context_ref = transport.json("transport/" + stage + ".context.json", signed,
                                 role="trusted_worker_context", visibility="operator", producer=stage)
    result_path = root / "transport" / (stage + ".result.json")
    out_path = root / "transport" / (stage + ".stdout")
    err_path = root / "transport" / (stage + ".stderr")
    key_r, key_w = os.pipe()
    stdout = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    stderr = os.open(err_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o400)
    guardian = None
    process = None
    try:
        os.write(key_w, secret)
        os.close(key_w); key_w = -1
        command = [sys.executable, "-I", "-B", str(Path(__file__).parent.parent / "neural063.py"),
                   "_trusted-worker", "--context", context_ref.path,
                   "--context-sha256", context_ref.sha256,
                   "--context-bytes", str(context_ref.bytes), "--key-fd", str(key_r),
                   "--result", str(result_path)]
        env = {"PATH": os.defpath, "LANG": "C.UTF-8", "PYTHONHASHSEED": "0",
               "OMP_NUM_THREADS": str(len(limits["device_manifest"]["trusted_worker_cpu_ids"])),
               "OPENBLAS_NUM_THREADS": str(len(limits["device_manifest"]["trusted_worker_cpu_ids"]))}
        check_deadline(admitted["deadline"])
        guardian = Guardian(spec, worker_limits, transport)
        expected_parent = creation_parent()
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=env, cwd=root, close_fds=True,
                                   pass_fds=(key_r,), preexec_fn=lambda: _limit_child(worker_limits, expected_parent, guardian.group))
        os.close(key_r); key_r = -1
        started = time.monotonic()
        status = usage = None
        timeout = False
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, stdout)
        selector.register(process.stderr, selectors.EVENT_READ, stderr)
        log_bytes = 0
        log_cap = limits["journal_bytes"] // 8
        over_cap_bytes = 0
        lingering_pipes = False
        pipe_deadline = worker_limits["monotonic_deadline"] + 1
        while status is None or selector.get_map():
            for key, _ in selector.select(0.05):
                chunk = os.read(key.fileobj.fileno(), min(65536, max(1, log_cap - log_bytes + 1)))
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                keep = min(len(chunk), max(0, log_cap - log_bytes))
                if keep:
                    os.write(key.data, chunk[:keep])
                    log_bytes += keep
                if keep != len(chunk):
                    over_cap_bytes += len(chunk) - keep
                    timeout = True
            if guardian.process.poll() is not None:
                timeout = True
            elapsed = time.monotonic() - started
            if status is not None:
                if selector.get_map() and not guardian.terminations:
                    # Leader ownership has ended. Pin-scoped cgroup cleanup
                    # catches setsid descendants immediately; never killpg.
                    guardian.terminate("leader_reaped_with_lingering_pipes")
                    pipe_deadline = time.monotonic() + 1
                if selector.get_map() and time.monotonic() > pipe_deadline:
                    timeout = lingering_pipes = True
                    for key in list(selector.get_map().values()):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                continue
            pid, child_status, child_usage = os.wait4(process.pid, os.WNOHANG)
            if pid:
                status, usage = child_status, child_usage
                pipe_deadline = time.monotonic() + 1
                continue
            if time.monotonic() >= worker_limits["monotonic_deadline"] or time.time() >= spec["attempt_expires_at"] or timeout:
                timeout = True
                if not guardian.terminations:
                    guardian.terminate("worker_deadline_or_limit")
                reap_deadline = time.monotonic() + 2
                while True:
                    reaped, status_candidate, usage_candidate = os.wait4(process.pid, os.WNOHANG)
                    if reaped:
                        status, usage = status_candidate, usage_candidate
                        pipe_deadline = time.monotonic() + 1
                        break
                    if time.monotonic() >= reap_deadline:
                        raise ContractError("trusted child did not reap within finite cleanup reserve")
                    time.sleep(0.02)
        selector.close()
        process.returncode = os.waitstatus_to_exitcode(status)
        measured = {"wall_seconds": time.monotonic() - started,
                    "trusted_worker_user_cpu_seconds": usage.ru_utime,
                    "trusted_worker_system_cpu_seconds": usage.ru_stime,
                    "trusted_worker_peak_rss_bytes": usage.ru_maxrss * 1024,
                    "rss_platform": "qualified_linux_kib", "exit_code": process.returncode,
                    "timeout_or_log_limit": timeout,
                    "descendant_pipe_cleanup_failure": lingering_pipes,
                    "log_prefix_only_due_to_limit": bool(over_cap_bytes),
                    "received_over_log_cap_bytes": over_cap_bytes,
                    "uncaptured_emitted_log_bytes": None if over_cap_bytes else 0,
                    "stdout_bytes": out_path.stat().st_size, "stderr_bytes": err_path.stat().st_size,
                    "candidate_container_resources": "separately measured by runtime component",
                    "physical_os_io": None}
        measured["cgroup_guardian"] = guardian.finish()
        guardian = None
        observed = measured["cgroup_guardian"]["observations"]
        aggregate_exceeded = observed["cpu"].get("usage_usec", 0) > worker_limits["cpu_core_seconds"] * 1000000
        if timeout or process.returncode or aggregate_exceeded:
            raise WorkerFailure("trusted stage worker failed or exceeded aggregate CPU", measured)
        try:
            result_body = capture(result_path, limits["journal_bytes"] // 4)
            measured["parent_result_read_bytes"] = len(result_body)
            measured["context_transport_write_bytes"] = transport.meter.write_bytes
            result = decode(result_body)
            if result.get("schema") != "neural063_trusted_worker_result_v1" or result.get("stage") != stage:
                raise ContractError("wrong trusted child result")
            measured["artifact_usage"] = result["artifact_usage"]
            output = result["result"]
            return StageResult(output["outcome"],
                               {k: Artifact.parse(v) for k, v in output["artifacts"].items()},
                               output["measurements"], output["reasons"]), measured
        except Exception as exc:
            raise WorkerFailure("invalid trusted child result: " + str(exc), measured) from exc
    finally:
        active_error = sys.exc_info()[1]
        closure_result = None
        cleanup_error = None
        if guardian is not None:
            try:
                closure_result = guardian.finish()
            except BaseException as exc:
                cleanup_error = exc
        if process is not None and process.returncode is None:
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired as exc:
                cleanup_error = exc
        if process is not None:
            for pipe in (process.stdout, process.stderr):
                if pipe is not None and not pipe.closed:
                    pipe.close()
        for fd in (key_r, key_w, stdout, stderr):
            if fd >= 0:
                os.close(fd)
        if cleanup_error is not None or (active_error is not None and not isinstance(active_error, WorkerFailure)):
            raise WorkerFailure("trusted worker/containment failed: " + str(cleanup_error or active_error),
                                {"closure_error": str(cleanup_error) if cleanup_error else None,
                                 "cgroup_guardian": closure_result,
                                 "containment_recovery": getattr(cleanup_error, "usage", {}),
                                 "prior_error": str(active_error), "prior_usage": getattr(active_error, "usage", {}),
                                 "unavailable_worker_counters": "unknown after interrupted closure; never zero-imputed"}) from active_error


def worker_main(args):
    secret = os.read(args.key_fd, 33)
    os.close(args.key_fd)
    if len(secret) != 32:
        raise ContractError("exact one-use parent transport capability required")
    ref = Artifact(args.context, args.context_bytes, args.context_sha256,
                   "trusted_worker_context", "operator", "transport")
    signed = decode(capture(args.context, args.context_bytes, descriptor=ref))
    context = signed["context"]
    expected = hmac.new(secret, canonical(context), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signed["mac"], expected):
        raise ContractError("parent context authentication failed")
    if context["schema"] != "neural063_trusted_worker_context_v1":
        raise ContractError("wrong trusted-worker context")
    limits = context["limits"]
    meter = ByteMeter(limits["read_bytes"], limits["write_bytes"] - limits["journal_bytes"])
    meter.read(args.context_bytes + len(secret))
    verify_implementation(context["implementation"], meter=meter)
    contract = load_contract(meter=meter)
    if context["contract_pins"] != contract["pins"]:
        raise ContractError("contract changed before worker import")
    store = ArtifactStore(context["root"], meter)
    ctx = StageContext(context["stage"], context["attempt"], store, context["inputs"],
                       context["parameters"], context["prerequisites"], contract,
                       limits, context["operation"], receipt_refs=context["receipt_refs"], qualification=context["qualification"])
    ctx.require_scientific()
    result = dispatch_worker(ctx)
    ctx.require_scientific()
    output = {"schema": "neural063_trusted_worker_result_v1", "stage": ctx.stage,
              "result": result.object(), "artifact_usage": meter.snapshot()}
    body = canonical(output)
    if len(body) > limits["journal_bytes"] // 4:
        raise ContractError("worker result exceeds reserved receipt allocation")
    fd = os.open(args.result, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, "wb") as stream:
        stream.write(body); stream.flush(); os.fsync(stream.fileno())
    return 0
