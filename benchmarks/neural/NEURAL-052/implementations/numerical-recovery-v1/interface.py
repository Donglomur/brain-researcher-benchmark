"""Bounded JSON I/O only; no NEURAL-052 scientific schema or data access.

Readers capture one regular file descriptor and verify its identity against the
name before returning bytes. Callers needing a hash must hash those returned
bytes and pass the same bytes to ``decode_json``; do not reopen for parsing.
Final-component symlinks and non-regular files are rejected. Parent-directory
integrity and isolation from later candidate writes remain executor duties.

Writers serialize and validate before exclusively creating a fresh report.
Writing failures are raised, never represented as a successful score. An I/O
failure may retain its new partial file for operator inspection; it is never
silently reused or deleted by this module.
"""
from __future__ import annotations

import json
import math
import os
import stat


MAX_JSON = 4_194_304
MAX_DEPTH = 64
MAX_INTEGER_DIGITS = 4096
_IDENTITY_FIELDS = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_mode")


class Invalid(ValueError):
    """Malformed, oversized, changed or unreadable JSON boundary input/output.

    The caller must distinguish candidate faults from operator/private faults
    by the operation's role; this I/O layer never assigns scientific scores.
    """


def _limit(value: int, name: str) -> int:
    if type(value) is not int or value < 1:
        raise Invalid(f"{name} must be a positive integer")
    return value


def _identity(a: os.stat_result, b: os.stat_result) -> bool:
    return all(getattr(a, key) == getattr(b, key) for key in _IDENTITY_FIELDS)


def capture_regular(path, cap: int = MAX_JSON) -> bytes:
    """Same-open bounded capture; FIFO/device/symlink and mutation rejection."""
    cap = _limit(cap, "byte cap")
    fd = None
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > cap:
            raise Invalid("bounded regular file required")
        body = bytearray()
        while True:
            part = os.read(fd, min(1_048_576, cap + 1 - len(body)))
            if not part:
                break
            body.extend(part)
            if len(body) > cap:
                raise Invalid("JSON byte cap exceeded")
        after = os.fstat(fd)
        named = os.lstat(path)
        if (not stat.S_ISREG(named.st_mode) or not _identity(before, after)
                or not _identity(after, named) or len(body) != after.st_size):
            raise Invalid("file changed during capture")
        return bytes(body)
    except OSError as exc:
        raise Invalid(f"regular file capture failed: {type(exc).__name__}") from exc
    finally:
        if fd is not None:
            os.close(fd)


def _depth(text: str, max_depth: int) -> None:
    """Bound structural nesting before the recursive standard JSON decoder."""
    depth, quoted, escape = 0, False, False
    for ch in text:
        if quoted:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
        elif ch in "[{":
            depth += 1
            if depth > max_depth:
                raise Invalid("JSON nesting limit exceeded")
        elif ch in "]}":
            depth -= 1
    # Syntax/balancing is checked by json.loads, not this resource precheck.


def _pairs(items):
    result = {}
    for key, value in items:
        if key in result:
            raise Invalid("duplicate JSON key")
        result[key] = value
    return result


def _constant(token):
    raise Invalid("nonfinite JSON number")


def _float(token):
    value = float(token)
    if not math.isfinite(value):
        raise Invalid("nonfinite or overflowing JSON number")
    return value


def _integer(token):
    digits = token[1:] if token.startswith("-") else token
    if len(digits) > MAX_INTEGER_DIGITS:
        raise Invalid("JSON integer digit limit exceeded")
    return int(token)


def decode_json(body: bytes, cap: int = MAX_JSON, max_depth: int = MAX_DEPTH):
    """Decode captured UTF-8 bytes; normalize parser and integer-limit errors."""
    cap, max_depth = _limit(cap, "byte cap"), _limit(max_depth, "nesting limit")
    if not isinstance(body, (bytes, bytearray)) or len(body) > cap:
        raise Invalid("bounded JSON bytes required")
    try:
        text = bytes(body).decode("utf-8")
        _depth(text, max_depth)
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=_constant,
                          parse_float=_float, parse_int=_integer)
    except Invalid:
        raise
    except (ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise Invalid(f"invalid JSON: {type(exc).__name__}") from exc


def read_json(path, cap: int = MAX_JSON, max_depth: int = MAX_DEPTH):
    return decode_json(capture_regular(path, cap), cap=cap, max_depth=max_depth)


def write_json_fresh(path, value, cap: int = MAX_JSON, max_depth: int = MAX_DEPTH) -> None:
    """Exclusive fresh creation, including dangling-symlink and race rejection.

    No exists()-then-write gap: O_EXCL is the authority. Before opening, produce
    only bounded UTF-8 JSON, reject nonfinite values and enforce nesting limits.
    A report is successful only after its FD is synced and named identity holds.
    """
    cap, max_depth = _limit(cap, "byte cap"), _limit(max_depth, "nesting limit")
    body = bytearray()
    try:
        encoder = json.JSONEncoder(ensure_ascii=False, allow_nan=False, sort_keys=True,
                                   separators=(",", ":"))
        for part in encoder.iterencode(value):
            encoded = part.encode("utf-8")
            if len(body) + len(encoded) + 1 > cap:
                raise Invalid("report JSON byte cap exceeded")
            body.extend(encoded)
        body.extend(b"\n")
        # Also catches key coercion collisions such as {1: ..., '1': ...} and
        # guarantees this writer's outputs satisfy this reader's boundary.
        decode_json(body, cap=cap, max_depth=max_depth)
    except Invalid:
        raise
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise Invalid(f"report JSON serialization failed: {type(exc).__name__}") from exc
    fd = None
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        created = os.fstat(fd)
        if not stat.S_ISREG(created.st_mode):
            raise Invalid("report must be a new regular file")
        view = memoryview(body)
        sent = 0
        while sent < len(view):
            written = os.write(fd, view[sent:sent + 1_048_576])
            if written <= 0:
                raise Invalid("report write made no progress")
            sent += written
        os.fsync(fd)
        after, named = os.fstat(fd), os.lstat(path)
        if ((after.st_dev, after.st_ino) != (created.st_dev, created.st_ino)
                or after.st_size != len(body) or not stat.S_ISREG(named.st_mode)
                or not _identity(after, named)):
            raise Invalid("report path changed during write")
    except OSError as exc:
        raise Invalid(f"fresh report write failed: {type(exc).__name__}") from exc
    finally:
        if fd is not None:
            os.close(fd)
