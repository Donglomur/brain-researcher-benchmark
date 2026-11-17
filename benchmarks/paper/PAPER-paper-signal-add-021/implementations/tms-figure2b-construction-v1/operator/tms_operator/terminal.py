"""Fixed bounded Harbor terminal transport; construction only, no native admission.

Imported only by the source-admitted trusted host. Candidate text is passed solely
as the selected container shell argument. No task/data/reference is loaded here.
"""
import asyncio
import base64
import codecs
import contextvars
import hashlib
import json
import math
import os
import re
import stat
import sys
import time
from pathlib import Path
from types import MappingProxyType

from harbor.environments.base import ExecResult
from harbor.environments.capabilities import EnvironmentCapabilities
from harbor.environments.docker.docker import (
    DockerEnvironment, _sanitize_docker_compose_project_name,
)
from tms_figure.contract import Budget

_ACTIVE = contextvars.ContextVar("figure_terminal_invocation", default=None)
_QUANTUM = 4096
_POLICY_KEYS = {
    "docker_path", "docker_host", "compose_project", "docker_env",
    "lifecycle_read_bytes", "lifecycle_write_bytes",
    "lifecycle_deadline_monotonic", "cleanup_read_bytes", "cleanup_write_bytes",
    "cleanup_deadline_monotonic", "metadata_timeout_seconds", "metadata_output_cap",
    "compose_file", "image_id", "image_environment", "keepalive_argv",
    "docker_cgroup_parent", "container_user", "cpu_count", "memory_bytes",
    "memory_swap_bytes", "pids_limit", "mounts", "tmpfs_bytes", "container_environment",
}


class TerminalArmFailure(RuntimeError):
    """The original operation failed; closure evidence is separate, never implied."""
    def __init__(self, first_failure, cleanup, cleanup_exceptions=()):
        super().__init__("terminal arm aborted: " + first_failure["type"])
        self.first_failure = first_failure
        self.cleanup = cleanup
        self.cleanup_exceptions = list(cleanup_exceptions)


def _need(value, message):
    if not value:
        raise ValueError(message)


def _positive_int(value):
    return type(value) is int and value > 0


def _positive_time(value):
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def _error(value):
    # A bounded description accompanies the real exception retained as __cause__.
    text = str(value)
    return {"type": type(value).__name__, "message_prefix": text[:4096],
            "message_characters": len(text), "message_prefix_truncated": len(text) > 4096}


def _pin(body):
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def _json_bound(value):
    if value is None or type(value) is bool:
        return 5
    if type(value) in (int, float):
        _need(type(value) is int or math.isfinite(value), "finite JSON metadata")
        return len(str(value)) + 4
    if type(value) is str:
        return 2 + 12 * len(value)
    if type(value) in (list, tuple):
        return 2 + sum(_json_bound(x) + 1 for x in value)
    if type(value) is dict:
        _need(all(type(k) is str for k in value), "string JSON keys")
        return 2 + sum(_json_bound(k) + _json_bound(v) + 2 for k, v in value.items())
    raise ValueError("closed JSON metadata types")


def _encoded(value, budget):
    bound = _json_bound(value)
    budget.charge(write=bound)
    body = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    _need(len(body) <= bound, "metadata construction envelope")
    return body


def _decode(body):
    def pairs(rows):
        out = {}
        for key, value in rows:
            _need(key not in out, "duplicate Docker metadata key")
            out[key] = value
        return out
    return json.loads(body.decode("utf-8", "strict"), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


class _Binding:
    __slots__ = ("policy", "lifecycle", "cleanup", "reservation", "container_id",
                 "closed", "fatal", "busy", "sequence", "events", "cleanup_active",
                 "activated", "creation_attempted", "up_completed", "compose_identity")
    def __init__(self, policy, lifecycle, cleanup, reservation):
        self.policy = MappingProxyType(dict(policy, docker_env=MappingProxyType(dict(policy["docker_env"]))))
        self.lifecycle, self.cleanup = lifecycle, cleanup
        self.reservation = reservation
        self.container_id = None
        self.closed = self.fatal = self.busy = self.cleanup_active = False
        self.sequence = 0
        self.events = []
        self.activated = self.creation_attempted = self.up_completed = False
        self.compose_identity = None


def _binding(environment):
    _need(type(environment) is FigureDockerEnvironment, "exact fixed FigureDockerEnvironment")
    value = getattr(environment, "_figure_terminal_binding", None)
    _need(type(value) is _Binding, "transport configured before native setup")
    _need(value.policy["compose_project"] ==
          _sanitize_docker_compose_project_name(environment.session_id),
          "fixed Compose project matches environment")
    return value


def configure_environment_transport(environment, policy, budget):
    """Before native start: reserve finite lifecycle and independent cleanup costs.

    The trusted host must first admit executable/image/source/daemon/storage
    identities. This function cannot issue that external qualification.
    """
    _need(type(environment) is FigureDockerEnvironment, "exact fixed Docker class")
    _need(not hasattr(environment, "_figure_terminal_binding"), "one transport binding")
    _need(type(budget) is Budget and type(policy) is dict and set(policy) == _POLICY_KEYS,
          "exact budget and transport policy")
    # Own an independent policy snapshot before retaining nested lists/dicts.
    policy_body = _encoded(policy, budget)
    policy = _decode(policy_body)
    _need(type(policy["docker_path"]) is str and Path(policy["docker_path"]).is_absolute()
          and "\0" not in policy["docker_path"] and "\n" not in policy["docker_path"],
          "selected absolute Docker executable")
    _need(type(policy["docker_host"]) is str
          and policy["docker_host"].startswith("unix:///")
          and not any(x in policy["docker_host"] for x in ("\0", "\n", "\r")),
          "explicit selected local Unix Docker socket")
    _need(type(policy["compose_project"]) is str
          and re.fullmatch(r"[a-z0-9][a-z0-9_-]*", policy["compose_project"]),
          "selected Compose project")
    _need(policy["compose_project"] == _sanitize_docker_compose_project_name(environment.session_id),
          "project-to-environment join")
    _validate_fixed_policy(policy)
    _need(_path_text(environment.task_env_config.workdir)
          and any(not row["read_only"] and Path(environment.task_env_config.workdir).is_relative_to(Path(row["target"]))
                  for row in policy["mounts"]), "explicit workdir inside selected writable mount")
    env = policy["docker_env"]
    _need(type(env) is dict and set(env) <= {"PATH", "HOME", "DOCKER_CONFIG", "XDG_CONFIG_HOME"}
          and all(type(v) is str and not any(c in v for c in ("\0", "\n", "\r"))
                  for v in env.values()), "closed trusted Docker CLI environment")
    for key in ("lifecycle_read_bytes", "lifecycle_write_bytes",
                "cleanup_read_bytes", "cleanup_write_bytes", "metadata_output_cap"):
        _need(_positive_int(policy[key]), "positive transport byte operands")
    _need(_positive_time(policy["metadata_timeout_seconds"]), "positive metadata timeout")
    now = time.monotonic()
    for key in ("lifecycle_deadline_monotonic", "cleanup_deadline_monotonic"):
        _need(_positive_time(policy[key]) and policy[key] > now, "future absolute deadline")
    _need(policy["cleanup_deadline_monotonic"] >= policy["lifecycle_deadline_monotonic"],
          "cleanup deadline covers lifecycle")
    before = {"reads": budget.reads, "writes": budget.writes}
    budget.charge(read=policy["lifecycle_read_bytes"] + policy["cleanup_read_bytes"],
                  write=policy["lifecycle_write_bytes"] + policy["cleanup_write_bytes"])
    lifecycle = Budget(policy["lifecycle_read_bytes"], policy["lifecycle_write_bytes"],
                       policy["lifecycle_deadline_monotonic"] - now)
    cleanup = Budget(policy["cleanup_read_bytes"], policy["cleanup_write_bytes"],
                     policy["cleanup_deadline_monotonic"] - now)
    # Constructor clocks are deliberately replaced by the exact selected deadlines.
    lifecycle.deadline = policy["lifecycle_deadline_monotonic"]
    cleanup.deadline = policy["cleanup_deadline_monotonic"]
    reservation = {"before": before, "after": {"reads": budget.reads, "writes": budget.writes},
                   "lifecycle": {"read_bytes": lifecycle.read_limit, "write_bytes": lifecycle.write_limit},
                   "cleanup": {"read_bytes": cleanup.read_limit, "write_bytes": cleanup.write_limit},
                   "policy": _pin(policy_body), "refunded": False}
    environment._figure_terminal_binding = _Binding(policy, lifecycle, cleanup, reservation)
    result = _encoded(reservation, budget)
    budget.charge(read=len(result))
    return json.loads(result)


def bind_terminal_environment(environment, container_id):
    """AGENT_START: bind the exact ID after the host's real Docker/source inspection."""
    binding = _binding(environment)
    _need(not binding.activated and not binding.closed and not binding.fatal,
          "one initial container-ID binding")
    _need(type(container_id) is str and re.fullmatch(r"[a-f0-9]{64}", container_id),
          "full exact inspected container ID")
    _need(binding.container_id in (None, container_id), "actual startup-to-inspection ID join")
    binding.container_id = container_id
    binding.activated = True


def _record(binding, event, budget):
    # Retain only bounded metadata/pins here; full successful responses are returned.
    body = _encoded(event, budget)
    binding.events.append(event)
    return _pin(body)


def _remaining(budget, seconds):
    budget.charge()
    return min(float(seconds), budget.deadline - time.monotonic())


async def _reap_cli(process, budget):
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    remaining = budget.deadline - time.monotonic()
    _need(remaining > 0, "independent CLI cleanup deadline")
    await asyncio.wait_for(process.wait(), timeout=remaining)
    _need(type(process.returncode) is int, "actual terminal CLI reap")
    return {"pid": process.pid, "return_code": process.returncode, "reaped": True}


async def _process(binding, argv, env, *, timeout, cap, budget,
                   stdin_data=None, on_output=None, cleanup_operation=False):
    """Bounded byte pumps, with capacity charged before every read and append."""
    _need(_positive_time(timeout) and _positive_int(cap), "positive process operands")
    _need(type(budget) is Budget, "exact shared Budget class")
    end = time.monotonic() + _remaining(budget, timeout)
    process = None
    out, err = [], []
    before = {"reads": budget.reads, "writes": budget.writes}
    read_envelope = cap + 2 * _QUANTUM + 2
    budget.charge(read=read_envelope)
    counters = {"raw_output_bytes": 0, "read_reserved_bytes": read_envelope,
                "stdout_bytes": 0, "stderr_bytes": 0}
    tasks = []

    async def drain(stream, chunks, name):
        decoder = codecs.getincrementaldecoder("utf-8")("replace")
        while True:
            capacity = min(_QUANTUM, cap - counters["raw_output_bytes"] + 1)
            _need(capacity > 0, "output admission exhausted")
            budget.charge()
            block = await stream.read(capacity)
            if not block:
                if on_output is not None:
                    budget.charge(write=9)
                    tail = decoder.decode(b"", final=True)
                    if tail:
                        await on_output(tail, name)
                return
            counters["raw_output_bytes"] += len(block)
            _need(counters["raw_output_bytes"] <= read_envelope, "precharged stream envelope")
            counters[name + "_bytes"] += len(block)
            _need(counters["raw_output_bytes"] <= cap, "terminal raw output cap exceeded")
            budget.charge(write=len(block))
            chunks.append(block)
            if on_output is not None:
                budget.charge(write=3 * len(block))
                text = decoder.decode(block, final=False)
                if text:
                    await on_output(text, name)

    async def write_stdin():
        if stdin_data is None:
            return
        budget.charge(write=len(stdin_data))
        process.stdin.write(stdin_data)
        await process.stdin.drain()
        process.stdin.close()
        await process.stdin.wait_closed()

    try:
        process = await asyncio.create_subprocess_exec(
            *argv, env=env, stdin=asyncio.subprocess.PIPE if stdin_data is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, limit=_QUANTUM)
        tasks = [asyncio.create_task(drain(process.stdout, out, "stdout")),
                 asyncio.create_task(drain(process.stderr, err, "stderr")),
                 asyncio.create_task(write_stdin()), asyncio.create_task(process.wait())]
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=max(0.0, end - time.monotonic()))
        _need(type(process.returncode) is int and process.returncode >= 0,
              "natural Docker CLI completion required")
        budget.charge(write=counters["raw_output_bytes"])
        stdout, stderr = b"".join(out), b"".join(err)
        budget.charge()
        return {"stdout": stdout, "stderr": stderr, "return_code": process.returncode,
                "pid": process.pid, **counters,
                "charged": {"read": budget.reads - before["reads"], "write": budget.writes - before["writes"]}}
    except BaseException as first:
        cleanup_errors=[]
        for task in tasks:
            if not task.done():
                try:task.cancel()
                except BaseException as error:cleanup_errors.append(("task-cancel",error))
        kill_error=None
        if process is not None and process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            except BaseException as error:
                kill_error=error;cleanup_errors.append(("initial-cli-kill",error))
        retained=sum(map(len,out))+sum(map(len,err))
        cleanup = {"container": None, "cli": None,
                   "initial_kill_error":None if kill_error is None else _error(kill_error),
                   "task_join":None,
                   "transport_observation": {**counters,
                       "received_bytes_not_retained":counters["raw_output_bytes"]-retained,
                       "failed_raw_stream_bodies_retained":False,
                       "failure_stream_scope":"counts only; overrun/read prefixes may be unavailable, never called a complete raw capture",
                       "cli_pid": None if process is None else process.pid,
                       "charged": {"read": budget.reads - before["reads"],
                                   "write": budget.writes - before["writes"]}}}
        # Killing the Docker CLI does not kill in-container command descendants.
        # The independent cleanup reserve remains usable after budget exhaustion.
        if not cleanup_operation and binding.container_id is not None:
            try:
                cleanup["container"] = await _abort(binding, "transport_failure")
            except BaseException as failure:
                cleanup["container"] = {"error": _error(failure), "absence_verified": False}
                cleanup_errors.append(("container-abort",failure))
        if process is not None:
            try:
                cleanup["cli"] = await _reap_cli(process, binding.cleanup)
            except BaseException as failure:
                cleanup["cli"] = {"error": _error(failure), "reaped": False}
                cleanup_errors.append(("cli-reap",failure))
        # Consume cancellation outcomes without replacing the original failure.
        if tasks:
            try:
                remaining=binding.cleanup.deadline-time.monotonic()
                _need(remaining>0,"original cleanup deadline for task join")
                await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True),timeout=remaining)
                cleanup["task_join"]={"completed":True}
            except BaseException as error:
                cleanup_errors.append(("task-join",error))
                cleanup["task_join"]={"completed":False,"error":_error(error)}
        if cleanup_operation:
            raise
        binding.fatal = True
        raise TerminalArmFailure(_error(first), cleanup,cleanup_errors) from first


async def _metadata(binding, args, *, cleanup=True):
    policy = binding.policy
    budget = binding.cleanup if cleanup else binding.lifecycle
    result = await _process(
        binding, [policy["docker_path"], "--host", policy["docker_host"], *args],
        dict(policy["docker_env"]), timeout=policy["metadata_timeout_seconds"],
        cap=policy["metadata_output_cap"], budget=budget, cleanup_operation=cleanup)
    # Record the actual command and exact output pins, retaining no candidate files.
    row = {"argv_suffix": args, "return_code": result["return_code"],
           "stdout": _pin(result["stdout"]), "stderr": _pin(result["stderr"]),
           "read_reserved_bytes": result["read_reserved_bytes"],
           "raw_output_bytes": result["raw_output_bytes"], "cli_pid": result["pid"]}
    _record(binding, {"kind": "cleanup_metadata" if cleanup else "lifecycle_metadata", **row}, budget)
    return result, row


def _ids(body):
    values = body.decode("ascii", "strict").split()
    _need(all(re.fullmatch(r"[a-f0-9]{64}", x) for x in values), "full Docker IDs")
    _need(len(values) == len(set(values)), "unique Docker IDs")
    return values


async def _abort(binding, reason):
    _need(not binding.cleanup_active, "serialized fixed cleanup")
    _need(binding.container_id is not None, "exact inspected ID required before destructive cleanup")
    binding.cleanup_active = True
    observations = []
    try:
        container = binding.container_id
        project = binding.policy["compose_project"]
        inspection, row = await _metadata(binding, ["inspect", container])
        observations.append(row)
        if inspection["return_code"] == 0:
            value = _decode(inspection["stdout"])
            _need(type(value) is list and len(value) == 1, "one inspected owned container")
            current = value[0]
            _need(current["Id"] == container and
                  current["Config"]["Labels"]["com.docker.compose.project"] == project
                  and current["Config"]["Labels"]["com.docker.compose.service"] == "main",
                  "actual container-ID/project ownership before removal")
            removed, row = await _metadata(binding, ["rm", "-f", container])
            observations.append(row)
            _need(removed["return_code"] == 0, "exact owned container removal")
        else:
            # An inspect error alone does not establish absence. Successful exact-ID
            # and project queries below must independently establish it.
            _need(inspection["return_code"] == 1, "unknown container inspection outcome")
        by_id, row = await _metadata(binding, ["ps", "-aq", "--no-trunc", "--filter", "id=" + container])
        observations.append(row)
        by_project, row = await _metadata(binding, ["ps", "-aq", "--no-trunc", "--filter",
                                                   "label=com.docker.compose.project=" + project])
        observations.append(row)
        _need(by_id["return_code"] == by_project["return_code"] == 0
              and _ids(by_id["stdout"]) == [] and _ids(by_project["stdout"]) == [],
              "independent exact-ID and whole owned-project absence")
        binding.closed = True
        receipt = {"schema": "figure_terminal_container_absence_v1",
                   "container_id": container, "compose_project": project, "reason": reason,
                   "observations": observations, "volumes_deleted": False,
                   "exact_id_absent": True, "owned_project_containers_absent": True,
                   "provider_or_host_actor_absence_inferred": False}
        _record(binding, {"kind": "container_closure", "receipt": receipt}, binding.cleanup)
        return receipt
    finally:
        binding.cleanup_active = False


async def abort_terminal_container(environment, reason, budget=None):
    """Fixed metadata/removal route; never accepts caller host commands or callbacks.

    The optional budget is a compatibility operand only and is not used for cleanup:
    cleanup always consumes the independent reservation made before native start.
    """
    binding = _binding(environment)
    _need(type(reason) is str and 0 < len(reason) <= 256, "bounded cleanup reason")
    if budget is not None:
        _need(type(budget) is Budget, "exact budget compatibility operand")
    return await _abort(binding, reason)


async def inspect_container(environment):
    """Actual current complete Docker row; caller performs full runtime admission."""
    binding = _binding(environment)
    _need(binding.container_id is not None and not binding.closed, "created current container")
    observed, row = await _metadata(binding, ["inspect", binding.container_id], cleanup=False)
    _need(observed["return_code"] == 0, "current container inspect completed")
    value = _decode(observed["stdout"])
    _need(type(value) is list and len(value) == 1 and type(value[0]) is dict
          and value[0]["Id"] == binding.container_id
          and value[0]["Config"]["Labels"]["com.docker.compose.project"] == binding.policy["compose_project"]
          and value[0]["Config"]["Labels"]["com.docker.compose.service"] == "main",
          "actual current ID/project/main-service inspection")
    binding.lifecycle.charge(write=len(observed["stdout"]))
    _record(binding, {"kind": "activation_inspection", "container_id": binding.container_id,
                      "metadata": row}, binding.lifecycle)
    return value[0]


async def observe_container_absence(environment):
    """Acquire fresh exact-ID and project queries; never relay a supplied flag."""
    binding = _binding(environment)
    _need(binding.container_id is not None, "exact known container for absence observation")
    rows = []
    for args in (["ps", "-aq", "--no-trunc", "--filter", "id=" + binding.container_id],
                 ["ps", "-aq", "--no-trunc", "--filter",
                  "label=com.docker.compose.project=" + binding.policy["compose_project"]]):
        result, row = await _metadata(binding, args)
        _need(result["return_code"] == 0 and _ids(result["stdout"]) == [],
              "fresh exact-ID and project absence")
        rows.append(row)
    observation = {"schema": "figure_terminal_absence_observation_v1",
                   "container_id": binding.container_id,
                   "compose_project": binding.policy["compose_project"],
                   "docker_host": binding.policy["docker_host"], "queries": rows,
                   "exact_id_absent": True, "owned_project_containers_absent": True,
                   "provider_or_host_actor_absence_inferred": False}
    _record(binding, {"kind": "absence_observation", "observation": observation}, binding.cleanup)
    return observation



def _path_text(value):
    return (type(value) is str and Path(value).is_absolute()
            and not any(x in value for x in ("\0", "\n", "\r", "$"))
            and ".." not in Path(value).parts)


def _validate_fixed_policy(policy):
    _need(type(policy["image_id"]) is str
          and re.fullmatch(r"sha256:[a-f0-9]{64}", policy["image_id"]), "exact image ID")
    _need(type(policy["image_environment"]) is list
          and all(type(x) is str and "\0" not in x for x in policy["image_environment"]),
          "exact selected image environment")
    _need(type(policy["keepalive_argv"]) is list and policy["keepalive_argv"]
          and all(type(x) is str and x and not any(c in x for c in ("\0", "$"))
                  for x in policy["keepalive_argv"]), "explicit container keepalive argv")
    _need(type(policy["docker_cgroup_parent"]) is str and policy["docker_cgroup_parent"]
          and not any(x in policy["docker_cgroup_parent"] for x in ("\0", "\n", "\r", "$"))
          and ".." not in policy["docker_cgroup_parent"].split("/"), "selected Docker cgroup parent")
    _need(type(policy["container_user"]) is str
          and re.fullmatch(r"[1-9][0-9]*:[1-9][0-9]*", policy["container_user"]),
          "explicit nonroot container UID:GID")
    _need(_positive_time(policy["cpu_count"]), "positive CPU count")
    for key in ("memory_bytes", "memory_swap_bytes", "pids_limit", "tmpfs_bytes"):
        _need(_positive_int(policy[key]), "positive container resource operand")
    _need(policy["memory_swap_bytes"] >= policy["memory_bytes"], "bounded memory/swap relation")
    _need(type(policy["container_environment"]) is dict
          and all(type(k) is str and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k)
                  and type(v) is str and not any(c in v for c in ("\0", "$"))
                  for k, v in policy["container_environment"].items()), "literal selected container environment")
    mounts = policy["mounts"]
    _need(type(mounts) is list and mounts, "selected complete bind mounts")
    targets = []
    for row in mounts:
        _need(type(row) is dict and set(row) == {"type", "source", "target", "read_only", "bind"}
              and row["type"] == "bind" and type(row["read_only"]) is bool
              and row["bind"] == {"create_host_path": False}
              and _path_text(row["source"]) and _path_text(row["target"]),
              "closed existing-source bind mount")
        target = row["target"]
        _need(target not in ("/", "/proc", "/sys", "/dev", "/run", "/var/run")
              and not target.startswith(("/proc/", "/sys/", "/dev/"))
              and not target.endswith("docker.sock"), "no host-control mount target")
        targets.append(target)
    _need(len(set(targets)) == len(targets), "unique mount targets")
    _need(sum(row["target"] == "/inputs" and row["read_only"] for row in mounts) == 1
          and sum(row["target"] == "/inputs" for row in mounts) == 1, "one immutable selected input")
    descriptor = policy["compose_file"]
    _need(type(descriptor) is dict and set(descriptor) == {"path", "bytes", "sha256"}
          and _path_text(descriptor["path"]) and _positive_int(descriptor["bytes"])
          and type(descriptor["sha256"]) is str
          and re.fullmatch(r"[a-f0-9]{64}", descriptor["sha256"]), "exact generated Compose descriptor")


def _identity(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _same_json(left, right):
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return set(left) == set(right) and all(_same_json(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same_json(a, b) for a, b in zip(left, right))
    return left == right


def _selected_compose(binding):
    policy = binding.policy
    descriptor = policy["compose_file"]
    path = Path(descriptor["path"])
    _need(all(not p.is_symlink() for p in (path, *path.parents)), "no Compose aliases")
    first = path.lstat()
    _need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1
          and stat.S_IMODE(first.st_mode) in (0o400, 0o444)
          and first.st_size == descriptor["bytes"], "sealed ordinary generated Compose")
    binding.lifecycle.charge(read=descriptor["bytes"] + 1, write=descriptor["bytes"])
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        opened = os.fstat(fd)
        _need(_identity(first) == _identity(opened), "Compose open identity")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            raw = stream.read(descriptor["bytes"] + 1)
        _need(_identity(opened) == _identity(os.fstat(fd)) == _identity(path.lstat()),
              "Compose capture identity")
    finally:
        os.close(fd)
    _need(_pin(raw) == {k: descriptor[k] for k in ("bytes", "sha256")}, "generated Compose hash")
    expected = {"services": {"main": {
        "image": policy["image_id"], "entrypoint": [], "command": policy["keepalive_argv"],
        "network_mode": "none", "cgroup_parent": policy["docker_cgroup_parent"],
        "user": policy["container_user"], "cpus": policy["cpu_count"],
        "mem_limit": policy["memory_bytes"], "memswap_limit": policy["memory_swap_bytes"],
        "pids_limit": policy["pids_limit"], "read_only": True,
        "security_opt": ["no-new-privileges:true"], "cap_drop": ["ALL"], "init": True,
        "logging": {"driver": "none"}, "restart": "no",
        "volumes": policy["mounts"], "tmpfs": ["/tmp:rw,nosuid,nodev,size=" + str(policy["tmpfs_bytes"])],
        "environment": policy["container_environment"],
    }}}
    _need(_same_json(_decode(raw), expected), "closed complete one-service Compose schema")
    binding.compose_identity = _identity(first)
    return path


def _compose_still_sealed(binding):
    path = Path(binding.policy["compose_file"]["path"])
    _need(binding.compose_identity is not None and _identity(path.lstat()) == binding.compose_identity,
          "Compose remains sealed across native operation")


async def _owned_current_id(binding, *, cleanup):
    policy = binding.policy
    result, _ = await _metadata(binding, ["ps", "-aq", "--no-trunc", "--filter",
                                          "label=com.docker.compose.project=" + policy["compose_project"]],
                                cleanup=cleanup)
    _need(result["return_code"] == 0, "actual owned project listing")
    ids = _ids(result["stdout"])
    if not ids:
        return None
    _need(len(ids) == 1, "one owned main-service container")
    observed, _ = await _metadata(binding, ["inspect", ids[0]], cleanup=cleanup)
    _need(observed["return_code"] == 0, "actual created container inspection")
    rows = _decode(observed["stdout"])
    _need(type(rows) is list and len(rows) == 1, "one created container record")
    row = rows[0]
    _need(row["Id"] == ids[0] and row["Image"] == policy["image_id"]
          and row["Config"]["Labels"]["com.docker.compose.project"] == policy["compose_project"]
          and row["Config"]["Labels"]["com.docker.compose.service"] == "main",
          "actual image/project/service identity")
    return ids[0]

class FigureDockerEnvironment(DockerEnvironment):
    @classmethod
    def preflight(cls):
        # Source-only construction does not probe an ambient daemon. start() must
        # perform the actual configured checks after source/policy admission.
        return None

    @staticmethod
    def _requires_egress_control(*, startup_network_policy, phase_network_policies):
        return False

    @property
    def capabilities(self):
        return EnvironmentCapabilities(disable_internet=True, mounted=True,
                                       docker_compose=False, windows=False)

    def __init__(self, *args, **kwargs):
        _need(sys.platform == "linux", "selected Linux-only Docker transport")
        super().__init__(*args, **kwargs)
        _need(not self._is_windows_container and not self._keep_containers
              and not self.extra_docker_compose_paths and not self._environment_docker_compose_path.exists(),
              "no alternate task Compose/Windows/keep-container route")
        _need(self.network_policy.network_mode.value == "no-network"
              and all(x.network_mode.value == "no-network" for x in self._phase_network_policies),
              "fixed no-network phase policy")

    @property
    def _docker_compose_paths(self):
        return [_selected_compose(_binding(self))]

    def _compose_env_vars(self, include_os_env=True):
        return dict(_binding(self).policy["docker_env"])

    async def start(self, force_build):
        binding = _binding(self)
        policy = binding.policy
        _need(force_build is False and not binding.creation_attempted, "one prebuilt-only start")
        _need(self.task_env_config.docker_image == policy["image_id"], "task/image admission join")
        _selected_compose(binding)
        daemon, _ = await _metadata(binding, ["info", "--format", "{{.OSType}}"], cleanup=False)
        _need(daemon["return_code"] == 0 and daemon["stdout"].strip() == b"linux", "actual selected Linux daemon")
        image, _ = await _metadata(binding, ["image", "inspect", policy["image_id"]], cleanup=False)
        _need(image["return_code"] == 0, "selected pre-existing image; never pull/build")
        images = _decode(image["stdout"])
        _need(type(images) is list and len(images) == 1
              and images[0]["Id"] == policy["image_id"] and images[0]["Os"] == "linux"
              and (images[0]["Config"].get("Env") or []) == policy["image_environment"],
              "exact selected Linux image/environment")
        _need(not images[0]["Config"].get("Volumes"), "image implicit volumes refused")
        healthcheck = images[0]["Config"].get("Healthcheck")
        _need(healthcheck in (None, {}) or
              (type(healthcheck) is dict and healthcheck.get("Test") == ["NONE"]),
              "active or unknown image healthcheck refused")
        for args in (["ps", "-aq", "--no-trunc", "--filter", "label=com.docker.compose.project=" + policy["compose_project"]],
                     ["network", "ls", "-q", "--filter", "label=com.docker.compose.project=" + policy["compose_project"]]):
            observed, _ = await _metadata(binding, args, cleanup=False)
            _need(observed["return_code"] == 0 and not observed["stdout"].strip(), "fresh project before creation")
        binding.creation_attempted = True
        await self._run_docker_compose_command(["up", "--detach", "--wait", "--pull", "never"])
        binding.up_completed = True
        binding.container_id = await _owned_current_id(binding, cleanup=False)
        _need(binding.container_id is not None, "actual created container ID")
        _record(binding, {"kind": "container_created", "container_id": binding.container_id,
                          "compose_project": policy["compose_project"]}, binding.lifecycle)

    async def stop(self, delete):
        binding = _binding(self)
        _need(delete is True, "selected delete-container lifecycle")
        if binding.container_id is None:
            _need(binding.creation_attempted, "no container was started by this environment")
            binding.container_id = await _owned_current_id(binding, cleanup=True)
            _need(binding.container_id is not None, "creation outcome needs independent host recovery")
        await _abort(binding, "native_stop")

    async def _apply_network_policy(self, network_policy):
        _need(network_policy.network_mode.value == "no-network", "no network transition")

    async def prepare_logs_for_host(self):
        raise ValueError("automatic ownership/log traversal disabled")

    async def upload_file(self, *args, **kwargs):
        raise ValueError("automatic file upload disabled; selected mounts only")

    async def upload_dir(self, *args, **kwargs):
        raise ValueError("automatic directory upload disabled; selected mounts only")

    async def download_file(self, *args, **kwargs):
        raise ValueError("automatic file capture disabled; fixed parent collector only")

    async def download_dir(self, *args, **kwargs):
        raise ValueError("automatic directory capture disabled; fixed parent collector only")

    async def attach(self):
        raise ValueError("interactive host/ambient Docker attach disabled")

    async def service_exec(self, command, *, service=None, **kwargs):
        _need(service in (None, "main"), "no alternate service command route")
        return await self.exec(command, **kwargs)

    async def service_upload_file(self, *args, **kwargs):
        raise ValueError("all service upload routes disabled")

    async def service_upload_dir(self, *args, **kwargs):
        raise ValueError("all service upload routes disabled")

    async def service_download_file(self, *args, **kwargs):
        raise ValueError("all service capture routes disabled")

    async def service_download_dir(self, *args, **kwargs):
        raise ValueError("all service capture routes disabled")

    async def download_dir_with_exclusions(self, *args, **kwargs):
        raise ValueError("automatic filtered capture disabled")

    async def service_download_dir_with_exclusions(self, *args, **kwargs):
        raise ValueError("automatic service filtered capture disabled")

    async def _is_rootless_docker(self):
        raise ValueError("ambient daemon ownership probing disabled")

    def _validate_daemon_mode(self):
        raise ValueError("use fixed bounded selected-daemon start observation")

    async def _validate_image_os(self, image_name):
        raise ValueError("use fixed bounded selected-image start observation")

    async def stop_service(self, service):
        _need(service == "main", "one fixed main service")
        await self.stop(delete=True)

    async def _run_docker_compose_command(
        self, command, check=True, timeout_sec=None, stdin_data=None, on_output=None,
    ):
        binding = _binding(self)
        policy = binding.policy
        invocation = _ACTIVE.get()
        terminal = invocation is not None
        if terminal:
            _need(invocation["environment"] is self and command and command[0] == "exec"
                  and check is False and stdin_data is None, "fixed terminal exec route")
            _need(timeout_sec == invocation["timeout"], "terminal timeout binding")
            command = [command[0], "--no-TTY", *command[1:]]
            budget, timeout, cap = invocation["budget"], invocation["timeout"], invocation["max_output"]
        else:
            _need(not (binding.container_id is not None and command and command[0] == "exec"),
                  "after activation terminal exec requires the fixed metered API")
            budget, timeout, cap = binding.lifecycle, policy["metadata_timeout_seconds"], policy["metadata_output_cap"]
            if timeout_sec is not None:
                _need(_positive_time(timeout_sec), "positive lifecycle command timeout")
                timeout = min(timeout, timeout_sec)
        _need(type(command) is list and all(type(x) is str and "\0" not in x for x in command),
              "fixed compose argument vector")
        argv = [policy["docker_path"], "--host", policy["docker_host"], "compose",
                "--project-name", policy["compose_project"], "--project-directory",
                str(self.environment_dir.resolve().absolute())]
        for path in self._docker_compose_paths:
            argv.extend(["-f", str(path.resolve().absolute())])
        argv.extend(command)
        env = self._compose_env_vars(include_os_env=False)
        _need(not any(k in env for k in ("DOCKER_HOST", "DOCKER_CONTEXT")),
              "no compose endpoint override")
        env.update(policy["docker_env"])
        result = await _process(binding, argv, env, timeout=timeout, cap=cap, budget=budget,
                                stdin_data=stdin_data, on_output=on_output)
        _compose_still_sealed(binding)
        budget.charge(write=3 * result["raw_output_bytes"])
        public = ExecResult(stdout=result["stdout"].decode("utf-8", "replace") or None,
                            stderr=result["stderr"].decode("utf-8", "replace") or None,
                            return_code=result["return_code"])
        if terminal:
            invocation["transport_result"] = result
        if check and result["return_code"] != 0:
            raise RuntimeError("fixed Docker compose lifecycle command failed")
        return public


async def run_terminal(environment, command, timeout, max_output, budget):
    """One candidate command, only via the selected container's inherited exec ABI."""
    binding = _binding(environment)
    _need(not binding.fatal and not binding.closed and not binding.busy
          and binding.container_id is not None and binding.activated,
          "active serial owned container")
    _need(type(budget) is Budget, "exact shared terminal Budget")
    binding.busy = True
    token = None
    started = time.monotonic()
    binding.sequence += 1
    try:
        _need(type(command) is str and command and "\0" not in command, "nonempty container command")
        _need(_positive_time(timeout) and _positive_int(max_output), "positive selected terminal limits")
        budget.charge(write=4 * len(command))
        command_bytes = command.encode("utf-8", "strict")
        invocation = {"environment": environment, "budget": budget, "timeout": timeout,
                      "max_output": max_output, "transport_result": None}
        token = _ACTIVE.set(invocation)
        _need(not environment._persistent_env and not environment._exec_env_overlays.get(),
              "no persistent/scoped command environment overlay")
        result = await environment.exec(command, timeout_sec=timeout,
                                        user=binding.policy["container_user"])
        transport = invocation["transport_result"]
        _need(type(transport) is dict and result.return_code == transport["return_code"],
              "actual admitted transport result")
        stdout, stderr = transport["stdout"], transport["stderr"]
        budget.charge(write=4 * ((len(stdout) + 2) // 3 + (len(stderr) + 2) // 3))
        stdout_b64, stderr_b64 = base64.b64encode(stdout).decode("ascii"), base64.b64encode(stderr).decode("ascii")
        receipt = {"schema": "figure_terminal_completed_v1", "sequence": binding.sequence,
                   "command_sha256": hashlib.sha256(command_bytes).hexdigest(),
                   "return_code": result.return_code, "stdout": result.stdout or "",
                   "stderr": result.stderr or "", "stdout_b64": stdout_b64, "stderr_b64": stderr_b64,
                   "raw_output_bytes": transport["raw_output_bytes"],
                   "read_reserved_bytes": transport["read_reserved_bytes"],
                   "elapsed_seconds": time.monotonic() - started}
        _record(binding, {"kind": "terminal_completed", "sequence": binding.sequence,
                          "command_sha256": receipt["command_sha256"], "return_code": result.return_code,
                          "stdout": _pin(stdout), "stderr": _pin(stderr),
                          "raw_output_bytes": transport["raw_output_bytes"],
                          "read_reserved_bytes": transport["read_reserved_bytes"]}, budget)
        budget.charge()
        return receipt
    except BaseException as first:
        binding.fatal = True
        if isinstance(first, TerminalArmFailure):
            failure = first
        else:
            try:
                cleanup = await _abort(binding, "terminal_failure")
            except BaseException as cleanup_failure:
                cleanup = {"error": _error(cleanup_failure), "absence_verified": False}
            failure = TerminalArmFailure(_error(first), cleanup)
        try:
            _record(binding, {"kind": "terminal_failed", "sequence": binding.sequence,
                              "first_failure": failure.first_failure, "cleanup": failure.cleanup},
                    binding.cleanup)
        except BaseException:
            # A failed failure-record write cannot erase the real exception/receipt.
            pass
        if failure is first:
            raise
        raise failure from first
    finally:
        if token is not None:
            _ACTIVE.reset(token)
        binding.busy = False


def terminal_journal(environment, budget):
    """Return actual private observations; this does not manufacture qualification."""
    binding = _binding(environment)
    _need(type(budget) is Budget, "exact journal Budget")
    value = {"schema": "figure_terminal_journal_v1",
             "container_id": binding.container_id, "compose_project": binding.policy["compose_project"],
             "reservation": binding.reservation, "events": binding.events,
             "arm_fatal": binding.fatal, "container_closed_observed": binding.closed,
             "lifecycle_usage": {"reads": binding.lifecycle.reads, "writes": binding.lifecycle.writes},
             "cleanup_usage": {"reads": binding.cleanup.reads, "writes": binding.cleanup.writes},
             "native_or_transport_qualification_created": False}
    body = _encoded(value, budget)
    budget.charge(read=len(body))
    return json.loads(body)
