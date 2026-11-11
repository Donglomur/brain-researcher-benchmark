"""Bounded single-capture JSON decoding shared by NEURAL091/092 source tools."""
import json
import math
import os
from pathlib import Path
import re
import stat

ROSTER_SHA256 = "9afc2888bf5200c0362d5adbc951fc90cce2c5e120d58fe00bb83aa5926949fb"


def pairs(values):
    out = {}
    for key, value in values:
        if key in out:
            raise ValueError("Duplicate JSON key")
        out[key] = value
    return out


def capture(path, limit=30_000_000):
    """One bounded regular-file capture; never reopen between identity and parse."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError("Expected bounded regular JSON file")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(limit + 1)
        after = os.fstat(fd)
        if (len(body) > limit or len(body) != before.st_size
                or (before.st_dev, before.st_ino, before.st_size, before.st_nlink, before.st_mtime_ns, before.st_ctime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_nlink, after.st_mtime_ns, after.st_ctime_ns)):
            raise ValueError("JSON input changed during bounded capture")
        return body
    finally:
        os.close(fd)


def decode(body):
    source = body.decode("utf-8")
    # A small explicit bound is independent of the host JSON parser's recursion
    # implementation. Quotes/escapes prevent brackets inside strings counting.
    depth, quoted, escaped = 0, False, False
    for ch in source:
        if quoted:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                quoted = False
        elif ch == '"':
            quoted = True
        elif ch in "[{":
            depth += 1
            if depth > 64:
                raise ValueError("JSON nesting exceeds parser limit")
        elif ch in "]}":
            depth -= 1
    try:
        return json.loads(source, object_pairs_hook=pairs,
                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError("Nonfinite JSON literal")))
    except RecursionError as e:
        raise ValueError("JSON nesting exceeds parser limit") from e


def load(path, limit=30_000_000):
    return decode(capture(path, limit))


def frozen_roster(path):
    """Authenticate this task's exact cohort/partition before any source action."""
    import hashlib
    body = capture(path, 25_000_000)
    if hashlib.sha256(body).hexdigest() != ROSTER_SHA256:
        raise ValueError("Frozen NEURAL091/092 roster content identity mismatch")
    return decode(body), body

