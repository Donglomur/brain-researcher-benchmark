"""Exact bounded operator artifacts. No artifacts are written on import."""
import hashlib
import json
import os
from pathlib import Path
from cohort import require
from io_support import canonical_bytes, checked_bytes, authenticate_file, ordinary_file, identity


def write_json_fresh(path, value, budget):
    data = canonical_bytes(value)
    budget.charge("artifact_write", len(data))
    path = Path(path)
    require(path.parent.is_dir() and not path.parent.is_symlink(), "Fresh ordinary operator directory")
    with path.open("xb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    budget.check_clock()
    return {"path": str(path), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read_json_exact(path, pin, budget):
    return json.loads(checked_bytes(path, pin, budget))


def write_array_fresh(path, array, budget):
    import numpy as np
    require(isinstance(array, np.ndarray) and not array.dtype.hasobject, "Ordinary numeric artifact")
    # Precompute only the small header, not a second encoded copy of the payload.
    import io
    header = io.BytesIO()
    shape = array.shape
    np.lib.format.write_array_header_2_0(header, {"descr": np.lib.format.dtype_to_descr(array.dtype),
                                                "fortran_order": False, "shape": shape})
    header_bytes = header.getvalue()
    budget.charge("artifact_write", len(header_bytes) + array.nbytes)
    path = Path(path)
    require(path.parent.is_dir() and not path.parent.is_symlink(), "Ordinary operator directory")
    digest = hashlib.sha256()
    with path.open("xb") as stream:
        stream.write(header_bytes)
        digest.update(header_bytes)
        for start in range(0, len(array), 128):
            chunk = np.ascontiguousarray(array[start:start + 128]).tobytes()
            stream.write(chunk)
            digest.update(chunk)
        stream.flush()
        os.fsync(stream.fileno())
    budget.check_clock()
    return {"path": str(path), "bytes": len(header_bytes) + array.nbytes,
            "sha256": digest.hexdigest(), "shape": list(shape), "dtype": array.dtype.str}


def read_array_exact(path, pin, shape, budget, *, kinds="f", item_sizes=(4, 8)):
    import numpy as np
    first = authenticate_file(path, pin, budget)
    p, fd, before = ordinary_file(path, pin["bytes"])
    try:
        require(identity(before) == first, "Array changed between hash and header")
        with os.fdopen(fd, "rb", closefd=False) as stream:
            version = np.lib.format.read_magic(stream)
            require(version in ((1, 0), (2, 0)), "Supported ordinary NPY encoding")
            reader = np.lib.format.read_array_header_1_0 if version == (1, 0) else np.lib.format.read_array_header_2_0
            actual_shape, fortran, dtype = reader(stream, max_header_size=65536)
            require(actual_shape == tuple(shape) and not fortran and not dtype.hasobject and
                    dtype.kind in kinds and dtype.itemsize in item_sizes, "Exact typed bounded array header")
            count = 1
            for extent in shape:
                require(type(extent) is int and extent >= 0, "Declared array extent")
                count *= extent
            require(before.st_size == stream.tell() + count * dtype.itemsize, "Exact NPY body size")
        require(identity(os.fstat(fd)) == identity(p.lstat()) == first, "Stable header identity")
    finally:
        os.close(fd)
    # The qualified namespace must keep this file immutable during use. A memory
    # map avoids retaining all160 full matrices in operator RAM; after-use hashes
    # remain required at worker/whole-grader completion.
    array = np.load(path, allow_pickle=False, mmap_mode="r")
    require(identity(p.lstat()) == first, "Stable mapping identity")
    # The restricted evaluator deliberately rejects ndarray subclasses. This is
    # a plain readonly ndarray view, not a copy and not a writable reinterpretation;
    # its base retains the map and the independent immutable-file requirement.
    plain = np.asarray(array)
    require(type(plain) is np.ndarray and not plain.flags.writeable, "Readonly plain mapped array view")
    return plain
