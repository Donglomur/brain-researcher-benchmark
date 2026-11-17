"""Bounded inert prediction I/O shared by NEURAL-069/070.

The caller authenticates the public roster/task manifest and supplies its exact
ordered ID -> (102, V) mapping. This module never opens targets or runs a model.
Only after validate_prediction_files returns may the caller load private arrays.
All size/digest evidence describes captured bytes, never a later reread.
"""
from __future__ import annotations

import ast
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat

import numpy as np

MAX_HEADER = 16384
MAX_JSON = 4 * 1024 * 1024
_SHA = re.compile(r"[a-f0-9]{64}")
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,159}\.npy")


class IOContractError(ValueError):
    """Candidate bytes do not satisfy the declared inert-file contract."""


def _need(ok, message):
    if not ok:
        raise IOContractError(message)


def _positive_int(value, name):
    _need(type(value) is int and value > 0, name + " must be a positive integer")


def prediction_name(value):
    """One ordinary basename; absolute, nested and rerooted paths are forbidden."""
    _need(type(value) is str and _NAME.fullmatch(value) is not None
          and ".." not in value, "prediction path must be a safe .npy basename")
    return value


def _capture(path, max_bytes, *, dir_fd=None):
    _positive_int(max_bytes, "max_bytes")
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW, dir_fd=dir_fd)
    try:
        before = os.fstat(fd)
        _need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
              and 0 < before.st_size <= max_bytes, "bounded ordinary single-link file required")
        parts = []
        remaining = before.st_size + 1
        while remaining:
            part = os.read(fd, min(1024 * 1024, remaining))
            if not part:
                break
            parts.append(part)
            remaining -= len(part)
        raw = b"".join(parts)
        after = os.fstat(fd)
        fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns", "st_nlink")
        _need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) for k in fields),
              "file changed during same-descriptor capture")
        return raw, hashlib.sha256(raw).hexdigest()
    finally:
        os.close(fd)


def capture_regular(path, max_bytes):
    """Return (bytes, sha256); refuse symlink leaves, devices, FIFOs and growth."""
    return _capture(path, max_bytes)


def strict_json(raw, *, max_bytes=MAX_JSON, max_depth=32, max_integer_digits=128):
    """UTF-8 JSON with duplicate, nonfinite, nesting and integer-size guards."""
    for value, name in ((max_bytes, "max_bytes"), (max_depth, "max_depth"),
                        (max_integer_digits, "max_integer_digits")):
        _positive_int(value, name)
    _need(type(raw) is bytes and 0 < len(raw) <= max_bytes, "bounded JSON bytes required")
    try:
        text = raw.decode("utf-8")
    except UnicodeError as error:
        raise IOContractError("JSON must be UTF-8") from error
    depth = 0
    quoted = escaped = False
    for character in text:
        if quoted:
            if escaped:
                escaped = False
            elif character == "\\":
                escaped = True
            elif character == '"':
                quoted = False
        elif character == '"':
            quoted = True
        elif character in "[{":
            depth += 1
            _need(depth <= max_depth, "JSON nesting exceeds contract")
        elif character in "]}":
            depth -= 1
    def pairs(items):
        result = {}
        for key, value in items:
            _need(key not in result, "duplicate JSON key")
            result[key] = value
        return result
    def integer(token):
        _need(len(token.lstrip("-")) <= max_integer_digits, "JSON integer exceeds digit limit")
        return int(token)
    def floating(token):
        value = float(token)
        _need(math.isfinite(value), "nonfinite JSON number")
        return value
    def constant(_):
        raise IOContractError("nonfinite JSON constant")
    try:
        return json.loads(text, object_pairs_hook=pairs, parse_int=integer,
                          parse_float=floating, parse_constant=constant)
    except (json.JSONDecodeError, RecursionError) as error:
        raise IOContractError("malformed JSON") from error


def _shape(value, *, expected_rows=102):
    _positive_int(expected_rows, "expected_rows")
    _need(type(value) in (tuple, list) and len(value) == 2
          and all(type(x) is int and x > 0 for x in value) and value[0] == expected_rows,
          "array shape must match the fixed expected row count and positive columns")
    return tuple(value)


def parse_npy(raw, expected_shape, *, expected_rows=102):
    """Validate header/extent before frombuffer; return a read-only float array.

    Only uncompressed NPY 1/2/3, C order, primitive 32/64-bit IEEE floats are
    accepted. Endianness is preserved. Object/structured dtypes and pickle are
    never deserialized. There is no clipping, normalization or missing-value fix.
    """
    expected_shape = _shape(expected_shape, expected_rows=expected_rows)
    _need(type(raw) is bytes and len(raw) >= 10 and raw[:6] == b"\x93NUMPY", "ordinary NPY bytes required")
    version = tuple(raw[6:8])
    _need(version in ((1, 0), (2, 0), (3, 0)), "unsupported NPY version")
    start = 10 if version == (1, 0) else 12
    _need(len(raw) >= start, "truncated NPY prefix")
    header_size = int.from_bytes(raw[8:start], "little")
    _need(0 < header_size <= MAX_HEADER and start + header_size <= len(raw), "bounded complete NPY header required")
    header_bytes = raw[start:start + header_size]
    _need(header_bytes.endswith(b"\n"), "NPY header newline required")
    try:
        header = ast.literal_eval(header_bytes.decode("utf-8" if version == (3, 0) else "latin1").strip())
    except (SyntaxError, ValueError, UnicodeError, RecursionError, MemoryError) as error:
        raise IOContractError("malformed primitive NPY header") from error
    _need(type(header) is dict and set(header) == {"descr", "fortran_order", "shape"}, "exact NPY header fields required")
    _need(header["fortran_order"] is False, "prediction must use C order")
    _need(type(header["shape"]) is tuple and header["shape"] == expected_shape
          and all(type(x) is int for x in header["shape"]), "NPY shape differs from public roster")
    _need(type(header["descr"]) is str and header["descr"] in
          ("<f4", ">f4", "=f4", "<f8", ">f8", "=f8"), "only primitive float32/float64 predictions allowed")
    dtype = np.dtype(header["descr"])
    offset = start + header_size
    count = expected_shape[0] * expected_shape[1]
    _need(len(raw) == offset + count * dtype.itemsize, "NPY data extent differs from exact shape/dtype")
    array = np.frombuffer(raw, dtype=dtype, count=count, offset=offset).reshape(expected_shape)
    _need(bool(np.isfinite(array).all()), "every prediction must be finite")
    return array


def validate_prediction_files(root, records, expected_shapes, *, max_total_bytes):
    """Admit the complete ordered panel before returning any captured arrays.

    records: [{id, path, bytes, sha256}, ...], exact keys and expected ID order.
    expected_shapes: insertion-ordered dict from the authenticated public roster.
    The application validates that roster's full 80-case biological support.
    Return {arrays: ID->read-only ndarray, files: captured descriptors} only after
    every record succeeds. No private target callback is part of this function.
    """
    _positive_int(max_total_bytes, "max_total_bytes")
    _need(type(expected_shapes) is dict and bool(expected_shapes), "nonempty authenticated public shape mapping required")
    expected = list(expected_shapes)
    _need(all(type(k) is str and 0 < len(k) <= 160 for k in expected), "ordinary public case IDs required")
    shapes = {key: _shape(value) for key, value in expected_shapes.items()}
    _need(type(records) is list and len(records) == len(expected), "complete prediction file roster required")
    names = set()
    total = 0
    for record, key in zip(records, expected):
        _need(type(record) is dict and set(record) == {"id", "path", "bytes", "sha256"}
              and record["id"] == key, "exact prediction record fields and public case order required")
        name = prediction_name(record["path"])
        _need(name not in names, "duplicate prediction filename")
        names.add(name)
        size = record["bytes"]
        _positive_int(size, "prediction bytes")
        _need(size <= 8 * shapes[key][0] * shapes[key][1] + MAX_HEADER + 12, "declared NPY size exceeds public shape cap")
        _need(type(record["sha256"]) is str and _SHA.fullmatch(record["sha256"]) is not None, "exact lowercase SHA256 required")
        total += size
        _need(total <= max_total_bytes, "complete prediction panel exceeds byte budget")
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _need(stat.S_ISDIR(os.fstat(root_fd).st_mode), "ordinary candidate directory required")
        arrays, pins = {}, []
        for record in records:
            raw, digest = _capture(record["path"], record["bytes"], dir_fd=root_fd)
            _need(len(raw) == record["bytes"] and digest == record["sha256"], "captured prediction pin mismatch")
            arrays[record["id"]] = parse_npy(raw, shapes[record["id"]])
            pins.append({"id": record["id"], "path": record["path"], "bytes": len(raw), "sha256": digest})
        return {"arrays": arrays, "files": pins}
    finally:
        os.close(root_fd)


def write_json_exclusive(path, value, *, max_bytes=MAX_JSON):
    """Write fresh bounded JSON; never follow or overwrite an existing leaf."""
    _positive_int(max_bytes, "max_bytes")
    try:
        raw = (json.dumps(value, allow_nan=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    except (ValueError, TypeError, RecursionError) as error:
        raise IOContractError("output is not finite JSON") from error
    _need(len(raw) <= max_bytes, "JSON output exceeds byte budget")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        _need(stat.S_ISREG(os.fstat(fd).st_mode), "ordinary output required")
        view = memoryview(raw)
        while view:
            count = os.write(fd, view)
            _need(count > 0, "short output write")
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
