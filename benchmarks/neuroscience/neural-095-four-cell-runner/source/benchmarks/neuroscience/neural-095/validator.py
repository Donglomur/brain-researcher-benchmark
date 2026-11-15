"""Bounded public-only NPZ boundary for one arbitrary NEURAL-095 prediction.

Adapted from the qualified NEURAL-077 adapter's ZIP/NPY preflight. No private
target, model, reference prediction, or candidate code is loaded here.
"""
from __future__ import annotations

import ast
import os
from pathlib import Path
import stat
import struct
import zipfile

import numpy as np

MAX_FILE_BYTES = 1024 * 1024
MAX_EXPANDED_BYTES = 1024 * 1024
MAX_HEADER_BYTES = 4096
MAX_CASES = 512
MEMBERS = {"case_id.npy", "prediction_ms.npy"}


class InvalidSubmission(ValueError):
    """Public submission failed validation; private loading is forbidden."""


def require(ok, message):
    if not ok:
        raise InvalidSubmission(message)


def canonical_id(value):
    return (type(value) is str and len(value) == 11 and value.startswith("dmfc-")
            and all(c in "0123456789" for c in value[5:]))


def public_ids(expected_ids):
    require(type(expected_ids) is list and 1 <= len(expected_ids) <= MAX_CASES
            and all(canonical_id(x) for x in expected_ids)
            and len(set(expected_ids)) == len(expected_ids),
            "Complete unique canonical public case IDs required")
    return expected_ids.copy()


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, st.st_nlink)


def _regular(path):
    path = Path(path).absolute()
    require(all(not p.is_symlink() for p in (path, *path.parents)),
            "Candidate and all ancestor paths must be unlinked")
    st = path.lstat()
    require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1
            and 0 < st.st_size <= MAX_FILE_BYTES,
            "Nonempty bounded regular file with one hard link required")
    return path, st


def _header(member, name, n, declared_bytes):
    require(member.read(6) == b"\x93NUMPY", "NPY magic required")
    version = member.read(2)
    require(version in (b"\x01\x00", b"\x02\x00"), "Only NPY versions 1 and 2 accepted")
    width = 2 if version == b"\x01\x00" else 4
    encoded = member.read(width)
    require(len(encoded) == width, "Truncated NPY header length")
    length = struct.unpack("<H" if width == 2 else "<I", encoded)[0]
    require(1 <= length <= MAX_HEADER_BYTES and member.tell() + length <= declared_bytes,
            "Bounded complete NPY header required")
    raw = member.read(length)
    require(len(raw) == length and raw.endswith(b"\n"), "Complete NPY header required")
    try:
        expression = ast.parse(raw.decode("latin1").strip(), mode="eval")
        require(isinstance(expression.body, ast.Dict), "Literal NPY header dictionary required")
        keys = [ast.literal_eval(k) for k in expression.body.keys]
        require(len(keys) == 3 and set(keys) == {"descr", "fortran_order", "shape"},
                "Exact unique NPY header keys required")
        header = ast.literal_eval(expression)
    except (SyntaxError, ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise InvalidSubmission("Invalid NPY header literal") from exc
    require(type(header["fortran_order"]) is bool
            and type(header["shape"]) is tuple and header["shape"] == (n,)
            and all(type(x) is int for x in header["shape"]),
            "Exact one-dimensional complete-case geometry required")
    require(type(header["descr"]) is str and len(header["descr"]) <= 32,
            "Simple bounded dtype descriptor required")
    try:
        dtype = np.dtype(header["descr"])
    except (ValueError, TypeError) as exc:
        raise InvalidSubmission("Invalid dtype") from exc
    require(not dtype.hasobject and dtype.fields is None and dtype.subdtype is None,
            "No object, structured or subarray dtype")
    if name == "case_id.npy":
        require(dtype.kind == "U" and dtype.itemsize == 44, "Unicode U11 case IDs required")
    else:
        require(dtype.kind == "f" and dtype.itemsize in (4, 8),
                "Prediction dtype must be float32 or float64")
    remaining = n * dtype.itemsize
    require(member.tell() + remaining == declared_bytes,
            "Expanded member must equal header plus exact array bytes")
    while remaining:
        block = member.read(min(65536, remaining))
        require(bool(block), "Truncated NPY body")
        remaining -= len(block)
    require(member.read(1) == b"", "Trailing NPY bytes rejected")
    # Reading through EOF verifies every ZIP CRC before any np.load allocation.


def _read(path, n):
    path, before = _regular(path)
    with path.open("rb") as source:
        opened = os.fstat(source.fileno())
        require(_identity(before) == _identity(opened), "Candidate changed before opening")
        with zipfile.ZipFile(source) as archive:
            rows = archive.infolist()
            require(len(rows) == 2 and {r.filename for r in rows} == MEMBERS,
                    "Exactly two unique NPZ members required; no extra fields")
            require(all(r.file_size > 0 for r in rows)
                    and sum(r.file_size for r in rows) <= MAX_EXPANDED_BYTES,
                    "Expanded ZIP cap exceeded")
            for row in rows:
                require(not row.is_dir() and not row.flag_bits & 1
                        and stat.S_IFMT(row.external_attr >> 16) in (0, stat.S_IFREG)
                        and row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                        "Linked, encrypted or unsupported ZIP member")
                with archive.open(row) as member:
                    _header(member, row.filename, n, row.file_size)
        source.seek(0)
        with np.load(source, allow_pickle=False) as bundle:
            require(set(bundle.files) == {"case_id", "prediction_ms"}, "Loaded fields differ from preflight")
            result = {key: bundle[key] for key in bundle.files}
        require(_identity(opened) == _identity(os.fstat(source.fileno())), "Candidate changed during validation")
        require(not path.is_symlink() and _identity(opened) == _identity(path.lstat()),
                "Candidate path changed during validation")
    return result


def validate(path, expected_ids):
    """Return one float64 vector in the verified public panel's identity order.

Production caller must pin the 258-case public identity file and require its
complete list. Smaller generated panels are supported only for qualification.
All finite float32/64 values, including negatives, are allowed without clipping.
"""
    try:
        expected = public_ids(expected_ids)
        candidate = _read(path, len(expected))
        ids = candidate["case_id"].tolist()
        require(all(canonical_id(x) for x in ids) and len(set(ids)) == len(ids)
                and set(ids) == set(expected),
                "Exact complete expected case IDs required; no missing, extra or duplicate IDs")
        p = candidate["prediction_ms"]
        require(p.shape == (len(expected),) and p.dtype.kind == "f"
                and p.dtype.itemsize in (4, 8) and np.isfinite(p).all(),
                "One finite float32/64 prediction per case required")
        positions = {name: i for i, name in enumerate(ids)}
        return p[[positions[name] for name in expected]].astype(np.float64, copy=True)
    except InvalidSubmission:
        raise
    except (OSError, ValueError, TypeError, KeyError, EOFError, RuntimeError,
            zipfile.BadZipFile, NotImplementedError, struct.error) as exc:
        raise InvalidSubmission("Malformed or unreadable candidate NPZ") from exc


def validate_and_score(path, expected_ids, private_loader, reference_scores):
    """Public validation precedes one trusted, hash-verifying private load.

The private loader must verify the pinned file and return the exact fields
case_id/tp_ms/condition/context. This wrapper additionally checks its ID order.
"""
    expected = public_ids(expected_ids)
    ordered = validate(path, expected)
    def joined_loader():
        result = private_loader()
        require(isinstance(result, dict) and "case_id" in result
                and np.asarray(result["case_id"]).tolist() == expected,
                "Private/public identity order differs")
        return result
    from metrics import score_candidate
    return score_candidate(ordered, joined_loader, reference_scores)
