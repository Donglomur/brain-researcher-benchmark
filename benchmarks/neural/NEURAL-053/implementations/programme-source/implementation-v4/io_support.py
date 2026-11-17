"""Bounded ordinary-file input and explicit future-run authority boundaries."""
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import time
from dataclasses import dataclass
from cohort import require, Refusal


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def object_digest(value):
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def ordinary_file(path, maximum):
    path = Path(path)
    require(type(maximum) is int and maximum >= 0, "Finite ordinary-file cap")
    require(not path.is_symlink(), "No symlink input")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0))
    before = os.fstat(fd)
    if not stat.S_ISREG(before.st_mode) or before.st_size > maximum:
        os.close(fd)
        raise Refusal("Ordinary file within declared cap required")
    return path, fd, before


def identity(s):
    return tuple(getattr(s, name) for name in
                 ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns"))


def checked_bytes(path, expected, budget):
    """Expected bytes/hash are independently admitted, not caller-discovered pins."""
    require(set(expected) >= {"bytes", "sha256"}, "Exact source descriptor")
    budget.charge("source_read", expected["bytes"])
    path, fd, before = ordinary_file(path, expected["bytes"])
    try:
        require(before.st_size == expected["bytes"], "Exact source extent")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(expected["bytes"] + 1)
        require(len(body) == expected["bytes"], "Exact bounded body")
        require(identity(before) == identity(os.fstat(fd)) == identity(path.lstat()),
                "Unchanged ordinary file during read")
        require(hashlib.sha256(body).hexdigest() == expected["sha256"], "Exact source hash")
        return body
    finally:
        os.close(fd)


def authenticate_file(path, expected, budget, chunk_bytes=1048576):
    budget.charge("source_read", expected["bytes"])
    path, fd, before = ordinary_file(path, expected["bytes"])
    try:
        require(before.st_size == expected["bytes"], "Exact original body extent")
        digest = hashlib.sha256()
        with os.fdopen(fd, "rb", closefd=False) as stream:
            for chunk in iter(lambda: stream.read(chunk_bytes), b""):
                budget.check_clock()
                digest.update(chunk)
        require(identity(before) == identity(os.fstat(fd)) == identity(path.lstat()),
                "Source identity changed during authentication")
        require(digest.hexdigest() == expected["sha256"], "Original derivative hash mismatch")
        return identity(before)
    finally:
        os.close(fd)


@dataclass
class Budget:
    """Logical counters plus inherited clock; not an OS memory/process governor.

    A separately qualified external observer must enforce process/RSS/CPU/GPU,
    physical I/O, namespaces and final durability. These counters never claim it.
    """
    limits: dict
    origin_monotonic: float
    deadline_monotonic: float

    def __post_init__(self):
        require(all(type(v) is int and v >= 0 for v in self.limits.values()), "Nonnegative limits")
        require(math.isfinite(self.origin_monotonic) and math.isfinite(self.deadline_monotonic)
                and self.origin_monotonic <= self.deadline_monotonic, "Inherited finite clock")
        self.used = {name: 0 for name in self.limits}
        self.events = []

    def check_clock(self):
        require(time.monotonic() <= self.deadline_monotonic, "Original whole-run deadline expired")

    def charge(self, name, amount=1):
        self.check_clock()
        require(name in self.limits and type(amount) is int and amount >= 0,
                "Declared resource counter")
        proposed = self.used[name] + amount
        require(proposed <= self.limits[name], f"Resource budget exhausted: {name}")
        self.used[name] = proposed

    def record(self, event, **details):
        self.check_clock()
        self.events.append({"event": event, **details})


REQUIRED_RUN_QUALIFICATIONS = frozenset({"source_inputs", "source_closure", "runtime",
    "namespace", "resources", "process_observer", "target_custody", "provider_contexts"})


def admit_full_run(receipt, expected_bindings, protected_approved_digests, required_phase=None):
    """Trusted operator entry boundary. The approved set is NOT author input.

    The independent operator supplies a protected accepted-receipt digest set
    from outside all author/candidate namespaces. An author-issued pass boolean
    does not confer authority. No current authentic receipt is shipped here.
    """
    require(isinstance(protected_approved_digests, frozenset), "Protected immutable approval set")
    require(isinstance(receipt, dict) and object_digest(receipt) in protected_approved_digests,
            "No independently approved full-run receipt")
    require(receipt.get("schema") == "neural053_full_run_admission_v1" and
            receipt.get("decision") == "accepted_exact_canonical_full_run",
            "Exact full canonical run authority")
    require(receipt.get("bindings") == expected_bindings and expected_bindings.get("profile") ==
            "four_people_1854_classes_96_contexts_3904_fits", "Current exact full-run bindings")
    if required_phase is not None:
        require(expected_bindings.get("phase") == required_phase, "Exact selected execution phase")
    qs = receipt.get("qualifications", {})
    require(set(qs) == REQUIRED_RUN_QUALIFICATIONS, "All independent runtime/input qualifications")
    require(all(isinstance(v, str) and len(v) == 64 and v in protected_approved_digests
                for v in qs.values()), "Every qualification independently accepted")
    require(isinstance(receipt.get("independent_reviewer"), str) and
            receipt["independent_reviewer"], "Independent review identity")
    return object_digest(receipt)


def safe_relative(root, name):
    p = Path(name)
    require(not p.is_absolute() and ".." not in p.parts and p.parts,
            "Safe source-relative path")
    candidate = Path(root) / p
    # A leaf O_NOFOLLOW alone does not exclude symlinked parent directories.
    current = Path(root)
    require(not current.is_symlink(), "Ordinary source root")
    for part in p.parts[:-1]:
        current = current / part
        require(not current.is_symlink(), "No symlink source ancestor")
    return candidate
