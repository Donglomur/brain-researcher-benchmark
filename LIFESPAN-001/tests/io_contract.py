"""Bounded grader-owned IO. Never import agent-visible staging helpers."""
from __future__ import annotations

import csv
from decimal import Decimal, InvalidOperation
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import zipfile

import numpy as np

LIMIT = 134_217_728
REQUIRED_FILES = ("cohort.csv", "parcels.csv", "connectome_primitives.npz",
                  "roi_partition.csv", "partition.json", "connectome_summary.csv",
                  "results.json", "run_metadata.json", "findings.md")


def need(condition, message):
    if not condition:
        raise ValueError(message)


def safe_path(value):
    raw = os.fspath(value)
    need(isinstance(raw, str) and raw.startswith("/") and "\x00" not in raw,
         "absolute path required")
    need(not any(p in (".", "..") for p in raw.split("/")), "path traversal refused")
    path = Path(raw)
    for p in (*reversed(path.parents), path):
        try:
            mode = p.lstat().st_mode
        except FileNotFoundError:
            continue
        need(not stat.S_ISLNK(mode), "symlink path or ancestor")
        if p != path:
            need(stat.S_ISDIR(mode), "non-directory ancestor")
    return path


def relative(value):
    need(isinstance(value, str) and value and "\\" not in value and "\x00" not in value,
         "invalid relative path")
    need(not value.startswith("/") and all(p not in ("", ".", "..") for p in value.split("/")),
         "unsafe relative path")
    return PurePosixPath(value)


def read_bytes(path, limit=LIMIT, *, size=None, sha256=None):
    path = safe_path(path)
    before = path.lstat()
    need(stat.S_ISREG(before.st_mode), "regular file required")
    need(before.st_size <= limit and (size is None or before.st_size == size), "file size mismatch/cap")
    identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), "rb") as stream:
        need(identity(os.fstat(stream.fileno())) == identity(before), "file changed before read")
        raw = stream.read(limit + 1)
        need(len(raw) <= limit and len(raw) == before.st_size, "file grew/truncated while reading")
        need(identity(os.fstat(stream.fileno())) == identity(before), "file changed during read")
    need(identity(path.lstat()) == identity(before), "file replaced during read")
    if sha256 is not None:
        need(hashlib.sha256(raw).hexdigest() == sha256, "file SHA256 mismatch")
    return raw


def _unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _finite_tree(value):
    if isinstance(value, float):
        need(math.isfinite(value), "nonfinite JSON number")
    elif isinstance(value, dict):
        for v in value.values(): _finite_tree(v)
    elif isinstance(value, list):
        for v in value: _finite_tree(v)


def json_bytes(raw):
    def invalid(value):
        raise ValueError("nonfinite JSON constant")
    value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique, parse_constant=invalid)
    _finite_tree(value)
    return value


def pinned_json(path, digest, limit=262_144):
    return json_bytes(read_bytes(path, limit, sha256=digest))


def csv_bytes(raw):
    reader = csv.reader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    header = next(reader, None)
    need(header is not None and all(header) and len(set(header)) == len(header), "invalid/duplicate CSV headers")
    rows = []
    for cells in reader:
        need(len(cells) == len(header), "CSV row width mismatch")
        rows.append(dict(zip(header, cells)))
    return rows


def integer(value):
    need(not isinstance(value, (bool, np.bool_)), "Boolean is not an integer field")
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid integer") from None
    need(d.is_finite() and d == d.to_integral_value(), "nonintegral field")
    need(abs(d) <= 2**63 - 1, "integer exceeds supported range")
    return int(d)


def number(value):
    need(not isinstance(value, (bool, np.bool_)) and value is not None, "numeric field required")
    try:
        value = float(value)
    except (ValueError, TypeError, OverflowError):
        raise ValueError("invalid number") from None
    need(math.isfinite(value), "finite numeric field required")
    return value


def integers(a):
    a = np.asarray(a)
    need(a.dtype.kind in "iuf", "integral numeric array required")
    need(np.isfinite(a).all(), "nonfinite integer array")
    if a.dtype.kind == "f":
        need(np.equal(a, np.floor(a)).all(), "fractional integer array")
    need(np.all(a >= -(2**63) + 1) and np.all(a < 2**63), "integer array range")
    return a.astype(np.int64)


def reals(a):
    a = np.asarray(a)
    need(a.dtype.kind in "iuf", "real numeric array required")
    return a.astype(np.float64)


def mask(a):
    a = np.asarray(a)
    need(a.dtype.kind in "biuf" and np.isfinite(a).all() and np.isin(a, [0, 1]).all(), "invalid Boolean mask")
    return a.astype(bool)


def strings(a):
    a = np.asarray(a)
    need(a.dtype.kind in "US", "string array required")
    values = [v.decode("utf-8") if isinstance(v, bytes) else str(v) for v in a.flat]
    return np.asarray(values, dtype=str).reshape(a.shape)


def npz_bytes(raw):
    """Preflight every NPY header before allocation; return same-buffer arrays."""
    result, expanded = {}, 0
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        seen = set()
        members = archive.infolist()
        need(len(members) <= 1024, "too many NPZ members")
        for info in members:
            name = info.filename
            need(name.endswith(".npy") and "/" not in name and "\\" not in name and name[:-4], "invalid NPZ member path")
            need(name not in seen and not info.is_dir() and not (info.flag_bits & 1), "duplicate/encrypted NPZ member")
            seen.add(name)
            expanded += info.file_size
            need(expanded <= LIMIT, "expanded NPZ cap")
            with archive.open(info) as stream:
                version = np.lib.format.read_magic(stream)
                need(version in ((1, 0), (2, 0)), "unsupported NPY version")
                read_header = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
                shape, fortran, dtype = read_header(stream, max_header_size=16384)
                need(not dtype.hasobject and len(shape) <= 8 and all(type(v) is int and v >= 0 for v in shape), "unsafe NPY dtype/shape")
                size = math.prod(shape) * dtype.itemsize
                need(size <= LIMIT and stream.tell() + size == info.file_size, "NPY shape/payload mismatch")
            payload = archive.read(info)
            value = np.lib.format.read_array(io.BytesIO(payload), allow_pickle=False)
            need(value.dtype == dtype and value.shape == shape, "NPY header changed")
            result[name[:-4]] = value
    return result, expanded


def output_snapshot(output_dir):
    root = safe_path(output_dir)
    need(root.is_dir(), "output directory required")
    need(not os.path.lexists(root / "failure_report.json"), "failure marker overrides success")
    files, total = {}, 0
    for parent, directories, filenames in os.walk(root, followlinks=False):
        for name in directories + filenames:
            path = Path(parent) / name
            mode = path.lstat().st_mode
            need(stat.S_ISDIR(mode) or stat.S_ISREG(mode), "nonregular output member")
            if stat.S_ISREG(mode):
                total += path.stat().st_size
                need(total <= LIMIT, "total artifact disk cap")
                files[path.relative_to(root).as_posix()] = path
    need(set(REQUIRED_FILES) <= set(files), "missing required artifact")
    snapshot, expanded = {}, 0
    for rel, path in files.items():
        raw = read_bytes(path)
        if rel.endswith(".npz"):
            arrays, size = npz_bytes(raw)
            if rel == "connectome_primitives.npz": snapshot[rel] = arrays
            expanded += size
        else:
            expanded += len(raw)
            if rel in REQUIRED_FILES: snapshot[rel] = raw
        need(expanded <= LIMIT, "total expanded artifact cap")
    return snapshot
