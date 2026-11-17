"""Public-only boundary for one arbitrary NEURAL-077 probability submission.

The two members are trial_ids.npy and target_probability.npy. ZIP and NPY
geometry, dtypes and expanded lengths are checked before np.load. This adapts
the bounded header/CRC approach in the qualified NEURAL-019 io_contract.py;
it does not import that package or require reference-family predictions.
"""
from __future__ import annotations

import ast
import math
import os
from pathlib import Path
import stat
import struct
import zipfile

import numpy as np


MAX_FILE_BYTES = 1024 * 1024
MAX_EXPANDED_BYTES = 1024 * 1024
MAX_HEADER_BYTES = 4096
MAX_ID_ITEMSIZE = 1024  # At most 256 Unicode code points per identity.
MAX_TRIALS_PER_CASE = 256
MEMBERS = {"trial_ids.npy", "target_probability.npy"}


class InvalidSubmission(ValueError):
    """Candidate failed the public boundary; private loading is forbidden."""


def require(condition, message):
    if not condition:
        raise InvalidSubmission(message)


def _public_ids(expected_ids_by_case):
    require(isinstance(expected_ids_by_case, dict) and len(expected_ids_by_case) == 2,
            "Exactly two expected development cases required")
    cases = {}
    combined = []
    for case, value in expected_ids_by_case.items():
        require(isinstance(case, str) and bool(case), "Nonempty public case name required")
        ids = np.asarray(value)
        require(ids.ndim == 1 and 2 <= len(ids) <= MAX_TRIALS_PER_CASE
                and ids.dtype.kind == "U" and 0 < ids.dtype.itemsize <= MAX_ID_ITEMSIZE,
                "Bounded one-dimensional public Unicode IDs required")
        names = ids.tolist()
        require(all(names) and len(set(names)) == len(names), "Unique nonempty public IDs required")
        cases[case] = names
        combined.extend(names)
    require(len(set(combined)) == len(combined), "Public IDs must be unique across both cases")
    return cases, combined


def _regular(path):
    path = Path(path).absolute()
    require(all(not item.is_symlink() for item in (path, *path.parents)),
            "Candidate and all ancestor paths must be unlinked")
    status = path.lstat()
    require(stat.S_ISREG(status.st_mode) and status.st_nlink == 1
            and 0 < status.st_size <= MAX_FILE_BYTES,
            "Nonempty bounded regular file with one hard link required")
    return path, status


def _identity(status):
    return (status.st_dev, status.st_ino, status.st_size, status.st_mtime_ns,
            status.st_ctime_ns, status.st_nlink)


def _header(member, member_name, n, declared_member_bytes):
    """Read the declared header length before allocating even the header string."""
    require(member.read(6) == b"\x93NUMPY", "NPY magic required")
    version = member.read(2)
    require(version in (b"\x01\x00", b"\x02\x00"), "Only NPY versions 1 and 2 accepted")
    width = 2 if version == b"\x01\x00" else 4
    encoded = member.read(width)
    require(len(encoded) == width, "Truncated NPY header length")
    length = struct.unpack("<H" if width == 2 else "<I", encoded)[0]
    require(1 <= length <= MAX_HEADER_BYTES and member.tell() + length <= declared_member_bytes,
            "Bounded complete NPY header required")
    raw = member.read(length)
    require(len(raw) == length and raw.endswith(b"\n"), "Complete newline-terminated NPY header required")
    try:
        header = ast.literal_eval(raw.decode("latin1"))
    except (SyntaxError, ValueError, UnicodeError, RecursionError) as exc:
        raise InvalidSubmission("Invalid NPY header literal") from exc
    require(isinstance(header, dict) and set(header) == {"descr", "fortran_order", "shape"},
            "Exact NPY header fields required")
    require(type(header["fortran_order"]) is bool and header["shape"] == (n,)
            and isinstance(header["shape"], tuple)
            and all(type(x) is int for x in header["shape"]),
            "Exact one-dimensional complete-case geometry required")
    require(isinstance(header["descr"], str) and len(header["descr"]) <= 32,
            "Simple bounded dtype descriptor required")
    try:
        dtype = np.dtype(header["descr"])
    except (TypeError, ValueError) as exc:
        raise InvalidSubmission("Invalid dtype") from exc
    require(not dtype.hasobject and dtype.fields is None and dtype.subdtype is None,
            "No object, structured or subarray dtype")
    if member_name == "trial_ids.npy":
        require(dtype.kind == "U" and 0 < dtype.itemsize <= MAX_ID_ITEMSIZE,
                "Bounded Unicode trial IDs required")
    else:
        require(dtype.kind == "f" and dtype.itemsize in (4, 8),
                "Probability dtype must be float32 or float64")
    remaining = n * dtype.itemsize
    require(member.tell() + remaining == declared_member_bytes,
            "Declared expanded member must equal header plus exact array bytes")
    while remaining:
        block = member.read(min(65536, remaining))
        require(bool(block), "Truncated NPY body")
        remaining -= len(block)
    # Draining every member also verifies its ZIP CRC before np.load.
    require(member.read(1) == b"", "Trailing NPY bytes rejected")


def _read_candidate(path, n):
    path, before = _regular(path)
    with path.open("rb") as source:
        opened = os.fstat(source.fileno())
        require(_identity(before) == _identity(opened), "Candidate changed before opening")
        with zipfile.ZipFile(source) as archive:
            rows = archive.infolist()
            require(len(rows) == 2 and {row.filename for row in rows} == MEMBERS,
                    "Exactly two unique NPZ members required; no extra fields")
            require(all(row.file_size > 0 for row in rows)
                    and sum(row.file_size for row in rows) <= MAX_EXPANDED_BYTES,
                    "Expanded ZIP cap exceeded")
            for row in rows:
                require(not row.is_dir()
                        and stat.S_IFMT(row.external_attr >> 16) in (0, stat.S_IFREG)
                        and not row.flag_bits & 1
                        and row.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                        "Linked, encrypted or unsupported ZIP member")
                with archive.open(row) as member:
                    _header(member, row.filename, n, row.file_size)
        source.seek(0)
        with np.load(source, allow_pickle=False) as bundle:
            require(set(bundle.files) == {"trial_ids", "target_probability"},
                    "Loaded NPZ fields differ from preflight")
            candidate = {key: bundle[key] for key in bundle.files}
        require(_identity(opened) == _identity(os.fstat(source.fileno())),
                "Candidate changed during validation")
        require(_identity(opened) == _identity(path.lstat()) and not path.is_symlink(),
                "Candidate path changed during validation")
    return candidate


def validate(path, expected_ids_by_case):
    """Return probabilities in each complete case's public ID order.

    Arbitrary candidate row reordering is allowed. The two expected ID vectors
    must come from a separately verified public packet. No private data is used.
    Returned float64 arrays preserve all submitted float32/64 values, including
    0 and 1. There is no clipping, normalization, threshold or score gate here.
    """
    try:
        cases, combined = _public_ids(expected_ids_by_case)
        candidate = _read_candidate(path, len(combined))
        ids = candidate["trial_ids"]
        probabilities = candidate["target_probability"]
        require(ids.shape == (len(combined),) and ids.dtype.kind == "U",
                "Complete one-dimensional Unicode identities required")
        names = ids.tolist()
        require(all(names) and len(set(names)) == len(names) and set(names) == set(combined),
                "Exact full expected ID union required; no duplicate/missing/extra trial")
        require(probabilities.shape == ids.shape and probabilities.dtype.kind == "f"
                and probabilities.dtype.itemsize in (4, 8)
                and np.isfinite(probabilities).all()
                and np.all((probabilities >= 0.0) & (probabilities <= 1.0)),
                "One finite float32/64 probability in [0,1] per trial required")
        position = {name: i for i, name in enumerate(names)}
        return {case: probabilities[[position[name] for name in expected]].astype(np.float64, copy=True)
                for case, expected in cases.items()}
    except InvalidSubmission:
        raise
    except (OSError, ValueError, TypeError, KeyError, EOFError, RuntimeError,
            zipfile.BadZipFile, NotImplementedError, struct.error) as exc:
        raise InvalidSubmission("Malformed or unreadable candidate NPZ") from exc


def validate_and_score(path, expected_ids_by_case, private_loader, reference_scores):
    """Finish both public cases before any private-loader invocation.

    The trusted private_loader(case) must pin and join labels to that case's
    expected public ID order before returning its integer label vector.
    """
    ordered = validate(path, expected_ids_by_case)
    from metrics import score_candidate
    return score_candidate(ordered, private_loader, reference_scores)
