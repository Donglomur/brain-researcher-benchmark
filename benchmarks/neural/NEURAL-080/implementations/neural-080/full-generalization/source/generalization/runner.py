"""Future Linux process caller; importing this module launches nothing.

The operator must provision a Python runtime and source/tools as finite pinned
regular-file trees. No installation, host-runtime discovery or fallback occurs.
The two adaptation modes use this same caller and immutable Limits object.

This is source for an empirical host qualification gate, not evidence that any
host is qualified. RLIMIT_AS/CPU/FSIZE/NOFILE apply per process; RLIMIT_NPROC is
UID-scoped and its enforcement depends on credentials. Polling output size and
final output admission are not a hard filesystem write quota. Linux wait4 RSS
does not cover a complete process tree: bwrap can report the command's exit via
eventfd before reaping namespace init. Its RSS is not simultaneous aggregate
process-tree RSS. The operator must prevent other
host principals from mutating the provisioned trees while a case runs. Before
and after identity/hash checks detect observed changes, not adversarial ABA.
Filesystem calls can block in the kernel: every bounded phase uses the same
monotonic deadline, reserves cleanup time, and refuses late success; an external
supervisor and filesystem quota remain host qualification requirements for a
strict end-to-end hard wall/write guarantee. No authentic run is implied here.
"""

from __future__ import annotations

import dataclasses
import errno
import hashlib
import json
import math
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any


MODES = ("frozen_program", "case_adaptive_equal_inputs_tools_compute")
_HEX = re.compile(r"[0-9a-f]{64}\Z")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}\Z")
_MOUNT_PREFIXES = ("/runtime", "/source", "/tools", "/lib", "/lib64", "/usr/lib", "/usr/local/lib")
_CHUNK = 65536
# Captured official v0.11.0 C source, from GitHub's complete embedded rawLines.
# The source-view refInfo reports the commit below; the raw endpoint failed.
# This binds reviewed API semantics, not the operator's future compiled binary.
_BWRAP_API = {
    "requested_tag": "v0.11.0",
    "source_view_commit": "9ca3b05ec787acfb4b17bed37db5719fa777834f",
    "source_bytes_lf": 116178,
    "source_sha256_lf": "7e972f6193fe48ff046033be85c5d8988102978ac6176ba19ff9e02e0594f741",
    "representation": "complete GitHub embedded rawLines, joined LF plus final LF",
    "raw_endpoint_confirmation": False,
}


@dataclass(frozen=True)
class FilePin:
    """A relative regular-file member; values are observations, not permission."""

    path: str
    bytes: int
    sha256: str
    executable: bool = False


@dataclass(frozen=True)
class TreePin:
    host_path: str
    members: tuple[FilePin, ...]


@dataclass(frozen=True)
class ReadOnlyMount:
    tree: TreePin
    guest_path: str


@dataclass(frozen=True)
class ExecutablePin:
    host_path: str
    bytes: int
    sha256: str


@dataclass(frozen=True)
class OutputMember:
    """Finite basename allowlist selected by the outer-case caller."""

    name: str
    max_bytes: int


@dataclass(frozen=True)
class Limits:
    wall_seconds: float
    cleanup_seconds: float
    poll_seconds: float
    cpu_seconds: int
    address_space_bytes: int
    file_bytes: int
    tmpfs_bytes: int
    open_files: int
    processes: int
    stdout_bytes: int
    stderr_bytes: int
    output_bytes: int
    output_members: int
    intake_bytes: int
    intake_members: int
    report_bytes: int
    threads: int
    seed: int


@dataclass(frozen=True)
class RunConfig:
    bubblewrap: ExecutablePin
    python_guest_path: str
    mounts: tuple[ReadOnlyMount, ...]
    limits: Limits
    forbidden_host_roots: tuple[str, ...]


@dataclass(frozen=True)
class CaseRequest:
    case_id: str
    programme_id: str
    mode: str
    view: TreePin
    argv: tuple[str, ...]
    expected_outputs: tuple[OutputMember, ...]
    output_path: str
    log_path: str


class DeadlineExceeded(TimeoutError):
    pass


def _positive_int(value: Any, label: str) -> int:
    if type(value) is not int or value <= 0:
        raise ValueError(label + " must be a positive integer")
    return value


def _absolute(path: str) -> str:
    if not isinstance(path, str) or not path.startswith("/") or "\x00" in path:
        raise ValueError("an absolute POSIX path is required")
    parts = path.split("/")
    if any(part in ("", ".", "..") for part in parts[1:]):
        raise ValueError("paths must be normalized, non-root, and without trailing slash")
    return path


def _relative(path: str) -> str:
    if not isinstance(path, str) or not path or "\x00" in path:
        raise ValueError("invalid member path")
    if path.startswith("/") or any(p in ("", ".", "..") for p in path.split("/")):
        raise ValueError("member path is not a normalized relative path")
    return path


def _overlap(left: str, right: str) -> bool:
    return left == right or left.startswith(right + "/") or right.startswith(left + "/")


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def configuration_digest(config: RunConfig) -> str:
    """Bind the actual mounts, runtime executable and shared resource limits."""
    return hashlib.sha256(_canonical(dataclasses.asdict(config))).hexdigest()


def _identity(st: os.stat_result) -> tuple[int, ...]:
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_uid,
            st.st_gid, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


class _Custody:
    """Preserve the original exception object; cleanup never replaces it."""

    def __init__(self, start: float, limits: Limits):
        self.start = start
        self.limits = limits
        self.deadline = start + limits.wall_seconds
        self.work_deadline = self.deadline - limits.cleanup_seconds
        self.primary: BaseException | None = None
        self.traceback = None
        self.secondary: list[BaseException] = []
        self.actions: list[dict[str, Any]] = []
        self.fds: list[tuple[int, str]] = []
        self.intake_bytes = 0
        self.intake_members = 0
        self.stdout_seen = 0
        self.stderr_seen = 0
        self.log_bytes = 0
        self.output_read_bytes = 0
        self.output_peak_observed_bytes = 0
        self.output_peak_observed_members = 0
        self.partial_paths: list[str] = []

    def check(self, *, cleanup: bool = False) -> None:
        if time.monotonic() >= (self.deadline if cleanup else self.work_deadline):
            raise DeadlineExceeded("whole caller deadline (including intake/capture/cleanup/report)")

    def fail(self, error: BaseException) -> None:
        if self.primary is None:
            self.primary = error
            self.traceback = error.__traceback__
        else:
            self.secondary.append(error)

    def attempt(self, label: str, fn) -> Any:
        try:
            value = fn()
            self.actions.append({"action": label, "returned": True})
            return value
        except BaseException as error:
            self.fail(error)
            self.actions.append({"action": label, "returned": False,
                                 "exception_type": type(error).__name__, "exception": str(error)[:2000]})
            return None

    def retain_fd(self, fd: int, label: str) -> int:
        self.fds.append((fd, label))
        return fd

    def close_fd(self, fd: int) -> None:
        # Remove before closing: an interrupted close must not later close a reused FD.
        for i, (held, _) in enumerate(self.fds):
            if held == fd:
                self.fds.pop(i)
                break
        os.close(fd)

    def charge_intake(self, count: int) -> None:
        self.intake_bytes += count
        if self.intake_bytes > self.limits.intake_bytes:
            raise ValueError("intake byte cap exceeded")


def _open_dir(path: str, custody: _Custody) -> int:
    """Walk from / with no-follow on every component, retaining the final FD."""
    _absolute(path)
    custody.check()
    current = custody.retain_fd(os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC), "path root")
    for part in path.split("/")[1:]:
        custody.check()
        newer = custody.retain_fd(os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                         dir_fd=current), "directory " + path)
        custody.close_fd(current)
        current = newer
    custody.check()
    return current


def _open_member(root_fd: int, relative: str, custody: _Custody) -> int:
    _relative(relative)
    parts = relative.split("/")
    parent = custody.retain_fd(os.dup(root_fd), "member parent")
    for part in parts[:-1]:
        custody.check()
        newer = custody.retain_fd(os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                         dir_fd=parent), "member directory")
        custody.close_fd(parent)
        parent = newer
    custody.check()
    fd = custody.retain_fd(os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                                  dir_fd=parent), "member " + relative)
    custody.close_fd(parent)
    return fd


def _hash_fd(fd: int, expected: FilePin | ExecutablePin, custody: _Custody,
             *, output: bool = False, cleanup: bool = False) -> dict[str, Any]:
    custody.check(cleanup=cleanup)
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
        raise ValueError("member must be a singly linked regular file")
    if before.st_size != expected.bytes:
        raise ValueError("member byte count differs from descriptor")
    if not output and before.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        raise ValueError("provisioned member is writable by group or other")
    os.lseek(fd, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    observed = 0
    while True:
        custody.check(cleanup=cleanup)
        block = os.read(fd, min(_CHUNK, expected.bytes - observed + 1))
        if not block:
            break
        observed += len(block)
        if output:
            custody.output_read_bytes += len(block)
        else:
            custody.charge_intake(len(block))
        if observed > expected.bytes:
            raise ValueError("member grew during capture")
        digest.update(block)
    after = os.fstat(fd)
    if observed != expected.bytes or _identity(before) != _identity(after):
        raise ValueError("member changed during capture")
    actual = digest.hexdigest()
    if expected.sha256 and actual != expected.sha256:
        raise ValueError("member SHA256 differs from descriptor")
    custody.check(cleanup=cleanup)
    return {"bytes": observed, "sha256": actual, "identity": list(_identity(after))}


def _validate_pin(member: FilePin | ExecutablePin) -> None:
    if type(member.bytes) is not int or member.bytes < 0 or not _HEX.fullmatch(member.sha256):
        raise ValueError("invalid byte/hash descriptor")


def _tree_census(root_fd: int, tree: TreePin, custody: _Custody) -> dict[str, Any]:
    """Exact finite tree census, with directories derived from declared members."""
    expected = {member.path: member for member in tree.members}
    if len(expected) != len(tree.members) or not expected:
        raise ValueError("tree members must be nonempty and unique")
    directories = {""}
    for relative, member in expected.items():
        _relative(relative)
        _validate_pin(member)
        parts = relative.split("/")
        directories.update("/".join(parts[:i]) for i in range(1, len(parts)))
    if directories & expected.keys():
        raise ValueError("file/directory prefix conflict")
    observed: dict[str, Any] = {}
    pending = [""]
    while pending:
        relative_dir = pending.pop()
        fd = custody.retain_fd(os.dup(root_fd), "census root") if not relative_dir else _open_member(root_fd, relative_dir, custody)
        if not stat.S_ISDIR(os.fstat(fd).st_mode):
            raise ValueError("declared directory is not a directory")
        if os.fstat(fd).st_mode & (stat.S_IWGRP | stat.S_IWOTH):
            raise ValueError("provisioned directory is writable by group or other")
        with os.scandir(fd) as entries:
            for entry in entries:
                custody.check()
                relative = (relative_dir + "/" if relative_dir else "") + entry.name
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    if relative not in directories:
                        raise ValueError("undeclared directory in provisioned tree")
                    pending.append(relative)
                elif stat.S_ISREG(info.st_mode):
                    if relative not in expected or relative in observed:
                        raise ValueError("undeclared or repeated file in provisioned tree")
                    custody.intake_members += 1
                    if custody.intake_members > custody.limits.intake_members:
                        raise ValueError("intake member cap exceeded")
                    file_fd = _open_member(root_fd, relative, custody)
                    pin = expected[relative]
                    if pin.executable and not os.fstat(file_fd).st_mode & 0o111:
                        raise ValueError("declared executable lacks execute mode")
                    observed[relative] = _hash_fd(file_fd, pin, custody)
                    custody.close_fd(file_fd)
                else:
                    raise ValueError("symlink or special member in provisioned tree")
        custody.close_fd(fd)
    if set(observed) != set(expected):
        raise ValueError("missing provisioned member")
    return observed


def _new_dir(path: str, custody: _Custody) -> tuple[int, int]:
    _absolute(path)
    parent_path, name = path.rsplit("/", 1)
    if not parent_path:
        raise ValueError("fresh output/log directories cannot be immediate root children")
    parent = _open_dir(parent_path, custody)
    custody.check()
    os.mkdir(name, mode=0o700, dir_fd=parent)  # exclusive, never reuse or replace
    custody.partial_paths.append(path)
    fd = custody.retain_fd(os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                                  dir_fd=parent), "fresh directory " + path)
    custody.check()
    return fd, parent


def _validate(config: RunConfig, request: CaseRequest) -> None:
    if sys.platform != "linux":
        raise RuntimeError("runner requires an explicitly provisioned Linux host")
    if threading.current_thread() is not threading.main_thread() or threading.active_count() != 1:
        raise RuntimeError("pre-exec resource installation requires a single-threaded dedicated caller")
    if os.getuid() == 0 or os.getuid() != os.geteuid() or os.getgid() != os.getegid():
        raise RuntimeError("runner requires an ordinary unprivileged operator process")
    if signal.getsignal(signal.SIGCHLD) != signal.SIG_DFL:
        raise RuntimeError("dedicated caller must retain default SIGCHLD custody without another reaper")
    for attr in ("O_NOFOLLOW", "O_DIRECTORY", "O_CLOEXEC", "waitid", "WNOWAIT", "wait4"):
        if not hasattr(os, attr):
            raise RuntimeError("required Linux custody primitive unavailable: " + attr)
    if request.mode not in MODES or not _NAME.fullmatch(request.case_id) or not _NAME.fullmatch(request.programme_id):
        raise ValueError("invalid case/programme/mode identity")
    limits = config.limits
    if not all(isinstance(value, tuple) for value in (config.mounts, config.forbidden_host_roots,
                                                    request.view.members, request.expected_outputs)):
        raise ValueError("configuration and request collections must be immutable tuples")
    if any(not isinstance(mount.tree.members, tuple) for mount in config.mounts):
        raise ValueError("mount manifests must be immutable tuples")
    for field in dataclasses.fields(limits):
        value = getattr(limits, field.name)
        if field.name in ("wall_seconds", "cleanup_seconds", "poll_seconds"):
            if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                raise ValueError(field.name + " must be finite and positive")
        elif field.name == "seed":
            if type(value) is not int or not 0 <= value <= 4294967295:
                raise ValueError("seed must be uint32")
        else:
            _positive_int(value, field.name)
    if not limits.poll_seconds < limits.cleanup_seconds < limits.wall_seconds:
        raise ValueError("poll < reserved cleanup < whole wall limit is required")
    if limits.open_files < 32 or limits.report_bytes < 4096:
        raise ValueError("insufficient explicit FD/report limits")
    _absolute(config.bubblewrap.host_path)
    _validate_pin(config.bubblewrap)
    python_path = _absolute(config.python_guest_path)
    if not config.mounts or not config.forbidden_host_roots:
        raise ValueError("explicit runtime/source mounts and private exclusion roots are required")
    guest_paths = []
    host_paths = [_absolute(request.view.host_path)]
    python_found = False
    for mount in config.mounts:
        guest = _absolute(mount.guest_path)
        if not any(guest == prefix or guest.startswith(prefix + "/") for prefix in _MOUNT_PREFIXES):
            raise ValueError("runtime/source/tool or explicit loader-library mount target is outside its allowed prefixes")
        if any(_overlap(guest, previous) for previous in guest_paths):
            raise ValueError("overlapping guest mounts")
        guest_paths.append(guest)
        host_paths.append(_absolute(mount.tree.host_path))
        for member in mount.tree.members:
            if guest + "/" + member.path == python_path and member.executable:
                python_found = True
    if not python_found:
        raise ValueError("Python executable must be an exact executable member of a pinned mount")
    if not request.argv or request.argv[0] != python_path:
        raise ValueError("argv must invoke exactly the pinned sandbox Python")
    if not isinstance(request.argv, tuple) or any(not isinstance(a, str) or "\x00" in a for a in request.argv):
        raise ValueError("argv must be a finite tuple of NUL-free strings")
    if len(request.argv) > 1024 or sum(len(a.encode("utf-8")) for a in request.argv) > 32768:
        raise ValueError("argv cap exceeded")
    outputs = {_absolute(request.output_path), _absolute(request.log_path)}
    if len(outputs) != 2 or _overlap(request.output_path, request.log_path):
        raise ValueError("output and log roots overlap")
    for i, path in enumerate(host_paths):
        if any(_overlap(path, other) for other in host_paths[:i]):
            raise ValueError("overlapping view/runtime/source host trees")
        if any(_overlap(path, out) for out in outputs):
            raise ValueError("input and output/log roots overlap")
    for forbidden in config.forbidden_host_roots:
        _absolute(forbidden)
        if any(_overlap(forbidden, path) for path in host_paths + list(outputs) + [config.bubblewrap.host_path]):
            raise ValueError("private source metadata/pool/binding overlaps a mount or output")
    if any(_overlap(config.bubblewrap.host_path, out) for out in outputs):
        raise ValueError("bubblewrap executable overlaps output")
    names = set()
    if not request.expected_outputs or len(request.expected_outputs) > limits.output_members:
        raise ValueError("finite nonempty output allowlist exceeds member cap")
    for output in request.expected_outputs:
        if not _NAME.fullmatch(output.name) or output.name in names:
            raise ValueError("output allowlist requires unique simple basenames")
        names.add(output.name)
        _positive_int(output.max_bytes, "output member cap")
        if output.max_bytes > min(limits.file_bytes, limits.output_bytes):
            raise ValueError("output member cap exceeds configured per-file/aggregate limit")


def _output_census(fd: int, request: CaseRequest, custody: _Custody,
                   *, final: bool = False, cleanup: bool = False) -> dict[str, os.stat_result]:
    expected = {m.name: m for m in request.expected_outputs}
    result = {}
    total = 0
    with os.scandir(fd) as entries:
        for entry in entries:
            custody.check(cleanup=cleanup)
            if entry.name not in expected:
                raise ValueError("unexpected candidate output member: " + entry.name)
            info = entry.stat(follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError("candidate output is not a singly linked regular file")
            if info.st_size > expected[entry.name].max_bytes:
                raise ValueError("candidate output member exceeds its admission cap")
            result[entry.name] = info
            total += info.st_size
            custody.output_peak_observed_bytes = max(custody.output_peak_observed_bytes, total)
            custody.output_peak_observed_members = max(custody.output_peak_observed_members, len(result))
            if total > custody.limits.output_bytes or len(result) > custody.limits.output_members:
                raise ValueError("candidate aggregate output admission cap exceeded")
    if final and set(result) != set(expected):
        raise ValueError("candidate output set is incomplete")
    return result


def _single_native_thread() -> None:
    # Python's threading.active_count() does not count BLAS/native worker threads.
    with os.scandir("/proc/self/task") as tasks:
        count = 0
        for _ in tasks:
            count += 1
            if count > 1:
                raise RuntimeError("pre-exec caller must have exactly one OS thread")
    if count != 1:
        raise RuntimeError("cannot establish the caller's OS-thread census")


def _preexec_limits(limits: Limits, bwrap_fd: int):
    # Invoked only by subprocess in the future dedicated Linux caller.
    import resource

    selected = ((resource.RLIMIT_CPU, limits.cpu_seconds),
                (resource.RLIMIT_AS, limits.address_space_bytes),
                (resource.RLIMIT_FSIZE, limits.file_bytes),
                (resource.RLIMIT_NOFILE, limits.open_files),
                (resource.RLIMIT_NPROC, limits.processes),
                (resource.RLIMIT_CORE, 0))
    for which, value in selected:
        resource.setrlimit(which, (value, value))
    # The Linux ELF exec consumes /proc/self/fd/N before close-on-exec runs.
    # Keep mount FDs for bwrap's --*-bind-fd operations, which consume them;
    # the executable FD must not leak into the candidate process.
    os.set_inheritable(bwrap_fd, False)
    os.umask(0o077)


def _sandbox_argv(config: RunConfig, request: CaseRequest, bwrap_fd: int,
                  view_fd: int, output_fd: int, mount_fds: tuple[int, ...]) -> tuple[str, ...]:
    """Bind only flags inspected in the pinned ordinary official C source.

    --unshare-all alone uses user/cgroup TRY (1876--1884), so require both
    explicitly (1887--1889,1911--1913,3065--3091). --*-bind-fd consumes each
    FD and compares source/mount inode+device (2001--2023,1239--1276).
    --remount-ro is nonrecursive (1322--1324), allowing only the explicit
    /output and size-limited /tmp regular-file storage mounts to stay writable.
    --disable-userns verifies its effect (3445--3491); --cap-drop ALL is
    parsed at2629--2639. Parent-death SIGKILL is installed in monitor,
    namespace init and command (380--387,623--624,3180--3181,3597--3598).
    No --new-session is used: the host caller owns the original process group.
    """
    argv = ["/proc/self/fd/" + str(bwrap_fd),
            "--unshare-all", "--unshare-user", "--unshare-cgroup",
            "--die-with-parent", "--disable-userns", "--cap-drop", "ALL",
            "--clearenv"]
    environment = {
        "PATH": "/runtime/bin", "LANG": "C", "LC_ALL": "C",
        "TMPDIR": "/tmp", "XDG_CACHE_HOME": "/tmp/cache",
        "PYTHONHASHSEED": str(config.limits.seed), "PYTHONNOUSERSITE": "1",
        "PYTHONDONTWRITEBYTECODE": "1", "NEURAL080_SEED": str(config.limits.seed),
        "NEURAL080_THREADS": str(config.limits.threads), "NEURAL080_MODE": request.mode,
    }
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                 "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS", "BLIS_NUM_THREADS"):
        environment[name] = str(config.limits.threads)
    for name, value in sorted(environment.items()):
        argv.extend(("--setenv", name, value))
    for mount, fd in zip(config.mounts, mount_fds, strict=True):
        argv.extend(("--ro-bind-fd", str(fd), mount.guest_path))
    argv.extend(("--ro-bind-fd", str(view_fd), "/view",
                 "--bind-fd", str(output_fd), "/output",
                 "--size", str(config.limits.tmpfs_bytes), "--tmpfs", "/tmp",
                 "--proc", "/proc", "--remount-ro", "/proc",
                 "--dev", "/dev", "--remount-ro", "/dev/pts", "--remount-ro", "/dev",
                 "--remount-ro", "/", "--chdir", "/output"))
    # The first command token is an absolute path, so bwrap's parser ends its
    # option scan (2745--2751); candidate tokens cannot add bwrap options.
    argv.extend(request.argv)
    return tuple(argv)


def _write_all(fd: int, body: bytes, custody: _Custody, *, cleanup: bool = False) -> None:
    position = 0
    while position < len(body):
        custody.check(cleanup=cleanup)
        written = os.write(fd, body[position:])
        if written <= 0:
            raise OSError("zero progress writing runner-owned file")
        position += written
        custody.log_bytes += written
    custody.check(cleanup=cleanup)


def _usage(value) -> dict[str, Any]:
    return {"user_seconds": value.ru_utime, "system_seconds": value.ru_stime,
            "maxrss_linux_kib": value.ru_maxrss, "minor_faults": value.ru_minflt,
            "major_faults": value.ru_majflt, "input_blocks": value.ru_inblock,
            "output_blocks": value.ru_oublock, "voluntary_switches": value.ru_nvcsw,
            "involuntary_switches": value.ru_nivcsw}


def run_case(config: RunConfig, request: CaseRequest) -> dict[str, Any]:
    """Run one future isolated case; raise the raw first failure with custody.

    On a failure the original exception has ``runner_observation`` attached
    when its type permits attributes. Partial output/log directories are retained
    and never silently deleted. The caller owns their later explicit disposition.
    stdout/stderr are raw bounded files, not trusted protocol or authority.
    """
    start = time.monotonic()
    # Check the values needed for deadline arithmetic before constructing custody.
    for value in (config.limits.wall_seconds, config.limits.cleanup_seconds):
        if type(value) not in (float, int) or not math.isfinite(value) or value <= 0:
            raise ValueError("finite positive wall/cleanup limits are required")
    custody = _Custody(start, config.limits)
    process = None
    selector = None
    output_fd = log_fd = bwrap_fd = None
    wait_observed = None
    usage = None
    returncode = None
    group_killed = False
    reaped = False
    input_trees: list[tuple[TreePin, int, dict[str, Any]]] = []
    acquired_paths = custody.partial_paths
    outputs: dict[str, Any] = {}
    argv: tuple[str, ...] = ()
    log_fds: dict[str, int] = {}
    report: dict[str, Any] = {"case_id": request.case_id, "programme_id": request.programme_id,
                              "mode": request.mode, "partial_paths": acquired_paths}

    def kill_group() -> None:
        nonlocal group_killed
        if process is None or reaped or group_killed:
            return
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        group_killed = True

    def reap() -> None:
        nonlocal reaped, usage, returncode
        if process is None or reaped:
            return
        while True:
            custody.check(cleanup=True)
            got, status, observed_usage = os.wait4(process.pid, os.WNOHANG)
            if got == process.pid:
                reaped = True
                returncode = os.waitstatus_to_exitcode(status)
                process.returncode = returncode
                usage = _usage(observed_usage)
                return
            time.sleep(min(0.01, max(0.0, custody.deadline - time.monotonic())))

    try:
        _validate(config, request)
        custody.check()
        report["configuration_sha256"] = configuration_digest(config)
        report["request_sha256"] = hashlib.sha256(_canonical(dataclasses.asdict(request))).hexdigest()
        report["view_manifest_sha256"] = hashlib.sha256(_canonical(dataclasses.asdict(request.view))).hexdigest()
        report["programme_argv"] = list(request.argv)
        report["limits"] = dataclasses.asdict(config.limits)
        report["reviewed_bubblewrap_api"] = dict(_BWRAP_API)
        parent_path, name = config.bubblewrap.host_path.rsplit("/", 1)
        parent_fd = _open_dir(parent_path, custody)
        bwrap_fd = _open_member(parent_fd, name, custody)
        custody.close_fd(parent_fd)
        info = os.fstat(bwrap_fd)
        if not info.st_mode & 0o111 or info.st_mode & (stat.S_ISUID | stat.S_ISGID):
            raise ValueError("bubblewrap must be executable and not setuid/setgid")
        custody.intake_members += 1
        report["bubblewrap_capture"] = _hash_fd(bwrap_fd, config.bubblewrap, custody)
        os.lseek(bwrap_fd, 0, os.SEEK_SET)
        elf_magic = os.read(bwrap_fd, 4)
        custody.charge_intake(len(elf_magic))
        if elf_magic != b"\x7fELF":
            raise ValueError("the selected bubblewrap must be a Linux ELF executable")
        for tree in (request.view,) + tuple(mount.tree for mount in config.mounts):
            root_fd = _open_dir(tree.host_path, custody)
            observed = _tree_census(root_fd, tree, custody)
            input_trees.append((tree, root_fd, observed))
            report.setdefault("captured_trees", []).append({
                "host_path": tree.host_path, "members": len(observed),
                "bytes": sum(item["bytes"] for item in observed.values()),
                "observed_census_sha256": hashlib.sha256(_canonical(observed)).hexdigest(),
            })
        view_fd = input_trees[0][1]
        output_fd, _ = _new_dir(request.output_path, custody)
        log_fd, _ = _new_dir(request.log_path, custody)
        report["directory_identities"] = {
            "output": list(_identity(os.fstat(output_fd))),
            "logs": list(_identity(os.fstat(log_fd))),
        }
        for label in ("stdout", "stderr"):
            fd = custody.retain_fd(os.open(label + ".bin", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                                          0o600, dir_fd=log_fd), label + " log")
            log_fds[label] = fd
        mount_fds = tuple(item[1] for item in input_trees[1:])
        argv = _sandbox_argv(config, request, bwrap_fd, view_fd, output_fd, mount_fds)
        inherited = (bwrap_fd, view_fd, output_fd) + mount_fds
        if len(inherited) + 32 > config.limits.open_files:
            raise ValueError("FD limit cannot accommodate explicit inherited mount descriptors")
        _single_native_thread()
        custody.check()
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, close_fds=True, pass_fds=inherited,
                                   shell=False, cwd="/", env={}, start_new_session=True,
                                   preexec_fn=lambda: _preexec_limits(config.limits, bwrap_fd))
        report["pid"] = process.pid
        report["process_group"] = process.pid
        custody.check()
        selector = selectors.DefaultSelector()
        for label, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
            if pipe is None:
                raise RuntimeError("requested subprocess pipe was not acquired")
            os.set_blocking(pipe.fileno(), False)
            selector.register(pipe, selectors.EVENT_READ, label)
        while True:
            custody.check()
            _output_census(output_fd, request, custody)
            if wait_observed is None:
                wait_observed = os.waitid(os.P_PID, process.pid, os.WEXITED | os.WNOHANG | os.WNOWAIT)
                if wait_observed is not None:
                    # Retain the zombie until its process group is signalled.
                    kill_group()
            if wait_observed is not None and not selector.get_map():
                break
            events = selector.select(min(config.limits.poll_seconds, max(0.0, custody.work_deadline - time.monotonic())))
            for key, _ in events:
                label = key.data
                cap = config.limits.stdout_bytes if label == "stdout" else config.limits.stderr_bytes
                seen = custody.stdout_seen if label == "stdout" else custody.stderr_seen
                try:
                    block = os.read(key.fd, min(_CHUNK, max(1, cap - seen + 1)))
                except BlockingIOError:
                    continue
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                if label == "stdout":
                    custody.stdout_seen += len(block)
                else:
                    custody.stderr_seen += len(block)
                # Keep at most cap bytes, while observing one excess byte.
                allowed = block[:max(0, cap - seen)]
                _write_all(log_fds[label], allowed, custody)
                if seen + len(block) > cap:
                    raise ValueError(label + " capture cap exceeded")
        reap()
        if returncode != 0:
            raise subprocess.CalledProcessError(returncode, argv)
        census = _output_census(output_fd, request, custody, final=True)
        for name in sorted(census):
            fd = _open_member(output_fd, name, custody)
            info = census[name]
            # Blank hash is intentional only for newly observed candidate bytes.
            observed = _hash_fd(fd, FilePin(name, info.st_size, ""), custody, output=True)
            if observed["identity"] != list(_identity(info)):
                raise ValueError("output changed between final census and capture")
            outputs[name] = observed
            custody.close_fd(fd)
        _output_census(output_fd, request, custody, final=True)
        # Rehash the exact pinned source trees and executable after the process.
        for tree, root_fd, initial in input_trees:
            if _tree_census(root_fd, tree, custody) != initial:
                raise ValueError("input tree identity changed during case")
        if _hash_fd(bwrap_fd, config.bubblewrap, custody) != report["bubblewrap_capture"]:
            raise ValueError("bubblewrap executable changed during case")
        custody.check()
    except BaseException as error:
        custody.fail(error)
    finally:
        # No action below is conditional on an earlier cleanup action succeeding.
        custody.attempt("kill owned process group", kill_group)
        custody.attempt("reap owned process", reap)
        if process is not None:
            for label, pipe in (("stdout", process.stdout), ("stderr", process.stderr)):
                if pipe is not None:
                    custody.attempt("close " + label + " pipe", pipe.close)
        if selector is not None:
            custody.attempt("close selector", selector.close)
        # Keep log-directory FD for the final bounded operator-only report.
        for fd, label in list(reversed(custody.fds)):
            if fd != log_fd:
                custody.attempt("close " + label, lambda fd=fd: custody.close_fd(fd))

    report.update({
        "report_stage": "observations before final report write/close and final deadline check",
        "returncode": returncode, "process_reaped": reaped,
        "process_group_kill_attempt_completed": group_killed,
        "wait4_observation": usage, "outputs": outputs,
        "observed": {"intake_bytes": custody.intake_bytes,
                     "intake_members_including_rechecks": custody.intake_members,
                     "stdout_bytes_seen": custody.stdout_seen, "stderr_bytes_seen": custody.stderr_seen,
                     "log_bytes_written_before_report": custody.log_bytes,
                     "output_bytes_read": custody.output_read_bytes,
                     "peak_polled_output_bytes": custody.output_peak_observed_bytes,
                     "peak_polled_output_members": custody.output_peak_observed_members},
        "cleanup_actions": custody.actions,
        "primary_failure": None if custody.primary is None else {
            "type": type(custody.primary).__name__, "message": str(custody.primary)[:2000]},
        "secondary_failures": [{"type": type(e).__name__, "message": str(e)[:2000]} for e in custody.secondary],
        "elapsed_before_report_seconds": time.monotonic() - start,
        "limitations": [
            "No host/native qualification or scientific result is asserted by this source caller.",
            "Per-process rlimits and UID-scoped NPROC are not aggregate process-tree resource quotas.",
            "Polled/final output admission is not a hard filesystem write quota.",
            "wait4 covers the direct bwrap monitor and children it reaped, not complete job CPU/RSS; namespace-init accounting can be absent.",
            "Provisioned trees must remain immutable to other host principals; hash rechecks cannot detect ABA mutation.",
            "Seed/thread environment is supplied; programme implementations must apply RNG/backend settings and host qualification must verify them.",
            "Only /output and bounded /tmp provide writable regular-file storage; standard isolated character devices remain streams.",
            "The observed API source commit/body does not attest the supplied binary's reproducible build or host kernel behavior.",
            "Blocking kernel/filesystem calls require an independent supervisor for strict hard whole-parent wall enforcement.",
        ],
    })
    if log_fd is not None:
        report_fd = None
        try:
            custody.check(cleanup=True)
            body = _canonical(report) + b"\n"
            if len(body) > config.limits.report_bytes:
                raise ValueError("runner report cap exceeded")
            report_fd = custody.retain_fd(os.open("RUN_OBSERVATION.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                                                 0o600, dir_fd=log_fd), "runner report")
            _write_all(report_fd, body, custody, cleanup=True)
        except BaseException as error:
            custody.fail(error)
        finally:
            if report_fd is not None:
                custody.attempt("close runner report", lambda: custody.close_fd(report_fd))
            custody.attempt("close log directory", lambda: custody.close_fd(log_fd))
    custody.attempt("final whole caller deadline", lambda: custody.check(cleanup=True))
    report["elapsed_seconds"] = time.monotonic() - start
    report["report_stage"] = "caller cleanup and report attempt finished"
    report["report_and_cleanup_finished_before_deadline"] = report["elapsed_seconds"] < config.limits.wall_seconds
    report["secondary_failures"] = [{"type": type(e).__name__, "message": str(e)[:2000]} for e in custody.secondary]
    if custody.primary is not None:
        report["primary_failure"] = {"type": type(custody.primary).__name__, "message": str(custody.primary)[:2000]}
        try:
            setattr(custody.primary, "runner_observation", report)
            setattr(custody.primary, "runner_secondary_failures", tuple(custody.secondary))
        except BaseException:
            pass  # Must not replace the original failure for immutable exception types.
        raise custody.primary.with_traceback(custody.traceback)
    return report


def run_matched_pair(config: RunConfig, reference: CaseRequest,
                     candidate: CaseRequest) -> dict[str, Any]:
    """Actual sequential callers with one resource/runtime config and equal view.

    Programme source/tool mounts are shared and immutable; each invocation gets
    a distinct fresh process, output directory, log directory and sandbox tmpfs.
    A failure is propagated immediately with that invocation's raw custody.
    This helper does not issue scores or compare protected target arrays.
    """
    if reference.case_id != candidate.case_id or reference.view != candidate.view:
        raise ValueError("paired programmes must have the exact same case view")
    if reference.mode != candidate.mode:
        raise ValueError("paired programmes must use the same adaptation regime")
    paths = (reference.output_path, reference.log_path, candidate.output_path, candidate.log_path)
    for i, path in enumerate(paths):
        _absolute(path)
        if any(_overlap(path, other) for other in paths[:i]):
            raise ValueError("paired process output/log roots overlap")
    reference_result = run_case(config, reference)
    try:
        candidate_result = run_case(config, candidate)
    except BaseException as error:
        try:
            setattr(error, "runner_pair_reference", reference_result)
        except BaseException:
            pass
        raise
    return {"configuration_sha256": configuration_digest(config),
            "reference": reference_result, "candidate": candidate_result}
