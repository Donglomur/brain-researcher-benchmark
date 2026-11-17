"""Capture only the reviewed IT source closure; never import captured code.

The central bootstrap must authenticate this module and perform the live
registry/preference gate before calling it. This module grants no execution or
data authority. Its only output is the exact, immutable source byte snapshot.
"""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import PurePosixPath
import stat
import time


PREFIX = "authoring/delivery-20261105/common/remaining-builds-wave21/paper020-full-design/"
BINDING_PATH = PREFIX + "implementation-v1/runtime-adapters-v1/central-integration/source-capture/BINDING.json"
BINDING_BYTES = 14843
BINDING_SHA256 = "24fd1358248f7f2f536a23709ffef7a86add653ba5e6ee5117a3db844a435cff"
SCIENTIFIC_SOURCE_DIGEST = "0be6179b8ed5ac62960f867901310293de781f6815bee20c9723fe1a2b9d8898"
ADAPTER_MANIFEST_SHA256 = "ff037dc7bbaca0862888b6b6caac6b6d463f2297697b249f9f6f3babb518b37a"
BODY_BYTES = 462268
READ_LIMIT_BYTES = BINDING_BYTES + BODY_BYTES
REQUIRED_READ_LIMIT_BYTES = READ_LIMIT_BYTES
MAX_DESCRIPTORS = 128
ADAPTER_PREFIX = "implementation-v1/runtime-adapters-v1/successor-v3/"
SCIENTIFIC_PREFIX = "implementation-v1/successor-v2/"
ADAPTER_FILES = (
    "__init__.py", "authority.py", "basis.py", "candidate_worker.py", "entry.py",
    "guardian.py", "host_observer.py", "mat_source.py", "native_execution.py",
    "native_worker.m", "process_control.py", "provider.py", "runtime.py",
    "runtime_worker.py", "wire.py",
)
SCIENTIFIC_FILES = (
    "entry.py", "lib/__init__.py", "lib/admission.py", "lib/controller.py",
    "lib/dispatcher.py", "lib/native_capture.m", "lib/native_scoring.py",
    "lib/packets.py", "lib/programme.py", "lib/references.py",
    "lib/reproduction.py", "lib/scoring.py", "lib/splits.py", "lib/strict.py",
    "lib/units.py", "lib/source_identity.py", "contracts/programme.json",
    "contracts/OPERATOR_PROTOCOL.json",
)


class CaptureError(ValueError):
    """Fail closed, retaining the logical body-read charge for the attempt."""

    def __init__(self, message, read_bytes=0):
        super().__init__(message)
        self.read_bytes = read_bytes


@dataclass(frozen=True)
class SourcePin:
    source_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class SourceMember:
    source_path: str
    staged_path: str
    role: str
    size_bytes: int
    sha256: str
    body: bytes


@dataclass(frozen=True)
class SourceCapture:
    members: tuple
    read_bytes: int
    binding_sha256: str
    scientific_source_digest: str
    merge_receipt_pin: SourcePin


def _relative(value):
    if type(value) is not str or not value or len(value.encode()) > 4096:
        raise CaptureError("invalid relative source path")
    parts = value.split("/")
    if len(parts) > 64 or any(p in ("", ".", "..") for p in parts):
        raise CaptureError("noncanonical relative source path")
    if "\x00" in value or "\\" in value or str(PurePosixPath(value)) != value:
        raise CaptureError("invalid relative source path")
    return parts


def _absolute(value):
    # Do not invoke a caller-controlled __fspath__ implementation.
    if type(value) is not str or not value.startswith("/") or value == "/":
        raise CaptureError("repo_root must be a canonical absolute string")
    return _relative(value[1:])


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_nlink, st.st_size,
            st.st_mtime_ns, st.st_ctime_ns)


def _directory_identity(st):
    # Other tasks may change sibling files. Only this directory's identity and
    # type/mode are part of the path chain; a recursive repository census is not.
    return st.st_dev, st.st_ino, st.st_mode


class _Tree:
    """Own all traversed directory edges and source fds until final validation."""

    def __init__(self, root, limit):
        self.limit = limit
        self.read_bytes = 0
        self.fds = []
        self.directories = {}
        self.directory_edges = []
        self.files = []
        self.root_parts = _absolute(root)
        if not hasattr(os, "O_NOFOLLOW") or not hasattr(os, "O_DIRECTORY"):
            raise CaptureError("O_NOFOLLOW and O_DIRECTORY are required")

    def _own(self, fd):
        if len(self.fds) >= MAX_DESCRIPTORS:
            os.close(fd)
            raise CaptureError("source descriptor bound exceeded")
        self.fds.append(fd)
        return fd

    def __enter__(self):
        try:
            fd = self._own(os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW))
            self.directories[()] = fd
            self._directory(self.root_parts)
            return self
        except BaseException:
            self.close()
            raise

    def __exit__(self, *_):
        self.close()

    def close(self):
        for fd in reversed(self.fds):
            os.close(fd)
        self.fds.clear()

    def _directory(self, parts):
        key = ()
        for name in parts:
            next_key = key + (name,)
            if next_key not in self.directories:
                parent = self.directories[key]
                fd = self._own(os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                       dir_fd=parent))
                before = os.fstat(fd)
                if not stat.S_ISDIR(before.st_mode):
                    raise CaptureError("source ancestor is not a directory")
                identity = _directory_identity(before)
                path_stat = os.stat(name, dir_fd=parent, follow_symlinks=False)
                if identity != _directory_identity(path_stat):
                    raise CaptureError("source directory changed during open")
                self.directory_edges.append((parent, name, fd, identity))
                self.directories[next_key] = fd
            key = next_key
        return self.directories[key]

    def read(self, relative, size, sha256):
        parts = _relative(relative)
        if type(size) is not int or size < 0 or size > BODY_BYTES:
            raise CaptureError("invalid pinned source size")
        if self.read_bytes + size > self.limit:
            raise CaptureError("logical source-read bound exceeded")
        parent = self._directory(self.root_parts + parts[:-1])
        # NONBLOCK prevents a substituted FIFO from blocking before fstat.
        fd = self._own(os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                               dir_fd=parent))
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != size:
            raise CaptureError("source must be a single-link regular file of its pinned size")
        identity = _identity(before)
        if _identity(os.stat(parts[-1], dir_fd=parent, follow_symlinks=False)) != identity:
            raise CaptureError("source path changed during open")
        self.files.append((parent, parts[-1], fd, identity))
        chunks = []
        remaining = size
        while remaining:
            chunk = os.read(fd, min(65536, remaining))
            self.read_bytes += len(chunk)
            if not chunk:
                raise CaptureError("source truncated during read")
            chunks.append(chunk)
            remaining -= len(chunk)
        body = b"".join(chunks)
        if _identity(os.fstat(fd)) != identity:
            raise CaptureError("source mutated during read")
        if hashlib.sha256(body).hexdigest() != sha256:
            raise CaptureError("source SHA-256 mismatch")
        return body

    def verify(self):
        for parent, name, fd, identity in self.directory_edges:
            if (_directory_identity(os.fstat(fd)) != identity or
                _directory_identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) != identity):
                raise CaptureError("source directory path changed before closure")
        for parent, name, fd, identity in self.files:
            if (_identity(os.fstat(fd)) != identity or
                _identity(os.stat(name, dir_fd=parent, follow_symlinks=False)) != identity):
                raise CaptureError("source file changed before closure")


def _binding(body):
    document = json.loads(body)
    if (document.get("schema") != "paper020_central_parent_source_binding_v1" or
        document.get("task_id") != "PAPER-ROOT-ADD-020" or
        document.get("scientific_source_digest") != SCIENTIFIC_SOURCE_DIGEST or
        document.get("adapter_manifest_sha256") != ADAPTER_MANIFEST_SHA256 or
        document.get("total_body_bytes") != BODY_BYTES or
        document.get("total_members") != 34):
        raise CaptureError("source binding identity differs")
    members = document["files"]
    expected = [(ADAPTER_PREFIX + p, "adapter_production_source") for p in ADAPTER_FILES]
    expected += [(ADAPTER_PREFIX + "ADAPTER_SOURCE_MANIFEST.json", "adapter_manifest")]
    expected += [(SCIENTIFIC_PREFIX + p, "scientific_source_or_contract") for p in SCIENTIFIC_FILES]
    if len(members) != len(expected):
        raise CaptureError("source binding cardinality differs")
    for item, (staged, role) in zip(members, expected):
        if (item["staged_path"] != staged or item["source_path"] != PREFIX + staged or
            item["role"] != role or type(item["bytes"]) is not int or item["bytes"] <= 0 or
            type(item["sha256"]) is not str or len(item["sha256"]) != 64 or
            any(c not in "0123456789abcdef" for c in item["sha256"])):
            raise CaptureError("source binding member differs")
    if sum(item["bytes"] for item in members) != BODY_BYTES:
        raise CaptureError("source binding byte cardinality differs")
    identity = [{"path": item["staged_path"][len(SCIENTIFIC_PREFIX):],
                 "bytes": item["bytes"], "sha256": item["sha256"]}
                for item in members[16:]]
    digest = hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    if digest != SCIENTIFIC_SOURCE_DIGEST:
        raise CaptureError("scientific source identity differs")
    return document


def _clock(origin_ns, deadline_ns):
    if (type(origin_ns) is not int or type(deadline_ns) is not int or
        origin_ns <= 0 or deadline_ns <= origin_ns):
        raise CaptureError("original monotonic origin and deadline are required")
    now = time.monotonic_ns()
    if now < origin_ns or now >= deadline_ns:
        raise CaptureError("original source-capture clock is not live")


def capture_source(repo_root, *, read_limit_bytes=REQUIRED_READ_LIMIT_BYTES,
                   origin_ns=None, deadline_ns=None):
    """Return the 34 pinned source members, preserving their staged paths.

    The original monotonic origin/deadline are required, checked directly before
    any source open and after held-fd closure checks. No fresh clock is invented.
    The fixed bound includes the binding read, not filesystem/OS I/O. A smaller
    caller budget fails before opening the root. A larger budget cannot expand
    the closure. No source, data, key, operator or executable path is discovered.
    The receipt pin is provenance from the authenticated binding; this call does
    not reread the receipt or inspect Git. Consumers must authenticate this
    capture implementation, own staging, and preserve every returned member.
    """
    _clock(origin_ns, deadline_ns)
    if type(read_limit_bytes) is not int or read_limit_bytes < REQUIRED_READ_LIMIT_BYTES:
        raise CaptureError("complete fixed source closure does not fit read bound")
    tree = None
    try:
        tree = _Tree(repo_root, READ_LIMIT_BYTES)
        with tree:
            document = _binding(tree.read(BINDING_PATH, BINDING_BYTES, BINDING_SHA256))
            captured = tuple(SourceMember(
                item["source_path"], item["staged_path"], item["role"], item["bytes"],
                item["sha256"], tree.read(item["source_path"], item["bytes"], item["sha256"]))
                for item in document["files"])
            tree.verify()
            receipt = document["merge_identity"]["observed_receipt"]
            result = SourceCapture(captured, tree.read_bytes, BINDING_SHA256,
                                   SCIENTIFIC_SOURCE_DIGEST,
                                   SourcePin(receipt["path"], receipt["bytes"], receipt["sha256"]))
        _clock(origin_ns, deadline_ns)
        return result
    except (OSError, ValueError, TypeError, KeyError) as exc:
        charge = tree.read_bytes if tree is not None else 0
        raise CaptureError(str(exc), charge) from exc
