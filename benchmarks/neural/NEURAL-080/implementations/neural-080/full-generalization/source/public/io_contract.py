"""Bounded single-capture JSON decoding shared by NEURAL060 source tools."""
import json
import math
import os
from pathlib import Path
import re
import stat


def pairs(values):
    out = {}
    for key, value in values:
        if key in out:
            raise ValueError("Duplicate JSON key")
        out[key] = value
    return out


def capture(path, limit=30_000_000, *, owner=None):
    """One bounded capture, preserving the first failure through both closes.

    The selected programme passes its existing Owner. Direct legacy callers
    retain the same bytes/exception API; their local record is not an external
    lifecycle report or an admission/cost authority.
    """
    record = (owner.begin('legacy_capture') if owner is not None else
              {'first': None, 'secondary': [], 'state': 'entered'})
    fd = None
    stream = None
    body = None
    def failed(exc):
        if owner is not None:
            owner.failure(record, exc)
        else:
            if record['first'] is None:
                record['first'] = exc
            else:
                record['secondary'].append(exc)
            record['state'] = 'failed'
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
            raise ValueError("Expected bounded regular JSON file")
        stream = os.fdopen(fd, "rb", closefd=False)
        body = stream.read(limit + 1)
        after = os.fstat(fd)
        if (len(body) > limit or len(body) != before.st_size
                or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
                != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)):
            raise ValueError("JSON input changed during bounded capture")
    except BaseException as exc:
        failed(exc)
    finally:
        # Record each occurrence; repeated exception identity is not deduplicated.
        if stream is not None:
            try:
                stream.close()
            except BaseException as exc:
                failed(exc)
        if fd is not None:
            try:
                os.close(fd)
            except BaseException as exc:
                failed(exc)
    if owner is not None:
        owner.complete(record)
    elif record['first'] is not None:
        raise record['first']
    return body


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

