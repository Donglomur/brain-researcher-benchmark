"""Bounded, immutable ordinary-file custody shared by the stage implementations.

This module has no dataset discovery, network or automatic native reads.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
from pathlib import Path
import stat
from dataclasses import asdict, dataclass


FORBIDDEN_DIRECTORY_NAME = "openbmi-full216-identity-keys-001"


class ContractError(ValueError):
    pass


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode()


def decode(body):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError("duplicate JSON key")
            result[key] = value
        return result
    def bad_constant(value):
        raise ContractError("nonfinite JSON literal: " + value)
    def real(value):
        result = float(value)
        if not math.isfinite(result):
            raise ContractError("JSON number is outside finite binary64 range")
        return result
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad_constant,
                      parse_float=real)


def guard_namespace(path):
    """Reject the reserved namespace lexically, before any filesystem access.

    This shared guard does not stat, resolve, open or require a file type.
    Ordinary-file and Unix-socket callers retain their own custody checks.
    """
    p = Path(path).absolute()
    if any(member.name.casefold() == FORBIDDEN_DIRECTORY_NAME.casefold() for member in (p, *p.parents)):
        raise ContractError("protected identity-key namespace is never accessible")
    return p


def ordinary(path, *, directory=False):
    p = guard_namespace(path)
    for member in (*reversed(p.parents), p):
        mode = member.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ContractError("symlink path/ancestor rejected")
    mode = p.lstat().st_mode
    if not (stat.S_ISDIR(mode) if directory else stat.S_ISREG(mode)):
        raise ContractError("wrong ordinary input type")
    if not directory and p.lstat().st_nlink != 1:
        raise ContractError("hard-linked input aliases are not admitted")
    return p


def identity(s):
    return (s.st_dev, s.st_ino, s.st_size, s.st_nlink, s.st_mtime_ns, s.st_ctime_ns)


@dataclass(frozen=True)
class Artifact:
    path: str
    bytes: int
    sha256: str
    role: str
    visibility: str
    producer: str
    media_type: str = "application/json"

    def object(self):
        return asdict(self)

    @classmethod
    def parse(cls, value):
        if not isinstance(value, dict) or set(value) != set(cls.__dataclass_fields__):
            raise ContractError("exact artifact descriptor fields required")
        x = cls(**value)
        if type(x.bytes) is not int or x.bytes < 0:
            raise ContractError("invalid artifact size")
        if (not isinstance(x.sha256, str) or len(x.sha256) != 64 or
                any(c not in "0123456789abcdef" for c in x.sha256)):
            raise ContractError("invalid artifact digest")
        if x.visibility not in ("operator", "development", "candidate", "report"):
            raise ContractError("invalid artifact visibility")
        if not all(isinstance(v, str) and v for v in
                   (x.path, x.role, x.producer, x.media_type)):
            raise ContractError("invalid artifact string field")
        return x


class ByteMeter:
    """Logical requested/read/write byte accounting, not physical OS I/O."""
    def __init__(self, read_limit, write_limit):
        if any(type(v) is not int or v < 0 for v in (read_limit, write_limit)):
            raise ContractError("finite integer byte limits required")
        self.read_limit, self.write_limit = read_limit, write_limit
        self.read_bytes = self.write_bytes = 0

    def read(self, amount):
        if amount < 0 or self.read_bytes + amount > self.read_limit:
            raise ContractError("logical read allowance exceeded")
        self.read_bytes += amount

    def write(self, amount):
        if amount < 0 or self.write_bytes + amount > self.write_limit:
            raise ContractError("logical write allowance exceeded")
        self.write_bytes += amount

    def snapshot(self):
        return {"logical_read_bytes": self.read_bytes,
                "logical_write_bytes": self.write_bytes,
                "physical_os_io": None}


def capture(path, cap, *, descriptor=None, meter=None):
    p = ordinary(path)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size > cap:
            raise ContractError("ordinary file exceeds explicit byte cap")
        if descriptor and before.st_size != descriptor.bytes:
            raise ContractError("artifact byte identity mismatch")
        if meter:
            meter.read(before.st_size)
        body = stream.read(before.st_size)
        if len(body) != before.st_size or stream.read(1):
            raise ContractError("source length changed during capture")
        if identity(before) != identity(os.fstat(stream.fileno())):
            raise ContractError("source metadata changed during capture")
        digest = hashlib.sha256(body).hexdigest()
        if descriptor and digest != descriptor.sha256:
            raise ContractError("artifact content identity mismatch")
        return body


class ArtifactStore:
    """Fresh output namespace; no overwrite, path escape or private-role alias."""
    def __init__(self, root, meter):
        self.root = ordinary(root, directory=True)
        self.meter = meter

    def path(self, relative):
        rel = Path(relative)
        if rel.is_absolute() or any(p in ("", ".", "..") for p in rel.parts):
            raise ContractError("relative artifact name required")
        p = guard_namespace(self.root / rel)
        if self.root not in p.parents:
            raise ContractError("artifact escaped root")
        for parent in reversed(p.parent.parents):
            if parent == self.root or self.root in parent.parents:
                ordinary(parent, directory=True)
        ordinary(p.parent, directory=True)
        return p

    def mkdir(self, relative):
        rel = Path(relative)
        if rel.is_absolute() or any(p in ("", ".", "..") for p in rel.parts):
            raise ContractError("relative directory name required")
        # Reject the complete destination before creating even an earlier,
        # otherwise permitted directory in a nested relative name.
        guard_namespace(self.root / rel)
        current = self.root
        for part in rel.parts:
            current = current / part
            try:
                current.mkdir(mode=0o700)
            except FileExistsError:
                ordinary(current, directory=True)
        return current

    def write(self, relative, body, *, role, visibility, producer,
              media_type="application/json"):
        if not isinstance(body, bytes):
            raise TypeError("artifact body must be bytes")
        # path() guards the full destination before its parent inspections;
        # no write charge or open can precede that shared lexical check.
        path = self.path(relative)
        self.meter.write(len(body))
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o400)
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        dfd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(dfd)
        finally:
            os.close(dfd)
        return Artifact(str(path), len(body), hashlib.sha256(body).hexdigest(),
                        role, visibility, producer, media_type)

    def json(self, relative, value, **kwargs):
        return self.write(relative, canonical(value), **kwargs)

    def read_json(self, descriptor, *, roles, cap):
        ref = descriptor if isinstance(descriptor, Artifact) else Artifact.parse(descriptor)
        if ref.role not in roles or ref.media_type != "application/json":
            raise ContractError("artifact role/media does not match this consumer")
        return decode(capture(ref.path, cap, descriptor=ref, meter=self.meter))
