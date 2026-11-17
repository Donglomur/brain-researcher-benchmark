"""Concrete future Docker lifecycle and concurrent framed stdio pump.

This source has not executed Docker. Source checks cannot qualify Docker,
storage quotas, kernel timing, or aggregate CPU containment. Real creation
requires a separately selected trusted physical-storage admission policy.
"""
import base64
import hashlib
import math
import os
from pathlib import Path
import re
import selectors
import signal
import stat
import subprocess
import threading
import time

from morse_broker import BrokerError, exact, integer, positive, canonical
from morse_protocol import FrameDecoder, FrameError, encode_frame, _decode_body


class StageError(ValueError):
    pass


LIMIT_KEYS = ("wall_seconds", "cleanup_seconds", "cpus", "cpu_seconds", "memory_bytes",
              "pids", "file_bytes", "nofile", "workspace_bytes", "output_bytes",
              "tmp_bytes", "stderr_bytes", "stdout_bytes", "frame_bytes",
              "command_timeout_seconds", "gpu_devices")
SPEC_KEYS = ("context_id", "mode", "phase", "name", "image_digest", "python_executable",
             "container_uid", "container_gid", "runtime_root", "capsule_root", "train_root",
             "query_root", "fit_root", "context_root", "output_root", "workspace_root",
             "limits", "storage_profile")


def safe_root(value):
    if type(value) is not str or not os.path.isabs(value) or any(c in value for c in (",", "\n", "\r", "\x00")):
        raise StageError("invalid mount path")
    path = Path(value)
    if str(path) != value or ".." in path.parts or path == Path("/"):
        raise StageError("noncanonical mount path")
    for part in (path, *path.parents):
        if not stat.S_ISDIR(part.lstat().st_mode) or part.is_symlink():
            raise StageError("mount path must traverse ordinary directories")
    return value


def validate_spec(spec):
    exact(spec, SPEC_KEYS, "stage spec")
    if spec["mode"] not in ("frozen_program", "case_adaptive") or spec["phase"] not in ("train", "query"):
        raise StageError("invalid context mode/phase")
    if not isinstance(spec["context_id"], str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", spec["context_id"]):
        raise StageError("invalid context ID")
    if not isinstance(spec["name"], str) or not re.fullmatch(r"morse-[a-z0-9-]{12,80}", spec["name"]):
        raise StageError("invalid owned container name")
    if not isinstance(spec["image_digest"], str) or not re.fullmatch(r"(?:[A-Za-z0-9._/:-]+@)?sha256:[0-9a-f]{64}", spec["image_digest"]):
        raise StageError("pinned image digest required")
    if not isinstance(spec["python_executable"], str) or not re.fullmatch(r"/[A-Za-z0-9_./-]+", spec["python_executable"]):
        raise StageError("fixed absolute container interpreter required")
    if ".." in Path(spec["python_executable"]).parts:
        raise StageError("noncanonical interpreter path")
    integer(spec["container_uid"], "container_uid")
    integer(spec["container_gid"], "container_gid")
    limits = spec["limits"]
    exact(limits, LIMIT_KEYS, "stage limits")
    for key in LIMIT_KEYS:
        if key == "gpu_devices":
            if limits[key] != []:
                raise StageError("this source route supports CPU only")
        elif key in ("wall_seconds", "cleanup_seconds", "cpus", "cpu_seconds", "command_timeout_seconds"):
            positive(limits[key], key)
        else:
            integer(limits[key], key)
    if limits["frame_bytes"] > 0xffffffff:
        raise StageError("frame limit exceeds protocol length field")
    # Fixed CFS period 100 ms. CPU quota is rounded down, never up. This is a
    # conservative rate-times-wall *qualification target*, not a measured
    # cgroup total or a proof that an unqualified daemon kills on deadline.
    quota = math.floor(limits["cpus"] * 100000)
    if not 1000 <= quota <= 0x7fffffffffffffff or limits["cpu_seconds"] < limits["cpus"]*(limits["wall_seconds"]+limits["cleanup_seconds"]+0.1):
        raise StageError("aggregate CPU operand inconsistent with conservative rate/wall bound")
    if limits["cleanup_seconds"] < 4*limits["command_timeout_seconds"]+5:
        raise StageError("cleanup reserve requires four commands plus bounded local cleanup")
    roots = ["runtime_root", "capsule_root", "train_root", "context_root", "output_root", "workspace_root"]
    if spec["phase"] == "train":
        if spec["query_root"] is not None or spec["fit_root"] is not None:
            raise StageError("training stage must not receive query/fit mounts")
    else:
        roots += ["query_root", "fit_root"]
    for key in roots:
        safe_root(spec[key])
    values = [spec[k] for k in roots]
    for i, left in enumerate(values):
        for right in values[i+1:]:
            if left == right or Path(left) in Path(right).parents or Path(right) in Path(left).parents:
                raise StageError("stage mount roots must be disjoint")
    profile = spec["storage_profile"]
    exact(profile, ("mechanism", "admission_id", "output_root", "workspace_root",
                    "output_bytes", "workspace_bytes"), "storage profile")
    if profile["mechanism"] != "independently_admitted_bounded_host_volumes_v1" or not isinstance(profile["admission_id"], str) or not profile["admission_id"]:
        raise StageError("explicit independently admitted storage profile required")
    for key in ("output_root", "workspace_root"):
        if profile[key] != spec[key]:
            raise StageError("storage path binding mismatch")
    for key in ("output_bytes", "workspace_bytes"):
        if profile[key] != limits[key]:
            raise StageError("storage limit binding mismatch")
    return spec


def create_argv(spec):
    validate_spec(spec)
    limits = spec["limits"]
    argv = ["create", "--interactive", "--name", spec["name"],
            "--label", "morse.context="+spec["context_id"],
            "--log-driver", "none",
            "--network", "none", "--read-only", "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges:true", "--cgroupns", "private",
            "--user", str(spec["container_uid"])+":"+str(spec["container_gid"]),
            "--pids-limit", str(limits["pids"]), "--memory", str(limits["memory_bytes"]),
            "--memory-swap", str(limits["memory_bytes"]), "--cpu-period", "100000",
            "--cpu-quota", str(math.floor(limits["cpus"]*100000)),
            "--ulimit", "fsize="+str(limits["file_bytes"])+":"+str(limits["file_bytes"]),
            "--ulimit", "nofile="+str(limits["nofile"])+":"+str(limits["nofile"]),
            "--tmpfs", "/tmp:rw,noexec,nosuid,nodev,size="+str(limits["tmp_bytes"]),
            "--workdir", "/work", "--env", "HOME=/work", "--env", "PYTHONDONTWRITEBYTECODE=1"]
    mounts = [("runtime_root", "/runtime", True), ("capsule_root", "/capsule", True),
              ("train_root", "/training", True), ("context_root", "/context", True),
              ("output_root", "/output", False), ("workspace_root", "/work", False)]
    if spec["phase"] == "query":
        mounts += [("query_root", "/query", True), ("fit_root", "/fit", True)]
    for key, destination, readonly in mounts:
        option = "type=bind,src="+spec[key]+",dst="+destination
        argv += ["--mount", option+(",readonly" if readonly else "")]
    argv += ["--entrypoint", spec["python_executable"], spec["image_digest"],
             "-I", "-B", "/runtime/morse_bootstrap.py", "/context/context.json",
             str(limits["file_bytes"]), str(limits["frame_bytes"])]
    return argv


class DockerCommandTransport:
    """Future real CLI route; no command text, shell, socket mount or host exec tool."""
    kind = "real_future_docker_cli"

    def __init__(self, docker_binary="docker"):
        if docker_binary != "docker" and not os.path.isabs(docker_binary):
            raise StageError("Docker binary must be fixed operator path")
        self.binary = docker_binary

    def start(self, args):
        return subprocess.Popen([self.binary, *args], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                close_fds=True, start_new_session=True,
                                env={"PATH": os.environ.get("PATH", os.defpath)})

    def command(self, args, timeout, byte_limit):
        from morse_broker import bounded_exchange
        proc = self.start(args)
        try:
            out, err = bounded_exchange(proc, b"", byte_limit, byte_limit, timeout, threading.Event())
            return {"returncode": proc.returncode, "stdout": out, "stderr": err}
        finally:
            terminate_process(proc)


def terminate_process(proc):
    if proc.poll() is None:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        proc.wait(timeout=2)
    finally:
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close()


def pump(proc, broker, limits):
    """Concurrent draining during model calls, partial frames and backpressure.

    Transport process is always terminated by its lifecycle owner. This pump
    never considers a worker-written receipt evidence of terminal state.
    """
    decoder = FrameDecoder(limits["frame_bytes"])
    deadline = time.monotonic()+limits["wall_seconds"]
    stdout_bytes = stderr_bytes = 0
    stderr_hash = hashlib.sha256()
    stderr_content = bytearray()
    pending = bytearray()
    result_box = []
    thread = None
    failure = None
    broker_thread_terminal = True
    broker_cancel_error = None
    stdout_eof = False
    with selectors.DefaultSelector() as selector:
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            os.set_blocking(stream.fileno(), False)
        selector.register(proc.stdout, selectors.EVENT_READ, "stdout")
        selector.register(proc.stderr, selectors.EVENT_READ, "stderr")
        def invoke(request):
            try:
                result_box.append((True, broker.handle(request)))
            except Exception as exc:
                result_box.append((False, type(exc).__name__))
        try:
            while selector.get_map() or thread is not None or pending:
                if time.monotonic() >= deadline:
                    raise StageError("stage_wall_deadline")
                if thread is not None and not thread.is_alive():
                    thread.join()
                    thread = None
                    ok, value = result_box.pop()
                    if not ok:
                        raise StageError("broker_request_failed")
                    if stdout_eof or proc.poll() is not None:
                        raise StageError("worker_exited_during_model_call")
                    pending.extend(encode_frame(value, limits["frame_bytes"]))
                    selector.register(proc.stdin, selectors.EVENT_WRITE, "stdin")
                for key, _ in selector.select(min(0.05, max(0, deadline-time.monotonic()))):
                    if key.data == "stdin":
                        try:
                            count = os.write(key.fd, pending[:65536])
                        except BrokenPipeError as exc:
                            raise StageError("worker_closed_response_pipe") from exc
                        del pending[:count]
                        if not pending:
                            selector.unregister(key.fileobj)
                        continue
                    data = os.read(key.fd, 65536)
                    if not data:
                        selector.unregister(key.fileobj)
                        if key.data == "stdout":
                            stdout_eof = True
                            decoder.finish()
                            if thread is not None or pending:
                                raise StageError("worker_eof_with_model_exchange_pending")
                        continue
                    if key.data == "stderr":
                        stderr_bytes += len(data)
                        if stderr_bytes > limits["stderr_bytes"]:
                            raise StageError("stderr_byte_limit")
                        stderr_hash.update(data)
                        stderr_content.extend(data)
                        continue
                    stdout_bytes += len(data)
                    if stdout_bytes > limits["stdout_bytes"]:
                        raise StageError("stdout_byte_limit")
                    if thread is not None or pending:
                        raise StageError("pipelined_tool_request")
                    requests = decoder.feed(data)
                    if requests:
                        if len(requests) != 1 or decoder.buffered_bytes:
                            raise StageError("pipelined_tool_request")
                        thread = threading.Thread(target=invoke, args=(requests[0],), daemon=True)
                        thread.start()
            proc.wait(timeout=max(0.001, deadline-time.monotonic()))
        except Exception as exc:
            failure = type(exc).__name__+":"+str(exc)
        finally:
            if failure is not None or thread is not None:
                try:
                    broker.cancel()
                except Exception as exc:
                    broker_cancel_error = type(exc).__name__
                    failure = "broker_cancel_failed:" + broker_cancel_error
            if thread is not None:
                thread.join(timeout=2.5)
                if thread.is_alive():
                    failure = "broker_thread_cleanup_unobserved"
                    broker_thread_terminal = False
    return {"success": failure is None, "error_code": failure,
            "stdout_bytes": stdout_bytes, "stderr_bytes": stderr_bytes,
            "stderr_sha256": stderr_hash.hexdigest(), "attach_exit_code": proc.poll(),
            "broker_thread_terminal": broker_thread_terminal,
            "broker_cancel_error": broker_cancel_error,
            "stderr_base64": base64.b64encode(stderr_content).decode("ascii"),
            "stderr_custody": "host-private; exclude from public summaries"}


def _checked(transport, args, timeout, limit):
    result = transport.command(args, timeout, limit)
    if (set(result) != {"returncode", "stdout", "stderr"} or
            type(result["returncode"]) is not int or result["returncode"] != 0 or
            type(result["stdout"]) is not bytes or type(result["stderr"]) is not bytes or
            len(result["stdout"]) > limit or len(result["stderr"]) > limit):
        raise StageError("lifecycle_command_failed")
    return result["stdout"]


def run_stage(stage_spec, broker, *, transport=None, storage_admission=None):
    spec = validate_spec(stage_spec)
    if broker.context_id != spec["context_id"] or broker.phase != spec["phase"] or broker.limits["frame_bytes"] != spec["limits"]["frame_bytes"]:
        raise StageError("broker stage binding mismatch")
    transport = DockerCommandTransport() if transport is None else transport
    if transport.kind not in ("real_future_docker_cli", "engineering_invented_transport"):
        raise StageError("unclassified command transport")
    if transport.kind == "real_future_docker_cli":
        if broker.engine.kind != "real_future_https_child":
            raise StageError("real worker requires admitted concrete model route")
        if storage_admission is None:
            raise StageError("physical storage qualification unavailable")
        # A trusted external policy must inspect/admit the actual bounded
        # volumes. No Boolean, hash, posthoc scan or worker report proves it.
        storage_admission.require_storage(spec["storage_profile"])
    limits = spec["limits"]
    timeout = limits["command_timeout_seconds"]
    command_bound = limits["frame_bytes"]
    container_id = None
    creation_attempted = False
    attached = None
    started = time.monotonic()
    receipt = {"context_id": spec["context_id"], "mode": spec["mode"], "phase": spec["phase"],
               "transport_path": transport.kind, "success": False, "error_code": None,
               "terminal_observed": False, "container_exit_code": None,
               "attach_exit_code": None, "cleanup_complete": False,
               "native_containment_qualified": False,
               "storage_qualification_source": "external_required" if transport.kind == "real_future_docker_cli" else "engineering_unqualified",
               "aggregate_cpu_enforcement": "CPU-rate plus wall/cleanup qualification target; not measured aggregate usage"}
    try:
        creation_attempted = True
        created = _checked(transport, create_argv(spec), timeout, command_bound).decode("ascii").strip()
        if not re.fullmatch(r"[0-9a-f]{64}", created):
            raise StageError("invalid_created_container_id")
        container_id = created
        attached = transport.start(["start", "--attach", "--interactive", container_id])
        receipt.update(pump(attached, broker, limits))
        receipt["attach_exit_code"] = attached.poll()
        if not receipt["success"]:
            raise StageError(receipt["error_code"] or "worker_pump_failed")
        wait_raw = _checked(transport, ["wait", container_id], timeout, command_bound)
        if not re.fullmatch(rb"\d+\s*", wait_raw):
            raise StageError("invalid_wait_status")
        state = _decode_body(_checked(transport, ["inspect", "--format", "{{json .State}}", container_id], timeout, command_bound).strip())
        if type(state.get("Running")) is not bool or type(state.get("ExitCode")) is not int or type(state.get("OOMKilled")) is not bool:
            raise StageError("invalid_container_state")
        receipt["terminal_observed"] = not state["Running"]
        receipt["container_exit_code"] = state["ExitCode"]
        if state["Running"] or int(wait_raw) != state["ExitCode"] or state["OOMKilled"]:
            raise StageError("container_terminal_status_mismatch")
        receipt["success"] = bool(receipt["success"] and state["ExitCode"] == 0 and receipt["attach_exit_code"] == 0)
        if not receipt["success"] and receipt["error_code"] is None:
            receipt["error_code"] = "nonzero_worker_exit"
    except Exception as exc:
        receipt["success"] = False
        receipt["error_code"] = type(exc).__name__+":"+str(exc)
    finally:
        cleanup_errors = []
        try:
            broker.cancel()
        except Exception as exc:
            cleanup_errors.append("broker_cancel_failed:" + type(exc).__name__)
        if receipt.get("broker_cancel_error") is not None:
            cleanup_errors.append("pump_broker_cancel_failed")
        if creation_attempted and container_id is None:
            # A timeout/invalid create response cannot prove whether the daemon
            # created an object. Never remove a possibly preexisting name.
            cleanup_errors.append("container_creation_state_unresolved")
        if receipt.get("broker_thread_terminal") is False:
            cleanup_errors.append("broker_thread_cleanup_unobserved")
        if attached is not None:
            try:
                terminate_process(attached)
            except Exception:
                cleanup_errors.append("attach_cleanup_failed")
        if container_id is not None:
            if not receipt["terminal_observed"]:
                try:
                    _checked(transport, ["kill", container_id], timeout, command_bound)
                    _checked(transport, ["wait", container_id], timeout, command_bound)
                    state = _decode_body(_checked(transport, ["inspect", "--format", "{{json .State}}", container_id], timeout, command_bound).strip())
                    if state.get("Running") is not False or type(state.get("ExitCode")) is not int:
                        raise StageError("cleanup_terminal_unobserved")
                    receipt["terminal_observed"] = True
                    receipt["container_exit_code"] = state["ExitCode"]
                except Exception:
                    cleanup_errors.append("container_terminal_cleanup_failed")
            try:
                _checked(transport, ["rm", "--force", container_id], timeout, command_bound)
            except Exception:
                cleanup_errors.append("container_remove_failed")
        try:
            receipt["broker"] = broker.receipt()
            if transport.kind == "real_future_docker_cli" and receipt["broker"].get("model_child_terminal") is not True:
                cleanup_errors.append("model_child_terminal_unobserved")
        except Exception as exc:
            receipt["broker_receipt_error"] = type(exc).__name__
            cleanup_errors.append("broker_receipt_unavailable")
        receipt["cleanup_complete"] = not cleanup_errors
        if cleanup_errors:
            receipt["success"] = False
            receipt["cleanup_errors"] = cleanup_errors
        receipt["observed_wall_seconds_including_cleanup"] = time.monotonic() - started
        receipt["observed_aggregate_cpu_seconds"] = None
    return receipt
