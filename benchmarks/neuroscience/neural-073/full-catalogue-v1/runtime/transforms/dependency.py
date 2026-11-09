"""Deferred, source-pinned NumPy access. No numerical import at module import time."""
from functools import lru_cache
from pathlib import Path
import hashlib
import importlib.metadata
import json
import sys


@lru_cache(maxsize=1)
def numpy_api():
    contract = json.loads(Path(__file__).with_name('NUMPY_API_CONTRACT.json').read_text())
    if tuple(sys.version_info[:2]) != tuple(contract['python_major_minor']):
        raise RuntimeError('NUMERICAL_DEPENDENCY_PYTHON_VERSION')
    dist = importlib.metadata.distribution(contract['package'])
    if dist.version != contract['version']:
        raise RuntimeError('NUMERICAL_DEPENDENCY_VERSION')
    base = Path(dist.locate_file('')).resolve()
    for item in contract['source_pins']:
        rel = Path(item['relative_distribution_root_path'])
        if rel.is_absolute() or '..' in rel.parts:
            raise RuntimeError('NUMERICAL_DEPENDENCY_PATH')
        path = base / rel
        if not path.is_file() or path.stat().st_size != item['bytes']:
            raise RuntimeError('NUMERICAL_DEPENDENCY_EXTENT')
        digest = hashlib.sha256()
        with path.open('rb') as f:
            for block in iter(lambda: f.read(65536), b''):
                digest.update(block)
        if digest.hexdigest() != item['sha256']:
            raise RuntimeError('NUMERICAL_DEPENDENCY_PIN')
    import numpy as np
    if Path(np.__file__).resolve() != (base/'numpy/__init__.py').resolve():
        raise RuntimeError('NUMERICAL_DEPENDENCY_IMPORTED_ORIGIN')
    if np.__version__ != contract['version']:
        raise RuntimeError('NUMERICAL_DEPENDENCY_IMPORTED_VERSION')
    return np
