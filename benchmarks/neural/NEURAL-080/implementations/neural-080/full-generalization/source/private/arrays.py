"""Strict ordinary-file primitive NPY boundary; same captured bytes are hashed/decoded."""
import hashlib
import io
import numpy as np
from io_contract import capture


def decode(body, shape, kinds="f", max_bytes=20_000_000):
    if len(body) > max_bytes:
        raise ValueError("Array exceeds byte bound")
    f = io.BytesIO(body)
    version = np.lib.format.read_magic(f)
    if version == (1, 0):
        actual, fortran, dtype = np.lib.format.read_array_header_1_0(f)
    elif version == (2, 0):
        actual, fortran, dtype = np.lib.format.read_array_header_2_0(f)
    else:
        raise ValueError("Only NPY v1/v2 primitive arrays supported")
    if tuple(actual) != tuple(shape) or fortran or dtype.hasobject or dtype.kind not in kinds:
        raise ValueError("Wrong shape, order or primitive dtype")
    if dtype.kind == "f" and dtype.itemsize not in (4, 8):
        raise ValueError("Only float32/float64 supported")
    size = int(np.prod(shape)) * dtype.itemsize
    if len(body) - f.tell() != size:
        raise ValueError("Trailing, truncated or falsely declared NPY body")
    out = np.frombuffer(body, dtype=dtype, count=int(np.prod(shape)), offset=f.tell()).reshape(shape)
    if not np.isfinite(out).all():
        raise ValueError("Nonfinite array values")
    return out


def load(path, descriptor, shape, max_bytes=20_000_000, *, owner=None):
    body = capture(path, max_bytes,owner=owner)
    if descriptor is not None and (len(body) != descriptor["bytes"] or
            hashlib.sha256(body).hexdigest() != descriptor["sha256"]):
        raise ValueError("Array identity mismatch")
    return decode(body, shape, max_bytes=max_bytes)
