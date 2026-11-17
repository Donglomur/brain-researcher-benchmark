"""Pinned local source conversion primitives; never import author Python code.

Restricted NumPy-pickle compatibility is an ingestion aid, not a sandbox.
Run this trusted preparer in an isolated operator environment with no secrets or
network. All source bytes must first match a separately reviewed publisher pin.
"""
import hashlib
import io
import json
import pickle
from pathlib import Path
import numpy as np


def verify_file(path, descriptor):
    p = Path(path)
    if type(descriptor) is not dict or not {'bytes', 'sha256'} <= set(descriptor):
        raise ValueError('reviewed byte/hash source descriptor required')
    expected = descriptor['bytes']
    digest = descriptor['sha256']
    if type(expected) is not int or expected <= 0 or type(digest) is not str or len(digest) != 64:
        raise ValueError('missing or malformed source pin')
    if p.is_symlink() or not p.is_file() or p.stat().st_size != expected:
        raise ValueError('ordinary source file with exact declared bytes required')
    h = hashlib.sha256()
    with p.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):h.update(chunk)
    if h.hexdigest() != digest:
        raise ValueError('source SHA256 mismatch')


class RestrictedNumpyUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        normalized = module.replace('numpy._core.', 'numpy.core.')
        allowed = {
            ('numpy', 'ndarray'): np.ndarray,
            ('numpy', 'dtype'): np.dtype,
            ('numpy.core.multiarray', '_reconstruct'): np._core.multiarray._reconstruct,
            ('numpy.core.multiarray', 'scalar'): np._core.multiarray.scalar,
            ('numpy.core.numeric', '_frombuffer'): np._core.numeric._frombuffer,
        }
        if (normalized, name) not in allowed:
            raise pickle.UnpicklingError('unapproved source pickle global')
        return allowed[(normalized, name)]

    def persistent_load(self, pid):
        raise pickle.UnpicklingError('persistent pickle references forbidden')


def read_source_dictionary(stream, *, maximum_bytes):
    raw = stream.read(maximum_bytes + 1)
    if len(raw) > maximum_bytes:
        raise ValueError('source member exceeds declared bound')
    wrapped = io.BytesIO(raw)
    version = np.lib.format.read_magic(wrapped)
    if version == (1, 0):shape, order, dtype = np.lib.format.read_array_header_1_0(wrapped, max_header_size=16384)
    elif version == (2, 0):shape, order, dtype = np.lib.format.read_array_header_2_0(wrapped, max_header_size=16384)
    else:raise ValueError('only reviewed NPYv1/v2 source wrappers supported')
    if shape != () or order is not False or dtype != np.dtype('O'):
        raise ValueError('source scalar object-array wrapper required')
    outer = RestrictedNumpyUnpickler(wrapped).load()
    if wrapped.read(1):raise ValueError('trailing bytes after source object')
    if type(outer) is not np.ndarray or outer.shape != () or outer.dtype != np.dtype('O'):
        raise ValueError('source scalar object result required')
    value = outer.item()
    if type(value) is not dict:raise ValueError('source dictionary required')
    return value


def safe_numeric(path, *, shape=None):
    arr = np.load(path, mmap_mode='r', allow_pickle=False)
    if type(arr) not in (np.ndarray, np.memmap) or arr.dtype.kind not in 'fiu' or (shape is not None and arr.shape != shape):
        raise ValueError('plain numeric array with exact declared shape required')
    return arr


def descriptor(path, root):
    p = Path(path);h = hashlib.sha256()
    with p.open('rb') as stream:
        while chunk := stream.read(1024 * 1024):h.update(chunk)
    return {'path': str(p.relative_to(root)), 'bytes': p.stat().st_size, 'sha256': h.hexdigest()}


def save_json(path, value):
    with Path(path).open('x') as stream:
        json.dump(value, stream, indent=2, allow_nan=False);stream.write('\n')
