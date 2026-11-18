"""Small immutable-file primitives for the trusted MEG coordinator.

These checks assume an evaluator-controlled host. They do not defend against a
malicious host administrator or confer authority to execute a participant.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import stat


class StorageError(ValueError):
    pass


def need(condition, message):
    if not condition:
        raise StorageError(message)


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def decoded(body):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def invalid(value):
        raise StorageError("nonfinite JSON: " + value)
    return json.loads(body, object_pairs_hook=unique, parse_constant=invalid)


def pin(body):
    need(type(body) is bytes, "bytes required")
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def descriptor(value):
    need(type(value) is dict and set(value) == {"bytes", "sha256"}
         and type(value["bytes"]) is int and value["bytes"] >= 0
         and type(value["sha256"]) is str and len(value["sha256"]) == 64
         and all(c in "0123456789abcdef" for c in value["sha256"]), "exact file descriptor")
    return value


def ordinary_path(path):
    path = Path(path).absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), "symlink path forbidden")
    return path


def read(path, cap, expected=None):
    path = ordinary_path(path)
    need(type(cap) is int and cap > 0, "positive read ceiling")
    if expected is not None:
        descriptor(expected)
        need(expected["bytes"] <= cap, "expected extent exceeds read ceiling")
    extent = cap if expected is None else expected["bytes"]
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 <= before.st_size <= cap, "bounded single-link ordinary file")
        if expected is not None:
            need(before.st_size == extent, "file extent differs from reserved expected extent")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(extent + 1)
        after = os.fstat(fd)
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k)
             for k in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")),
             "file identity changed while reading")
        if expected is not None:
            need(pin(body) == descriptor(expected), "file pin mismatch")
        return body
    finally:
        os.close(fd)


def write(path, body, cap, *, public=False):
    path = ordinary_path(path)
    need(type(body) is bytes and len(body) <= cap, "bounded bytes required")
    mode = 0o444 if public else 0o600
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    try:
        with os.fdopen(fd, "wb", closefd=False) as stream:
            stream.write(body)
            stream.flush()
            # Public readability must survive a private process umask.
            os.fchmod(fd, mode)
            os.fsync(fd)
    finally:
        os.close(fd)
    return pin(body)


def directory(path):
    path = ordinary_path(path)
    need(not path.exists() and path.parent.is_dir(), "fresh directory and existing parent")
    path.mkdir(mode=0o700)
    return path


def seal_public_directory(path):
    path = ordinary_path(path)
    need(path.is_dir(), "directory required")
    for item in path.rglob("*"):
        need(not item.is_symlink(), "no symlink in public capsule")
        if item.is_file():
            need(stat.S_IMODE(item.stat().st_mode) == 0o444, "public leaf mode must be explicit")
        else:
            need(item.is_dir(), "ordinary directory only")
    for item in sorted((p for p in path.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        item.chmod(0o555)
    path.chmod(0o555)
