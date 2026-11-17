"""Exact canonical float32 windows; no numerical conversion is permitted."""
import hashlib
import os
from pathlib import Path
import stat
import numpy as np

REPRESENTATION = "float32-le-c-order-62x301-v1"
WINDOW_SHAPE = (62, 301)
WINDOW_BYTES = 62 * 301 * 4


class ViewError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ViewError(message)


def sha256(body):
    return hashlib.sha256(body).hexdigest()


def encode_window(array):
    require(type(array) is np.ndarray, "window must be an ordinary ndarray")
    require(array.dtype.str == "<f4" and array.shape == WINDOW_SHAPE,
            "window requires exact little-endian float32 shape62x301")
    require(np.isfinite(array).all(), "window must be finite")
    # Snapshot once. C-order denotes logical element order, not memory layout.
    # tobytes does not cast, normalize signed zero or flush subnormal values.
    body = array.tobytes(order="C")
    require(len(body) == WINDOW_BYTES, "window extent")
    # Check the actual immutable snapshot as well as the source view.
    require(np.isfinite(np.frombuffer(body, dtype="<f4")).all(), "snapshot must be finite")
    return body


def decode_window(body):
    require(type(body) is bytes and len(body) == WINDOW_BYTES, "canonical window extent/type")
    array = np.frombuffer(body, dtype="<f4").reshape(WINDOW_SHAPE)
    require(np.isfinite(array).all(), "canonical window must be finite")
    require(not array.flags.writeable, "immutable byte-backed view required")
    return array


def safe_path(path):
    path = Path(path).absolute()
    require(not any(p.is_symlink() for p in (path, *path.parents)), "symlink path refused")
    return path


def read_regular(path, max_bytes, *, expected_bytes=None, expected_sha256=None):
    require(type(max_bytes) is int and max_bytes > 0, "explicit positive read ceiling")
    path = safe_path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1,
                "single-link ordinary file required")
        require(0 <= before.st_size <= max_bytes, "file exceeds selected ceiling")
        if expected_bytes is not None:
            require(type(expected_bytes) is int and before.st_size == expected_bytes, "file extent mismatch")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            body = stream.read(before.st_size + 1)
        after, current = os.fstat(fd), path.lstat()
        attrs = ("st_dev", "st_ino", "st_mode", "st_nlink", "st_size", "st_mtime_ns", "st_ctime_ns")
        require(all(getattr(before, k) == getattr(after, k) == getattr(current, k) for k in attrs),
                "file changed during capture")
    finally:
        os.close(fd)
    require(len(body) == before.st_size, "captured file extent mismatch")
    if expected_sha256 is not None:
        require(sha256(body) == expected_sha256, "captured file digest mismatch")
    return body
