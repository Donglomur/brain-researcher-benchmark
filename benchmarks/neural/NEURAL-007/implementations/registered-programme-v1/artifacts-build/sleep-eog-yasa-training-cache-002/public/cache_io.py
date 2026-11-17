"""Bounded stored-NPZ IO for the common observation interface; no targets/models."""
import ast
import hashlib
import io
import math
import os
from pathlib import Path
import re
import stat
import zipfile

import numpy as np
import cache_core as core

MAX_FILE_BYTES = 8_000_000
MAX_HEADER_BYTES = 4096


def need(value):
    if not value:
        raise ValueError("invalid_shared_yasa_observation_file")


def fingerprint(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_nlink)


def locked_bytes(path, lock):
    """Read a trusted size/hash lock without following linked inputs or parents."""
    need(type(lock) is dict and set(lock) == {"bytes", "sha256"}
         and type(lock["bytes"]) is int and 0 < lock["bytes"] <= MAX_FILE_BYTES
         and type(lock["sha256"]) is str
         and re.fullmatch(r"[0-9a-f]{64}", lock["sha256"]) is not None)
    path = Path(os.path.abspath(path))
    need(all(not parent.is_symlink() for parent in (path, *path.parents)))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_size == lock["bytes"])
        chunks, remaining = [], lock["bytes"]
        while remaining:
            block = os.read(fd, min(131072, remaining))
            need(bool(block))
            chunks.append(block)
            remaining -= len(block)
        need(os.read(fd, 1) == b"" and fingerprint(os.fstat(fd)) == fingerprint(before))
    finally:
        os.close(fd)
    data = b"".join(chunks)
    need(hashlib.sha256(data).hexdigest() == lock["sha256"])
    return data


def inspect_headers(data, layout):
    """No array loading until every member's geometry and byte count has passed.

    layout maps a key to (exact shape, exact NPY dtype descriptor, exact order).
    The boolean order is True for F and False for C, not a permissive choice.
    NPY header
    bytes are bounded before literal parsing; no pickle or dtype expressions.
    """
    need(type(data) is bytes and 0 < len(data) <= MAX_FILE_BYTES
         and type(layout) is dict and 1 <= len(layout) <= 8)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        entries = archive.infolist()
        need(not archive.comment and len(entries) == len(layout)
             and {e.filename for e in entries} == {k + ".npy" for k in layout})
        total = 0
        for entry in entries:
            mode = stat.S_IFMT(entry.external_attr >> 16)
            need(not entry.is_dir() and mode in (0, stat.S_IFREG)
                 and not entry.flag_bits & (1 | 8)
                 and entry.compress_type == zipfile.ZIP_STORED
                 and entry.file_size == entry.compress_size
                 and not entry.comment and 0 < entry.file_size <= MAX_FILE_BYTES)
            total += entry.file_size
            need(total <= MAX_FILE_BYTES)
            expected_shape, expected_dtype, expected_fortran = layout[entry.filename[:-4]]
            need(type(expected_fortran) is bool)
            with archive.open(entry) as stream:
                magic = stream.read(8)
                need(magic in (b"\x93NUMPY\x01\x00", b"\x93NUMPY\x02\x00"))
                prefix_length = 2 if magic[-2:] == b"\x01\x00" else 4
                length_bytes = stream.read(prefix_length)
                need(len(length_bytes) == prefix_length)
                length = int.from_bytes(length_bytes, "little")
                need(0 < length <= MAX_HEADER_BYTES)
                encoded = stream.read(length)
                need(len(encoded) == length and encoded.endswith(b"\n"))
                header = ast.literal_eval(encoded.decode("latin1"))
                need(type(header) is dict and set(header) == {"descr", "fortran_order", "shape"})
                shape, descr = header["shape"], header["descr"]
                need(type(shape) is tuple and all(type(n) is int and n >= 0 for n in shape)
                     and shape == expected_shape and header["fortran_order"] is expected_fortran
                     and type(descr) is str and descr == expected_dtype
                     and re.fullmatch(r"<f8|<U[1-9][0-9]{0,2}", descr) is not None)
                itemsize = 8 if descr == "<f8" else 4 * int(descr[2:])
                size = math.prod(shape) * itemsize
                need(size <= MAX_FILE_BYTES and stream.tell() + size == entry.file_size)


def load_layout(path, lock, layout):
    data = locked_bytes(path, lock)
    inspect_headers(data, layout)
    # All members, including the last one, passed before any ndarray allocation.
    with np.load(io.BytesIO(data), allow_pickle=False, max_header_size=MAX_HEADER_BYTES) as archive:
        arrays = {name: archive[name] for name in layout}
    return arrays


def cache_layout(case_id, epochs):
    core.canonical_ids(case_id, epochs)  # Bounded public schema check.
    return {"epoch_id": ((epochs,), "<U" + str(len(case_id) + 6), False),
            "class_order": ((5,), "<U2", False),
            "component_order": ((4,), "<U11", False),
            "component_probabilities": ((epochs, 4, 5), "<f8", False)}


def load_cache(path, lock, case_id, epochs):
    values = load_layout(path, lock, cache_layout(case_id, epochs))
    core.validate_cache(values, case_id, epochs)
    return values


def digest(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write_cache(path, values, case_id, epochs):
    """Trusted fresh operator directory only; no overwrites; verify round trip."""
    core.validate_cache(values, case_id, epochs)
    path = Path(path)
    need(all(not parent.is_symlink() for parent in (path, *path.parents)))
    # Assemble and check the complete stored archive before creating its output.
    buffer = io.BytesIO()
    # Output storage is canonical C; logical dtype/shape/value bytes stay exact.
    np.savez(buffer, **{key: np.ascontiguousarray(value) for key, value in values.items()})
    data = buffer.getvalue()
    inspect_headers(data, cache_layout(case_id, epochs))
    lock = digest(data)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    restored = load_cache(path, lock, case_id, epochs)
    need(all(restored[key].dtype == values[key].dtype and restored[key].shape == values[key].shape
             and restored[key].tobytes(order="C") == values[key].tobytes(order="C") for key in core.FIELDS))
    path.chmod(0o444)
    return lock


def load_qualified_development(path, lock):
    # Exact saved source layout independently observed from NPY headers:
    # four components + two ensembles are F; IDs and the anchor are C.
    layout = {"epoch_id": ((5450,), "<U21", False),
              **{"prob_" + name: ((5450, 5), "<f8", name != "Fpz_EEG_EOG_anchor")
                 for name in core.VIEWS}}
    arrays = load_layout(path, lock, layout)
    return core.split_qualified_development(arrays["epoch_id"],
        {name: arrays["prob_" + name] for name in core.VIEWS}, core.CLASSES)
