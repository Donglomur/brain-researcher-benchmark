"""Strict metadata, immutable objects and finite effect accounting.

This module does not grant execution authority. A trusted host supplies the
selection pin; a candidate or an uploaded manifest cannot authorize itself.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat


class Rejected(ValueError):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code, self.detail = code, detail


def require(condition, code, detail):
    if not condition:
        raise Rejected(code, detail)


def integer(value, name, minimum=0):
    require(type(value) is int and value >= minimum, "invalid-integer", name)
    return value


def fraction(value, name="rational"):
    require(isinstance(value, list) and len(value) == 2, "invalid-rational", name)
    require(type(value[0]) is int and type(value[1]) is int and value[1] > 0,
            "invalid-rational", name)
    return Fraction(*value)


def rational(value):
    value = Fraction(value)
    return [value.numerator, value.denominator]


def identifier(value, name="id"):
    require(isinstance(value, str) and 0 < len(value.encode("utf-8")) <= 200
            and not any(ord(c) < 32 for c in value), "invalid-id", name)
    return value


def unique(rows, field="id"):
    ids = [identifier(row[field], field) for row in rows]
    require(len(ids) == len(set(ids)), "duplicate-id", field)
    return {row[field]: row for row in rows}


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False).encode("utf-8")
    except (ValueError, TypeError) as error:
        raise Rejected("invalid-json", str(error)) from error


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "duplicate-json-key", key)
        result[key] = value
    return result


def parse_json(body, max_bytes):
    require(len(body) <= integer(max_bytes, "max JSON bytes", 1),
            "metadata-limit", "JSON body exceeds admitted cap")
    try:
        def finite_float(text):
            value = float(text)
            require(math.isfinite(value), "nonfinite-json", text)
            return value
        return json.loads(body, object_pairs_hook=_pairs, parse_float=finite_float,
                          parse_constant=lambda x: (_ for _ in ()).throw(
                              Rejected("nonfinite-json", x)))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise Rejected("invalid-json", str(error)) from error


def relative(value):
    require(isinstance(value, str) and "\\" not in value and "\x00" not in value,
            "unsafe-path", str(value))
    path = PurePosixPath(value)
    require(not path.is_absolute() and path.parts and all(
        part not in ("", ".", "..") for part in path.parts)
        and str(path) == value, "unsafe-path", value)
    return path


def validate_pin(pin):
    require(set(pin) == {"path", "bytes", "sha256"}, "invalid-pin", "pin fields")
    relative(pin["path"])
    integer(pin["bytes"], "pin bytes")
    require(isinstance(pin["sha256"], str)
            and re.fullmatch(r"[0-9a-f]{64}", pin["sha256"]),
            "invalid-pin", "sha256")
    return pin


@dataclass
class Meter:
    """Logical bytes/steps, explicitly not a physical I/O or RSS measurement."""
    read_limit: int
    write_limit: int
    step_limit: int
    reads: int = 0
    writes: int = 0
    steps: int = 0

    def __post_init__(self):
        for key in ("read_limit", "write_limit", "step_limit"):
            integer(getattr(self, key), key)

    def charge(self, kind, amount):
        integer(amount, "charge")
        attr, limit = {"read": ("reads", "read_limit"),
                       "write": ("writes", "write_limit"),
                       "step": ("steps", "step_limit")}[kind]
        require(getattr(self, attr) + amount <= getattr(self, limit),
                "resource-limit", f"logical {kind} cap")
        setattr(self, attr, getattr(self, attr) + amount)

    def receipt(self):
        return {"logical_read_bytes": self.reads, "logical_write_bytes": self.writes,
                "algorithmic_steps": self.steps, "physical_io": None, "rss": None}


class ObjectStore:
    """Root-relative, no symlink traversal; hashes streamed after reservation.

    Pins must already have a permitted role. Opening an object is an effect;
    nothing here treats a publisher digest as measured local integrity.
    """
    def __init__(self, root, meter):
        self.root = Path(root).absolute()
        self.meter = meter

    def _open(self, rel):
        parts = relative(rel).parts
        directory = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                nxt = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                              dir_fd=directory)
                os.close(directory)
                directory = nxt
            fd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            require(stat.S_ISREG(os.fstat(fd).st_mode), "not-regular-file", rel)
            return fd
        finally:
            os.close(directory)

    def read(self, pin, retain=False):
        validate_pin(pin)
        self.meter.charge("read", pin["bytes"])
        hasher, blocks = hashlib.sha256(), []
        fd = self._open(pin["path"])
        try:
            before = os.fstat(fd)
            require(before.st_size == pin["bytes"], "size-mismatch", pin["path"])
            total = 0
            while total < pin["bytes"]:
                block = os.read(fd, min(1024 * 1024, pin["bytes"] - total))
                require(bool(block), "short-read", pin["path"])
                total += len(block)
                hasher.update(block)
                if retain:
                    blocks.append(block)
            after = os.fstat(fd)
            require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                    == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
                    "object-changed", pin["path"])
            require(hasher.hexdigest() == pin["sha256"], "digest-mismatch", pin["path"])
            return b"".join(blocks) if retain else dict(pin)
        finally:
            os.close(fd)

    def json(self, pin, max_bytes):
        require(pin["bytes"] <= max_bytes, "metadata-limit", pin["path"])
        return parse_json(self.read(pin, retain=True), max_bytes)


def write_new(path, value, meter):
    """Append-only receipt creation. Existing failure/history cannot be erased."""
    body = canonical(value) + b"\n"
    meter.charge("write", len(body))
    path = Path(path)
    require(path.parent.is_dir() and not path.parent.is_symlink(),
            "unsafe-output-parent", str(path.parent))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        # Retain any partially created receipt; never reuse the attempt ID.
        raise
    return {"path": path.name, "bytes": len(body),
            "sha256": hashlib.sha256(body).hexdigest()}


def outcome(status, result=None, gaps=(), **extra):
    require(status in {"ok", "required-unscorable", "invalid-input", "resource-limit",
                       "failed", "not-qualified"}, "invalid-status", status)
    return {"status": status, "result": result, "gaps": list(gaps), **extra}
