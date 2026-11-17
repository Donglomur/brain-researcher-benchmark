"""Bounded artifact/configuration and inherited-budget primitives."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import threading
import time


class AdapterError(ValueError):
    def __init__(self, message, evidence=None):
        super().__init__(message)
        self.evidence = evidence or {}


def need(condition, message):
    if not condition:
        raise AdapterError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def integer(value, name, minimum=0):
    need(type(value) is int and value >= minimum, name + " must be an exact nonnegative integer")
    return value


def positive(value, name):
    need(type(value) in (int, float) and math.isfinite(value) and value > 0, name + " must be finite positive")
    return value


def file_pin(path, ceiling=None, budget=None):
    path = Path(path)
    st = path.lstat()
    need(stat.S_ISREG(st.st_mode) and not path.is_symlink(), "ordinary artifact file required")
    if ceiling is not None:
        need(st.st_size <= ceiling, "artifact exceeds declared read cap")
    if budget:
        budget.charge("source_read", st.st_size)
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(65536), b""):
            h.update(block)
            if budget:
                budget.check_clock()
    after = path.stat()
    need((st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns), "artifact changed during read")
    return {"path": str(path.resolve()), "bytes": st.st_size, "sha256": h.hexdigest()}


def authenticate(pin, budget=None):
    need(isinstance(pin, dict) and {"path", "bytes", "sha256"} <= set(pin), "complete artifact descriptor")
    integer(pin["bytes"], "artifact size")
    actual = file_pin(pin["path"], pin["bytes"], budget)
    need(actual["bytes"] == pin["bytes"] and actual["sha256"] == pin["sha256"], "artifact identity mismatch")
    return actual


def json_exact(pin, budget=None, cap=16777216):
    authenticate(pin, budget)
    need(pin["bytes"] <= cap, "JSON descriptor cap")
    if budget:
        budget.charge("source_read", pin["bytes"])
    data = Path(pin["path"]).read_bytes()
    need(len(data) == pin["bytes"] and hashlib.sha256(data).hexdigest() == pin["sha256"], "JSON changed after pin")
    return json.loads(data)


def write_fresh(path, data, budget):
    path = Path(path)
    need(isinstance(data, bytes), "bytes-only write")
    budget.charge("artifact_write", len(data))
    with path.open("xb") as stream:
        stream.write(data); stream.flush(); os.fsync(stream.fileno())
    sync_directory(path.parent)
    budget.check_clock()
    return {"path": str(path.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def copy_exact(pin, destination, budget):
    """One authenticated copy; original descriptor never replaced by current hash."""
    source = Path(pin["path"])
    st = source.lstat()
    need(stat.S_ISREG(st.st_mode) and not source.is_symlink() and st.st_size == pin["bytes"], "staged exact ordinary source")
    budget.charge("source_read", st.st_size)
    budget.charge("artifact_write", st.st_size)
    h = hashlib.sha256(); count = 0
    with source.open("rb") as inp, Path(destination).open("xb") as out:
        for block in iter(lambda: inp.read(65536), b""):
            budget.check_clock(); count += len(block)
            need(count <= pin["bytes"], "source grew during staging")
            h.update(block); out.write(block)
        out.flush(); os.fsync(out.fileno())
    need(count == pin["bytes"] and h.hexdigest() == pin["sha256"], "staged source differs from approved pin")
    Path(destination).chmod(0o444)
    return {"path": str(Path(destination).resolve()), "bytes": count, "sha256": h.hexdigest()}


class CaseBudget:
    """Equal per-case envelope nested inside the unchanged whole-study ledger."""
    def __init__(self, parent, limits, wall_seconds):
        self.parent = parent
        self.origin_monotonic = parent.origin_monotonic
        self.started_monotonic = time.monotonic()
        self.deadline_monotonic = min(parent.deadline_monotonic, self.started_monotonic + positive(wall_seconds, "case wall"))
        self.limits = dict(limits)
        need(all(type(v) is int and v >= 0 for v in self.limits.values()), "exact case counters")
        self.used = {k: 0 for k in self.limits}
        self._lock = threading.Lock()

    def check_clock(self):
        self.parent.check_clock()
        need(time.monotonic() <= self.deadline_monotonic, "original/case deadline expired; no reset")

    def charge(self, name, amount=1):
        self.check_clock(); integer(amount, "resource charge")
        with self._lock:
            need(name in self.limits and self.used[name] + amount <= self.limits[name], "case budget exhausted: " + name)
            self.parent.charge(name, amount)
            self.used[name] += amount

    def snapshot(self):
        return {"origin_monotonic": self.origin_monotonic, "started_monotonic": self.started_monotonic,
                "deadline_monotonic": self.deadline_monotonic, "limits": self.limits, "used": dict(self.used)}


