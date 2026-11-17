"""Stable bounded reads and byte hashing; no scientific imports."""
import hashlib
import os
from pathlib import Path
import stat

def read_regular(path, cap, expected=None):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Symbolic-link file is not accepted")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or not 0 < before.st_size <= cap:
            raise ValueError("Nonempty bounded ordinary single-link file required")
        raw = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
    if len(raw) != before.st_size or len(raw) > cap or any(
        getattr(before, k) != getattr(after, k)
        for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
    ):
        raise ValueError("Unstable or oversized file")
    if expected is not None and (
        len(raw) != expected["bytes"] or hashlib.sha256(raw).hexdigest() != expected["sha256"]
    ):
        raise ValueError("Artifact byte identity mismatch")
    return raw

def stream_pin(path):
    path = Path(path)
    if path.is_symlink():
        raise ValueError("Source asset must be an ordinary file")
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ValueError("Source asset must be a regular file")
    digest = hashlib.sha256(); count = 0
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1048576), b""):
            count += len(block); digest.update(block)
    after = path.stat()
    if count != before.st_size or any(getattr(before, k) != getattr(after, k)
        for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
        raise ValueError("Source asset changed during hashing")
    return {"bytes": count, "sha256": digest.hexdigest()}
