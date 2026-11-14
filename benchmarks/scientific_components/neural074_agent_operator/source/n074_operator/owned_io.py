"""Pinned file IO for an operator-owned ordinary namespace.

This is content/ordering enforcement, not native isolation against a hostile
filesystem or malicious candidate. No file is opened at import time.
"""
from dataclasses import dataclass
from pathlib import PurePosixPath
import hashlib
import json
import math
import os
import stat
import time


class Refusal(ValueError):
    pass


class BoundaryFailure(RuntimeError):
    """Retain the original operation exception and every subsequent close error."""
    def __init__(self, first, secondary=()):
        self.first = first
        self.secondary = tuple(secondary)
        super().__init__(type(first).__name__)


def require(condition, message):
    if not condition:
        raise Refusal(message)


def text(value, name):
    require(type(value) is str and value and value.strip() == value and
            "\x00" not in value and len(value.encode("utf-8")) <= 2048, name)
    return value


def exact_keys(value, names, name):
    require(type(value) is dict and set(value) == set(names), name)
    return value


def integer(value, name, minimum=1):
    require(type(value) is int and minimum <= value <= (1 << 63) - 1, name)
    return value


def digest(value):
    require(type(value) is str and len(value) == 64 and
            all(c in "0123456789abcdef" for c in value), "exact SHA256")
    return value


@dataclass(frozen=True)
class Pin:
    bytes: int
    sha256: str

    def validate(self):
        integer(self.bytes, "selected file extent", 0)
        digest(self.sha256)
        return self

    @classmethod
    def parse(cls, value):
        exact_keys(value, ("bytes", "sha256"), "closed file pin")
        return cls(value["bytes"], value["sha256"]).validate()

    def document(self):
        return {"bytes": self.bytes, "sha256": self.sha256}


class Budget:
    """One cooperative deadline and cumulative managed file-byte reservations."""
    def __init__(self, *, read_bytes, write_bytes, file_operations, seconds):
        self.read_cap = integer(read_bytes, "read reservation")
        self.write_cap = integer(write_bytes, "write reservation")
        self.file_cap = integer(file_operations, "file-operation reservation")
        require(type(seconds) in (int, float) and math.isfinite(seconds) and
                0 < seconds <= 86400, "finite original operation lifetime")
        self.origin = time.monotonic()
        self.deadline = self.origin + seconds
        self.read_reserved = self.write_reserved = self.files_reserved = 0

    def check(self):
        require(time.monotonic() < self.deadline, "original cooperative deadline")

    def read(self, size):
        self.check()
        integer(size, "read extent", 0)
        require(size <= self.read_cap - self.read_reserved, "cumulative read cap")
        self.read_reserved += size

    def write(self, size):
        self.check()
        integer(size, "write extent", 0)
        require(size <= self.write_cap - self.write_reserved, "cumulative write cap")
        self.write_reserved += size

    def file(self):
        self.check()
        require(self.files_reserved < self.file_cap, "cumulative file-operation cap")
        self.files_reserved += 1

    def observation(self):
        return {"read_reserved": self.read_reserved, "read_cap": self.read_cap,
                "write_reserved": self.write_reserved, "write_cap": self.write_cap,
                "files_reserved": self.files_reserved, "file_cap": self.file_cap,
                "origin": self.origin, "deadline": self.deadline,
                "hard_RSS_or_physical_IO_measurement": False}


def canonical_path(value, absolute):
    text(value, "canonical path")
    path = PurePosixPath(value)
    require(path.is_absolute() is absolute and str(path) == value and
            ".." not in path.parts and "." not in path.parts,
            "non-aliased selected path")
    parts = path.parts[1:] if absolute else path.parts
    require(not absolute or value == "/" + "/".join(parts), "single-root absolute spelling")
    require(parts and len(parts) <= 32 and all(len(p.encode()) <= 255 for p in parts),
            "bounded ordinary path")
    return parts


def _stamp(value):
    return (value.st_dev, value.st_ino, value.st_mode, value.st_nlink,
            value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def _close(fds, first=None):
    later = []
    while fds:
        descriptor = fds.pop()  # Retire ownership before a possibly failing close.
        try:
            os.close(descriptor)
        except BaseException as error:
            later.append(error)
    if first is not None:
        raise BoundaryFailure(first, later) from first
    if later:
        raise BoundaryFailure(later[0], later[1:]) from later[0]


def _directories(parts, fds):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fds.append(os.open("/", flags))
    for part in parts:
        fds.append(os.open(part, flags, dir_fd=fds[-1]))
    return fds[-1]


class Tree:
    """A frozen root inode; each access traverses directory FDs without symlinks."""
    def __init__(self, root):
        self.root = root
        self.parts = canonical_path(root, True)
        fds = []
        first = None
        try:
            fd = _directories(self.parts, fds)
            s = os.fstat(fd)
            require(stat.S_ISDIR(s.st_mode), "ordinary input root")
            self.identity = (s.st_dev, s.st_ino, s.st_mode)
            self.ancestors = tuple((os.fstat(f).st_dev, os.fstat(f).st_ino) for f in fds)
        except BaseException as error:
            first = error
        _close(fds, first)

    def _parent(self, name, fds):
        relative = canonical_path(name, False)
        require(len(self.parts) + len(relative) <= 32, "bounded complete path")
        fd = _directories(self.parts, fds)
        s = os.fstat(fd)
        require((s.st_dev, s.st_ino, s.st_mode) == self.identity,
                "selected root identity changed")
        for part in relative[:-1]:
            fds.append(os.open(part, os.O_RDONLY | os.O_DIRECTORY |
                               os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd))
            fd = fds[-1]
        return fd, relative[-1]

    def capture(self, name, pin, budget):
        require(type(pin) is Pin, "exact selected Pin")
        pin.validate()
        budget.read(pin.bytes + 1)
        budget.file()
        fds, first, raw = [], None, None
        try:
            parent, leaf = self._parent(name, fds)
            before = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
            require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
                    before.st_size == pin.bytes, "ordinary single-link selected extent")
            fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK |
                         os.O_CLOEXEC, dir_fd=parent)
            fds.append(fd)
            opened = os.fstat(fd)
            require(_stamp(opened) == _stamp(before), "opened source identity")
            chunks, remaining = [], pin.bytes + 1
            while remaining:
                budget.check()
                chunk = os.read(fd, min(65536, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            after = os.fstat(fd)
            named = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
            require(_stamp(before) == _stamp(after) == _stamp(named),
                    "source changed during capture")
            require(len(raw) == pin.bytes and hashlib.sha256(raw).hexdigest() == pin.sha256,
                    "complete selected content identity")
            budget.check()
        except BaseException as error:
            first = error
        _close(fds, first)
        return raw

    def write_once(self, name, raw, budget):
        require(type(raw) is bytes, "immutable publication bytes")
        budget.write(len(raw))
        budget.file()
        fds, first, pin = [], None, None
        try:
            parent, leaf = self._parent(name, fds)
            fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                         os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=parent)
            fds.append(fd)
            view, offset = memoryview(raw), 0
            while offset < len(raw):
                budget.check()
                count = os.write(fd, view[offset:offset + 65536])
                require(count > 0, "short publication write")
                offset += count
            os.fsync(fd)
            os.fchmod(fd, 0o400)
            os.fsync(fd)
            final = os.fstat(fd)
            named = os.stat(leaf, dir_fd=parent, follow_symlinks=False)
            require(stat.S_ISREG(final.st_mode) and final.st_nlink == 1 and
                    final.st_size == len(raw) and _stamp(final) == _stamp(named),
                    "published leaf identity")
            os.fsync(parent)
            pin = Pin(len(raw), hashlib.sha256(raw).hexdigest())
            budget.check()
        except BaseException as error:
            first = error
        _close(fds, first)
        return pin

    def mkdir_once(self, name, budget):
        budget.file()
        fds, first = [], None
        try:
            parent, leaf = self._parent(name, fds)
            os.mkdir(leaf, 0o700, dir_fd=parent)
            os.fsync(parent)
            budget.check()
        except BaseException as error:
            first = error
        _close(fds, first)


def create_tree(root, budget):
    parts = canonical_path(root, True)
    budget.file()
    fds, first = [], None
    try:
        parent = _directories(parts[:-1], fds)
        os.mkdir(parts[-1], 0o700, dir_fd=parent)
        os.fsync(parent)
        budget.check()
    except BaseException as error:
        first = error
    _close(fds, first)
    return Tree(root)


def separated(*roots):
    paths = [PurePosixPath(tree.root) for tree in roots]
    require(len({tree.identity[:2] for tree in roots}) == len(roots), "aliased roots")
    require(all(a.identity[:2] not in b.ancestors and b.identity[:2] not in a.ancestors
                for i, a in enumerate(roots) for b in roots[i + 1:]),
            "inode-overlapping custody ancestors")
    require(all(a != b and a not in b.parents and b not in a.parents
                for i, a in enumerate(paths) for b in paths[i + 1:]),
            "overlapping custody roots")


def strict_json(raw):
    require(type(raw) is bytes, "immutable JSON source")
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "duplicate JSON key")
            value[key] = item
        return value
    def constant(value):
        raise Refusal("nonfinite JSON constant")
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant)


def json_bytes(value, maximum):
    integer(maximum, "metadata byte cap")
    raw = (json.dumps(value, sort_keys=True, separators=(",", ":"),
                      allow_nan=False, ensure_ascii=True) + "\n").encode("utf-8")
    require(len(raw) <= maximum, "metadata publication cap")
    return raw
