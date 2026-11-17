"""Pinned OCI launch and independent closure source; no authority at import time.

Production needs an external verifier for the complete Qualification manifest.
Docker and a kernel-accounting executable are required, never downloaded here.
The latter supplies primitive, loss-detecting, per-container logical I/O counters;
Docker block-I/O statistics are deliberately not substituted for those counters.
Tests inject RAM command transports. No receipt callback is accepted.
"""
from __future__ import annotations

import base64
from dataclasses import asdict, dataclass, field
import hashlib
import json
import os
from pathlib import PurePosixPath
import re
import secrets
import selectors
import signal
import stat
import subprocess
import time
from typing import Callable, Protocol


class ProcessError(RuntimeError):
    pass


def require(condition, message):
    if not condition:
        raise ProcessError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def hex_digest(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "Expected SHA-256")
    return value


def natural(value, name, zero=False):
    require(type(value) is int and value >= (0 if zero else 1), "Invalid " + name)
    return value


def safe_text(value, limit=1024):
    require(type(value) is str and 0 < len(value.encode()) <= limit
            and not any(ord(c) < 32 or ord(c) == 127 for c in value), "Unsafe text")
    return value


def safe_path(value):
    safe_text(value, 4096)
    p = PurePosixPath(value)
    require(p.is_absolute() and str(p) == value and ".." not in p.parts
            and "," not in value and ":" not in value, "Noncanonical absolute path")
    return value


def parse_json(data, cap):
    require(type(data) is bytes and len(data) <= cap, "JSON byte bound")
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "Duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda _: (_ for _ in ()).throw(ProcessError("Nonfinite JSON")))
    except (ValueError, UnicodeError) as exc:
        raise ProcessError("Malformed JSON") from exc


def hash_file(path, expected_bytes, *, maximum=1 << 34):
    """Read exact regular files with no symlink component and bounded reads.

    External mount immutability qualification is still needed: before/after
    hashes cannot exclude a malicious mutate/use/restore race by themselves.
    """
    safe_path(path); natural(expected_bytes, "file extent", zero=True)
    require(expected_bytes <= maximum, "File read bound")
    root_fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    fd = None
    try:
        for part in PurePosixPath(path).parts[1:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
            os.close(root_fd); root_fd = next_fd
        fd = os.open(PurePosixPath(path).name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_size == expected_bytes, "Exact regular file required")
        h = hashlib.sha256(); read = 0
        while read < expected_bytes:
            chunk = os.read(fd, min(65536, expected_bytes - read))
            require(bool(chunk), "Premature file EOF")
            read += len(chunk); h.update(chunk)
        require(os.read(fd, 1) == b"", "File grew during read")
        after = os.fstat(fd)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                "File changed during read")
        return h.hexdigest(), read
    finally:
        if fd is not None:
            os.close(fd)
        os.close(root_fd)


@dataclass(frozen=True)
class ExecutablePin:
    path: str
    sha256: str
    bytes: int

    def validate(self):
        safe_path(self.path); hex_digest(self.sha256); natural(self.bytes, "executable bytes")


@dataclass(frozen=True)
class Mount:
    role: str
    host_path: str
    container_path: str
    sha256: str
    bytes: int

    def validate(self):
        require(self.role in {"source", "input", "model", "request"}, "Unknown mount role")
        safe_path(self.host_path); safe_path(self.container_path)
        require(self.container_path.startswith("/paper020-view/"), "Mount outside exact view")
        hex_digest(self.sha256); natural(self.bytes, "mount bytes", zero=True)


@dataclass(frozen=True)
class Limits:
    memory_bytes: int
    scratch_bytes: int
    pids: int
    cpus: int
    stdout_bytes: int
    stderr_bytes: int
    trace_bytes: int
    read_bytes: int
    write_bytes: int
    retained_bytes: int
    live_bytes: int

    def validate(self):
        for name, value in asdict(self).items():
            natural(value, name)
        require(self.pids >= 2 and self.trace_bytes >= 4096, "Insufficient guardian/trace limit")
        require(all(v <= (1 << 63) - 1 for v in asdict(self).values()), "Finite platform resource bounds required")
        require(self.stdout_bytes * 4 + self.stderr_bytes <= self.memory_bytes,
                "Memory profile must cover complete encoded output copies and bounded logs")
        require(self.trace_bytes >= self.stdout_bytes + 4096, "Trace must cover complete encoded output plus envelope")
        require(self.scratch_bytes <= self.memory_bytes, "Scratch must fit memory bound")


REQUIRED_CAPABILITIES = (
    "immutable_image_and_runtime", "immutable_mount_files", "private_pid_namespace",
    "same_monotonic_clock", "network_none_enforced", "unprivileged_caps_enforced",
    "cgroup_memory_swap_pids_limits", "tmpfs_disk_bound", "lossless_logical_io_accounting",
    "owned_container_ids_not_reused", "guardian_pid1_subreaper", "bounded_daemon_logs",
    "guardian_worker_tamper_isolation",
)


@dataclass(frozen=True)
class Qualification:
    docker: ExecutablePin
    accountant: ExecutablePin
    daemon_socket: str
    image: str
    image_id: str
    python_path: str
    guardian: ExecutablePin
    worker: ExecutablePin
    environment_digest: str
    accounting_source_digest: str
    source_digest: str
    uid: int
    gid: int
    certificate_digest: str

    def manifest(self):
        for pin in (self.docker, self.accountant, self.guardian, self.worker):
            pin.validate()
        safe_path(self.daemon_socket); safe_path(self.python_path)
        require(re.fullmatch(r"[a-z0-9][a-z0-9./_:-]*@sha256:[0-9a-f]{64}", self.image), "Immutable OCI digest required")
        require(re.fullmatch(r"sha256:[0-9a-f]{64}", self.image_id), "Immutable OCI image ID required")
        for value in (self.environment_digest, self.accounting_source_digest, self.source_digest, self.certificate_digest):
            hex_digest(value)
        natural(self.uid, "nonroot uid"); natural(self.gid, "nonroot gid")
        return {"schema": "paper020_process_qualification_v1", **asdict(self),
                "required_capabilities": list(REQUIRED_CAPABILITIES)}


@dataclass(frozen=True)
class LaunchSpec:
    phase_id: str
    context: str
    binding_digest: str
    implementation_digest: str
    input_digest: str
    model_digest: str | None
    origin_ns: int
    deadline_ns: int
    argv: tuple[str, ...]
    mounts: tuple[Mount, ...]
    limits: Limits

    def validate(self, qualification):
        safe_text(self.phase_id, 256); safe_text(self.context, 256)
        for value in (self.binding_digest, self.implementation_digest, self.input_digest):
            hex_digest(value)
        if self.model_digest is not None:
            hex_digest(self.model_digest)
        natural(self.origin_ns, "origin"); natural(self.deadline_ns, "deadline")
        require(self.deadline_ns > self.origin_ns, "Original deadline must follow origin")
        require(type(self.argv) is tuple and 0 < len(self.argv) <= 64, "Bounded exact argv tuple required")
        for arg in self.argv:
            safe_text(arg, 4096)
        require(self.argv[:4] == (qualification.python_path, "-I", "-B", qualification.worker.path),
                "Worker differs from pinned isolated Python invocation")
        require(type(self.mounts) is tuple and 0 < len(self.mounts) <= 128, "Exact nonempty mount tuple required")
        for mount in self.mounts:
            require(type(mount) is Mount, "Typed mount required"); mount.validate()
        require(len({m.host_path for m in self.mounts}) == len(self.mounts)
                and len({m.container_path for m in self.mounts}) == len(self.mounts), "Repeated mount path")
        require(any(m.role == "source" for m in self.mounts) and any(m.role == "input" for m in self.mounts),
                "Source and input mount bindings required")
        if self.model_digest is not None:
            require(any(m.role == "model" for m in self.mounts), "Model mount missing")
        self.limits.validate()


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    stdout: bytes
    stderr: bytes
    returncode: int | None
    started_ns: int
    finished_ns: int
    timed_out: bool = False
    interrupted: bool = False
    truncated: bool = False
    forced: bool = False


class CommandTransport(Protocol):
    def run(self, argv: tuple[str, ...], *, origin_ns: int, deadline_ns: int,
            stdout_limit: int, stderr_limit: int) -> CommandResult: ...


class SubprocessCommandTransport:
    """Future real command entrypoint; construction requires external authority.

    No shell, ambient environment, daemon URL, cwd, inherited fd or numeric-group
    signal is accepted. Linux pidfds identify only the owned CLI child. An expired
    original deadline never creates an additional cleanup grace period.
    """
    def __init__(self, qualification, verify, *, clock=time.monotonic_ns, popen=subprocess.Popen):
        require(callable(verify) and verify(qualification.manifest()) is True,
                "External execution qualification required")
        self.qualification, self.clock, self.popen = qualification, clock, popen

    def run(self, argv, *, origin_ns, deadline_ns, stdout_limit, stderr_limit):
        start = self.clock()
        require(origin_ns <= start < deadline_ns, "Original command clock expired")
        require(type(argv) is tuple and argv and argv[0] in
                {self.qualification.docker.path, self.qualification.accountant.path}, "Unqualified command executable")
        for arg in argv:
            safe_text(arg, 131072)
        natural(stdout_limit, "stdout cap"); natural(stderr_limit, "stderr cap")
        pin = self.qualification.docker if argv[0] == self.qualification.docker.path else self.qualification.accountant
        require(hash_file(pin.path, pin.bytes)[0] == pin.sha256, "Command executable changed")
        # Pin verification is blocking work, charged to the ORIGINAL interval.
        # Equality refuses before dispatch; hashing cannot grant fresh time.
        before_spawn = self.clock()
        require(type(before_spawn) is int and origin_ns <= before_spawn < deadline_ns,
                "Original command clock expired after executable verification")
        proc = self.popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          shell=False, close_fds=True, cwd="/", env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        # Open before any wait/poll can reap this child. No reused integer PID is signalled.
        pidfd = None; sel = selectors.DefaultSelector(); out = bytearray(); err = bytearray()
        timed_out = interrupted = truncated = forced = False
        try:
            pidfd = os.pidfd_open(proc.pid, 0)
            for stream, target, cap in ((proc.stdout, out, stdout_limit), (proc.stderr, err, stderr_limit)):
                os.set_blocking(stream.fileno(), False); sel.register(stream, selectors.EVENT_READ, (target, cap))
            while sel.get_map() or proc.poll() is None:
                now = self.clock()
                if now >= deadline_ns:
                    timed_out = True; break
                for key, _ in sel.select(min(.02, (deadline_ns - now) / 1e9)):
                    target, cap = key.data
                    chunk = os.read(key.fileobj.fileno(), min(65536, max(1, cap - len(target) + 1)))
                    if not chunk:
                        sel.unregister(key.fileobj); continue
                    remaining = cap - len(target); target.extend(chunk[:remaining])
                    if len(chunk) > remaining:
                        truncated = True; break
                if truncated:
                    break
        except BaseException:
            interrupted = True
        finally:
            if timed_out or interrupted or truncated:
                forced = True
                if pidfd is not None:
                    try:
                        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
            sel.close()
            for stream in (proc.stdout, proc.stderr):
                if stream is not None:
                    stream.close()
            if pidfd is not None:
                os.close(pidfd)
        # Only a nonblocking final reap under the unchanged deadline. Unknown
        # survivors are represented by None, never a synthetic zero exit.
        code = proc.poll()
        finished = self.clock()
        return CommandResult(argv, bytes(out), bytes(err), code, start, finished,
                             timed_out, interrupted, truncated, forced)


@dataclass
class OwnedLaunch:
    nonce: str
    name: str
    spec: LaunchSpec
    qualification_digest: str
    container_id: str | None = None
    created_ns: int | None = None
    started_ns: int | None = None
    failures: list[str] = field(default_factory=list)
    commands: list[dict] = field(default_factory=list)
    inspection_read_bytes: int = 0
    closed: bool = False
    cleanup_requested: bool = False


@dataclass(frozen=True)
class ProcessSnapshot:
    container_id: str
    running: bool
    exit_code: int
    observed_ns: int
    inspect_digest: str


@dataclass(frozen=True)
class ClosureEvidence:
    phase_id: str
    binding_digest: str
    implementation_digest: str
    origin_ns: int
    deadline_ns: int
    finished_ns: int
    container_id: str
    nonce: str
    natural_complete: bool
    all_descendants_closed: bool
    exit_code: int | None
    input_digest: str
    model_digest: str | None
    source_digest: str
    payload: bytes
    payload_digest: str
    resources: dict
    view_isolation_verified: bool
    source_seal_unchanged: bool
    evidence_digests: dict
    failures: tuple[str, ...]

    def controller_fields(self):
        """Structural fields only; owner additionally joins actual typed artifacts.

        No protected-target absence assertion is invented here: exact view
        classification is the owner's admitted exposure policy responsibility.
        """
        require(self.natural_complete, "Failed closure has no admissible success receipt")
        return {"phase_id": self.phase_id, "binding_digest": self.binding_digest,
                "implementation_digest": self.implementation_digest, "origin_ns": self.origin_ns,
                "finished_ns": self.finished_ns, "natural_complete": self.natural_complete,
                "all_descendants_closed": self.all_descendants_closed, "exit_code": self.exit_code,
                "view_isolation_verified": self.view_isolation_verified,
                "source_seal_unchanged": self.source_seal_unchanged,
                **{k: self.resources[k] for k in ("read_bytes", "write_bytes", "retained_bytes", "live_bytes")}}


class DockerProcessAdapter:
    def __init__(self, qualification, transport, verify, *, clock=time.monotonic_ns,
                 file_hasher=hash_file, nonce_factory=lambda: secrets.token_hex(24)):
        require(type(qualification) is Qualification and callable(verify)
                and verify(qualification.manifest()) is True, "External immutable execution qualification required")
        self.q, self.transport, self.clock = qualification, transport, clock
        self.file_hasher, self.nonce_factory = file_hasher, nonce_factory
        self.owned = {}

    def _check_clock(self, handle):
        now = self.clock()
        require(type(now) is int and handle.spec.origin_ns <= now < handle.spec.deadline_ns,
                "Original strict deadline exceeded")
        return now

    def _command(self, handle, argv, *, stdout_limit=None):
        self._check_clock(handle)
        cap = stdout_limit or handle.spec.limits.trace_bytes
        result = self.transport.run(tuple(argv), origin_ns=handle.spec.origin_ns,
                                    deadline_ns=handle.spec.deadline_ns, stdout_limit=cap,
                                    stderr_limit=handle.spec.limits.stderr_bytes)
        require(type(result) is CommandResult, "Typed command evidence required")
        handle.commands.append({"argv_digest": digest(list(argv)), "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
                                "stdout_bytes": len(result.stdout), "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
                                "stderr_bytes": len(result.stderr), "returncode": result.returncode,
                                "started_ns": result.started_ns, "finished_ns": result.finished_ns,
                                "timed_out": result.timed_out, "interrupted": result.interrupted,
                                "truncated": result.truncated, "forced": result.forced})
        require(len(canonical(handle.commands)) <= handle.spec.limits.trace_bytes, "Cumulative command trace cap")
        if (result.argv != tuple(argv) or type(result.returncode) is not int or result.returncode != 0
                or any((result.timed_out, result.interrupted, result.truncated, result.forced))
                or not (handle.spec.origin_ns <= result.started_ns <= result.finished_ns < handle.spec.deadline_ns)
                or len(result.stdout) > cap or len(result.stderr) > handle.spec.limits.stderr_bytes):
            handle.failures.append("command_failed")
            raise ProcessError("Command failed, exceeded bounds or lacked natural original-clock completion")
        self._check_clock(handle)
        return result.stdout

    def _docker(self, *args):
        return (self.q.docker.path, "--host", "unix://" + self.q.daemon_socket, *args)

    def _verify_files(self, handle):
        for pin in (self.q.docker, self.q.accountant):
            got, size = self.file_hasher(pin.path, pin.bytes)
            handle.inspection_read_bytes += size
            require(got == pin.sha256 and size == pin.bytes, "Pinned host executable changed")
        for mount in handle.spec.mounts:
            got, size = self.file_hasher(mount.host_path, mount.bytes)
            handle.inspection_read_bytes += size
            require(got == mount.sha256 and size == mount.bytes, "Immutable view file changed")

    def _config(self, handle):
        spec = handle.spec
        return {"schema": "paper020_guardian_request_v1", "nonce": handle.nonce,
                "phase_id": spec.phase_id, "binding_digest": spec.binding_digest,
                "implementation_digest": spec.implementation_digest, "origin_ns": spec.origin_ns,
                "deadline_ns": spec.deadline_ns, "argv": list(spec.argv),
                "guardian_sha256": self.q.guardian.sha256, "worker_sha256": self.q.worker.sha256,
                "guardian_bytes": self.q.guardian.bytes, "worker_bytes": self.q.worker.bytes,
                "worker_path": self.q.worker.path, "python_path": self.q.python_path,
                "result_path": "/scratch/output/result.json",
                "mounts": [{"path": m.container_path, "bytes": m.bytes, "sha256": m.sha256, "role": m.role}
                           for m in spec.mounts],
                "input_digest": spec.input_digest, "model_digest": spec.model_digest,
                "source_digest": self.q.source_digest, "limits": asdict(spec.limits)}

    def launch(self, spec):
        spec.validate(self.q)
        nonce = self.nonce_factory()
        require(type(nonce) is str and re.fullmatch(r"[0-9a-f]{48}", nonce) and nonce not in self.owned,
                "Fresh owned nonce required")
        handle = OwnedLaunch(nonce, "paper020-" + nonce, spec, digest(self.q.manifest()))
        self.owned[nonce] = handle  # Custody remains even when creation/launch fails.
        try:
            self._check_clock(handle); self._verify_files(handle)
            image = parse_json(self._command(handle, self._docker("image", "inspect", self.q.image)), spec.limits.trace_bytes)
            require(type(image) is list and len(image) == 1 and image[0].get("Id") == self.q.image_id,
                    "Resolved image differs from immutable pin")
            require(not image[0].get("Config", {}).get("Volumes"), "Image-defined volumes forbidden")
            require(set(image[0].get("Config", {}).get("Env") or []) <= {"PATH=/usr/bin:/bin", "LC_ALL=C"},
                    "Image contains unqualified inherited environment")
            l = spec.limits
            config = base64.b64encode(canonical(self._config(handle))).decode("ascii")
            require(len(config) < 120000, "Guardian request exceeds argv cap")
            args = ["create", "--pull=never", "--name", handle.name, "--label", "paper020.nonce=" + nonce,
                    "--label", "paper020.binding=" + spec.binding_digest, "--network=none", "--ipc=none", "--pid=private",
                    "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--user", f"{self.q.uid}:{self.q.gid}",
                    "--pids-limit", str(l.pids), "--memory", str(l.memory_bytes), "--memory-swap", str(l.memory_bytes),
                    "--cpus", str(l.cpus), "--ulimit", "core=0:0", "--ulimit", "nofile=64:64",
                    "--tmpfs", f"/scratch:rw,noexec,nosuid,nodev,size={l.scratch_bytes}", "--workdir", "/scratch",
                    "--log-driver=json-file", "--log-opt", f"max-size={l.trace_bytes}", "--log-opt", "max-file=1",
                    "--entrypoint", self.q.python_path]
            for value in ("PATH=/usr/bin:/bin", "LC_ALL=C", "HOME=/scratch", "TMPDIR=/scratch",
                          "PYTHONDONTWRITEBYTECODE=1", "PYTHONNOUSERSITE=1"):
                args += ["--env", value]
            for m in spec.mounts:
                args += ["--mount", f"type=bind,src={m.host_path},dst={m.container_path},readonly,bind-propagation=rprivate"]
            args += [self.q.image, "-I", "-B", self.q.guardian.path, "--config-base64", config]
            raw_id = self._command(handle, self._docker(*args), stdout_limit=128).strip()
            require(re.fullmatch(rb"[0-9a-f]{64}", raw_id), "Full created container ID required")
            handle.container_id = raw_id.decode(); handle.created_ns = self._check_clock(handle)
            # Account registration is before start and is bound to this exact ID.
            ack = parse_json(self._command(handle, (self.q.accountant.path, "begin", "--container-id", handle.container_id,
                             "--nonce", nonce, "--origin-ns", str(spec.origin_ns), "--deadline-ns", str(spec.deadline_ns))), l.trace_bytes)
            require(ack == {"schema": "paper020_account_begin_v1", "container_id": handle.container_id,
                            "nonce": nonce, "registered": True}, "Accounting registration not acknowledged")
            self._inspect(handle)
            self._command(handle, self._docker("start", handle.container_id), stdout_limit=128)
            handle.started_ns = self._check_clock(handle)
            return handle
        except BaseException as exc:
            handle.failures.append("launch:" + type(exc).__name__)
            raise

    def _inspect(self, handle):
        require(handle.container_id is not None, "Created full container ID required")
        value = parse_json(self._command(handle, self._docker("inspect", handle.container_id)), handle.spec.limits.trace_bytes)
        require(type(value) is list and len(value) == 1 and type(value[0]) is dict, "Exact container inspect required")
        obj = value[0]; cfg = obj.get("Config", {}); host = obj.get("HostConfig", {})
        require(obj.get("Id") == handle.container_id and obj.get("Name") == "/" + handle.name
                and obj.get("Image") == self.q.image_id and cfg.get("Image") == self.q.image,
                "Container identity or image mismatch")
        require(cfg.get("Labels", {}).get("paper020.nonce") == handle.nonce
                and cfg.get("Labels", {}).get("paper020.binding") == handle.spec.binding_digest,
                "Owned nonce/binding label mismatch")
        require(cfg.get("User") == f"{self.q.uid}:{self.q.gid}" and cfg.get("WorkingDir") == "/scratch"
                and cfg.get("Entrypoint") == [self.q.python_path]
                and cfg.get("Cmd") == ["-I", "-B", self.q.guardian.path, "--config-base64", base64.b64encode(canonical(self._config(handle))).decode()],
                "Actual process argv or user mismatch")
        require(type(cfg.get("Env")) is list and len(cfg["Env"]) == 6 and set(cfg["Env"]) ==
                {"PATH=/usr/bin:/bin", "LC_ALL=C", "HOME=/scratch", "TMPDIR=/scratch",
                 "PYTHONDONTWRITEBYTECODE=1", "PYTHONNOUSERSITE=1"}, "Actual environment differs")
        l = handle.spec.limits
        require(host.get("NetworkMode") == "none" and host.get("PidMode") in ("", "private")
                and host.get("IpcMode") == "none" and host.get("ReadonlyRootfs") is True
                and host.get("Privileged") is False and not host.get("CapAdd")
                and set(host.get("CapDrop", [])) == {"ALL"}
                and "no-new-privileges" in host.get("SecurityOpt", [])
                and not host.get("Devices") and not host.get("DeviceRequests")
                and host.get("Memory") == l.memory_bytes and host.get("MemorySwap") == l.memory_bytes
                and host.get("PidsLimit") == l.pids and host.get("NanoCpus") == l.cpus * 1_000_000_000,
                "Actual isolation/resource settings differ")
        require(host.get("Tmpfs") == {"/scratch": f"rw,noexec,nosuid,nodev,size={l.scratch_bytes}"}, "Unbounded or extra tmpfs")
        require(host.get("LogConfig") == {"Type": "json-file", "Config": {"max-size": str(l.trace_bytes), "max-file": "1"}},
                "Unbounded daemon log configuration")
        observed = obj.get("Mounts")
        require(type(observed) is list and len(observed) == len(handle.spec.mounts), "Unexpected mounts")
        actual = {(m.get("Source"), m.get("Destination"), m.get("Type"), m.get("RW"), m.get("Propagation")) for m in observed}
        expected = {(m.host_path, m.container_path, "bind", False, "rprivate") for m in handle.spec.mounts}
        require(actual == expected, "Actual mounts differ from exact read-only view")
        return obj

    def monitor(self, handle):
        require(self.owned.get(handle.nonce) is handle and not handle.closed, "Unknown or closed launch handle")
        try:
            obj = self._inspect(handle); state = obj.get("State", {})
            require(type(state.get("Running")) is bool and type(state.get("ExitCode")) is int, "Malformed process state")
            return ProcessSnapshot(handle.container_id, state["Running"], state["ExitCode"], self._check_clock(handle), digest(obj))
        except BaseException as exc:
            handle.failures.append("monitor:" + type(exc).__name__); raise

    def cleanup(self, handle):
        """Explicit future cleanup of the full owned container ID; always failure.

        Cleanup outside the original deadline is refused. An operator may later
        authorize a separately accounted recovery; this handle stays failed.
        """
        require(self.owned.get(handle.nonce) is handle, "Unknown launch handle")
        handle.cleanup_requested = True; handle.failures.append("cleanup_requested")
        self._inspect(handle)  # Fresh exact ID/nonce/image join before removal.
        self._command(handle, self._docker("rm", "--force", handle.container_id), stdout_limit=128)


class IndependentDockerObserver(DockerProcessAdapter):
    """Separate command/file observation; never uses worker-reported success alone."""
    def __init__(self, qualification, transport, verify, launcher, **kwargs):
        require(transport is not launcher.transport, "Observer transport must be independently owned")
        super().__init__(qualification, transport, verify, **kwargs)
        require(digest(qualification.manifest()) == digest(launcher.q.manifest()), "Observer qualification mismatch")
        self.launcher = launcher

    def close(self, handle):
        require(self.launcher.owned.get(handle.nonce) is handle and not handle.closed,
                "Unknown or already-closed launch")
        resources = {k: None for k in ("read_bytes", "write_bytes", "retained_bytes", "live_bytes")}
        evidence = {}; payload = b""; code = None; descendants = False; source_ok = False; isolation = False
        try:
            require(not handle.failures and not handle.cleanup_requested, "Sticky earlier failure")
            self._check_clock(handle); self._verify_files(handle)
            before = self._inspect(handle); evidence["inspect_before"] = digest(before)
            # docker wait is independently executed, bounded by the ORIGINAL clock.
            wait = self._command(handle, self._docker("wait", handle.container_id), stdout_limit=32).strip()
            require(re.fullmatch(rb"[0-9]{1,3}", wait), "Exact bounded container wait status required")
            code = int(wait)
            require(code <= 255, "Invalid container exit status")
            if code != 0:
                handle.failures.append("container_nonzero")
            after = self._inspect(handle); evidence["inspect_after"] = digest(after)
            state = after.get("State", {})
            require(state.get("Running") is False and state.get("Dead") is False and state.get("OOMKilled") is False
                    and state.get("ExitCode") == code and type(state.get("ExitCode")) is int
                    and not state.get("Error") and after.get("RestartCount") == 0, "Abnormal final container state")
            isolation = True
            created = after.get("Created"); finished = state.get("FinishedAt")
            require(type(created) is str and type(finished) is str
                    and re.fullmatch(r"[0-9T:.Z+-]{20,40}", created)
                    and re.fullmatch(r"[0-9T:.Z+-]{20,40}", finished), "Runtime event timestamps missing")
            events_raw = self._command(handle, self._docker("events", "--since", created, "--until", finished,
                                      "--filter", "container=" + handle.container_id, "--format", "{{json .}}"))
            events = [parse_json(line, handle.spec.limits.trace_bytes) for line in events_raw.splitlines() if line]
            require(events and all(e.get("Actor", {}).get("ID") == handle.container_id for e in events), "Event custody mismatch")
            actions = [e.get("Action") for e in events]
            require(actions.count("start") == 1 and actions.count("die") == 1
                    and set(actions) <= {"create", "start", "die"}
                    and not set(actions) & {"kill", "oom", "destroy", "restart", "pause", "unpause", "stop"}
                    and actions.index("start") < actions.index("die"), "Missing or forced lifecycle events")
            dies = [e for e in events if e.get("Action") == "die"]
            require(dies[0].get("Actor", {}).get("Attributes", {}).get("exitCode") == str(code), "Die event/wait status mismatch")
            evidence["events"] = hashlib.sha256(events_raw).hexdigest()
            raw = self._command(handle, self._docker("logs", handle.container_id))
            terminal = parse_json(raw.strip(), handle.spec.limits.trace_bytes)
            require(type(terminal) is dict and terminal.get("schema") == "paper020_guardian_terminal_v1",
                    "One guardian terminal envelope required")
            joins = {"nonce": handle.nonce, "phase_id": handle.spec.phase_id, "binding_digest": handle.spec.binding_digest,
                     "implementation_digest": handle.spec.implementation_digest, "origin_ns": handle.spec.origin_ns,
                     "deadline_ns": handle.spec.deadline_ns, "input_digest": handle.spec.input_digest,
                     "model_digest": handle.spec.model_digest, "source_digest": self.q.source_digest}
            require(all(terminal.get(k) == v for k, v in joins.items()), "Guardian terminal binding mismatch")
            require(terminal.get("descendants_reaped") is True and type(terminal.get("exit_code")) is int
                    and type(terminal.get("failures")) is list
                    and all(type(item) is str for item in terminal["failures"]),
                    "Guardian descendant reaping required for payload custody")
            if not (terminal.get("natural_complete") is True and terminal.get("all_descendants_closed") is True
                    and terminal["exit_code"] == 0 and terminal["failures"] == []
                    and terminal.get("all_wait_statuses_zero") is True):
                handle.failures.append("guardian_non_natural_completion")
            require(type(terminal.get("finished_ns")) is int
                    and handle.spec.origin_ns <= terminal["finished_ns"] < handle.spec.deadline_ns,
                    "Guardian original clock closure missing")
            require(terminal.get("mounts_digest") == digest(self._config(handle)["mounts"])
                    and terminal.get("worker_sha256") == self.q.worker.sha256
                    and terminal.get("guardian_sha256") == self.q.guardian.sha256, "Actual source/executable bindings differ")
            require(type(terminal.get("output_bundle")) is dict, "Missing complete output bundle")
            candidate_payload = canonical(terminal["output_bundle"])
            require(len(candidate_payload) <= handle.spec.limits.stdout_bytes
                    and terminal.get("stdout_sha256") == hashlib.sha256(candidate_payload).hexdigest(), "Output digest/extent mismatch")
            bundle = terminal["output_bundle"]
            require(set(bundle) == {"manifest_base64", "blobs_base64"} and type(bundle["blobs_base64"]) is dict,
                    "Exact complete output bundle required")
            try:
                manifest_bytes = base64.b64decode(bundle["manifest_base64"], validate=True)
            except (ValueError, TypeError) as exc:
                raise ProcessError("Invalid result manifest base64") from exc
            require(terminal.get("result_manifest_sha256") == hashlib.sha256(manifest_bytes).hexdigest(),
                    "Actual result manifest seal mismatch")
            payload = candidate_payload
            evidence["guardian"] = hashlib.sha256(raw).hexdigest()
            counters_raw = self._command(handle, (self.q.accountant.path, "seal", "--container-id", handle.container_id,
                          "--nonce", handle.nonce, "--origin-ns", str(handle.spec.origin_ns),
                          "--deadline-ns", str(handle.spec.deadline_ns)))
            counters = parse_json(counters_raw, handle.spec.limits.trace_bytes)
            require(type(counters) is dict and counters.get("schema") == "paper020_kernel_counters_v1"
                    and counters.get("container_id") == handle.container_id and counters.get("nonce") == handle.nonce
                    and counters.get("origin_ns") == handle.spec.origin_ns and counters.get("deadline_ns") == handle.spec.deadline_ns,
                    "Kernel counter binding mismatch")
            require(counters.get("accounting_complete") is True and counters.get("all_tasks_exited") is True
                    and counters.get("trace_lost") is False and counters.get("forced_termination") is False
                    and type(counters.get("all_exit_statuses_zero")) is bool,
                    "Full lossless natural kernel accounting required")
            if not counters["all_exit_statuses_zero"]:
                handle.failures.append("kernel_observed_nonzero_exit")
            require(type(counters.get("coverage_started_ns")) is int and type(counters.get("sealed_at_ns")) is int
                    and 0 <= counters["coverage_started_ns"] <= handle.spec.origin_ns <= handle.created_ns
                    <= terminal["finished_ns"] <= counters["sealed_at_ns"] <= self._check_clock(handle),
                    "Accounting did not cover full container lifetime")
            hex_digest(counters.get("cgroup_identity"))
            for key in ("read_bytes", "write_bytes", "retained_bytes", "live_bytes", "memory_peak_bytes", "pids_peak", "cpu_ns"):
                natural(counters.get(key), key, zero=True)
                resources[key] = counters[key]
            # Host executable/view admission reads and command/log transport are
            # charged separately from (and in addition to) container logical I/O.
            resources["read_bytes"] += handle.inspection_read_bytes + sum(c["stdout_bytes"] + c["stderr_bytes"] for c in handle.commands)
            resources["write_bytes"] += len(payload)
            resources["retained_bytes"] += len(payload)
            resources["live_bytes"] += len(payload) + handle.spec.limits.trace_bytes
            for key in ("read_bytes", "write_bytes", "retained_bytes", "live_bytes"):
                require(resources[key] <= getattr(handle.spec.limits, key), "Complete observed resource limit exceeded: " + key)
            require(resources["memory_peak_bytes"] <= handle.spec.limits.memory_bytes
                    and resources["pids_peak"] <= handle.spec.limits.pids, "Kernel peak exceeds enforced limit")
            evidence["counters"] = hashlib.sha256(counters_raw).hexdigest()
            self._verify_files(handle); self._check_clock(handle)
            # The final custody reads are also included before declaring success.
            resources["read_bytes"] += sum(p.bytes for p in (self.q.docker, self.q.accountant)) + sum(m.bytes for m in handle.spec.mounts)
            require(resources["read_bytes"] <= handle.spec.limits.read_bytes, "Final custody read exceeds cap")
            source_ok = descendants = True
        except BaseException as exc:
            handle.failures.append("close:" + type(exc).__name__ + ":" + str(exc)[:256])
        finished = self.clock()
        if not (type(finished) is int and handle.spec.origin_ns <= finished < handle.spec.deadline_ns):
            handle.failures.append("final_original_deadline")
        handle.closed = True
        resources["observed_host_file_read_bytes"] = handle.inspection_read_bytes
        resources["observed_command_output_bytes"] = sum(c["stdout_bytes"] + c["stderr_bytes"] for c in handle.commands)
        resources["retained_command_trace_bytes"] = len(canonical(handle.commands))
        complete = not handle.failures and descendants and source_ok and isolation and code == 0
        return ClosureEvidence(handle.spec.phase_id, handle.spec.binding_digest, handle.spec.implementation_digest,
            handle.spec.origin_ns, handle.spec.deadline_ns, finished, handle.container_id or "", handle.nonce,
            complete, descendants and complete, code, handle.spec.input_digest, handle.spec.model_digest,
            self.q.source_digest, payload, hashlib.sha256(payload).hexdigest(), resources, isolation and complete,
            source_ok and complete, evidence, tuple(handle.failures))
