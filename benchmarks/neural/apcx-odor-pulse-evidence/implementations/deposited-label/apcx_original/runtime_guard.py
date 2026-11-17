"""Pin the existing local Arrow/NumPy distribution before native imports.

No package installation or native imports occur on importing this project file.
OS loader/stdlib/transitive system libraries remain the stated trusted host;
this is a fixed construction runtime, not an adversarial candidate sandbox.
"""
import base64
import hashlib
import importlib.abc
import importlib.machinery
import importlib
import os
from pathlib import Path
import platform
import sys

from .native_io import hash_regular, ordinary


def verify_runtime(manifest, budget):
    base = Path(manifest['site_packages']); known = set(); observed = []
    for package in manifest['packages']:
        pin = package['record']
        got = hash_regular(Path(pin['path']), pin['bytes'], budget, 'runtime_bytes')
        if got['sha256'] != pin['sha256']: raise ValueError('installed RECORD changed')
        for item in package['files']:
            relative = Path(item['path'])
            if relative.is_absolute() or '..' in relative.parts: raise ValueError('closed package root')
            p = base / relative
            if p in known: raise ValueError('duplicate runtime member')
            known.add(p)
            got = hash_regular(p, item['bytes'], budget, 'runtime_bytes')
            algorithm, expected = item['hash'].split('=', 1)
            encoded = base64.urlsafe_b64encode(bytes.fromhex(got['sha256'])).decode().rstrip('=')
            if algorithm != 'sha256' or encoded != expected: raise ValueError('installed runtime identity mismatch: ' + item['path'])
            observed.append({'path': str(p), 'bytes': got['bytes'], 'sha256': got['sha256']})
    return known, {'files_verified': len(observed), 'bytes_verified': sum(x['bytes'] for x in observed),
                   'identity_digest': hashlib.sha256(('\n'.join(x['path'] + ':' + x['sha256'] for x in observed)).encode()).hexdigest()}


class ClosedPackageFinder(importlib.abc.MetaPathFinder):
    def __init__(self, allowed): self.allowed = {str(p) for p in allowed}
    def find_spec(self, fullname, path=None, target=None):
        top = fullname.split('.', 1)[0]
        if top in sys.stdlib_module_names: return None
        if top not in ('pyarrow', 'numpy'): raise ModuleNotFoundError('unselected third-party import: ' + fullname)
        spec = importlib.machinery.PathFinder.find_spec(fullname, path, target)
        if spec is None or spec.origin not in self.allowed:
            raise ModuleNotFoundError('runtime import outside exact pinned files: ' + fullname)
        return spec


def activate(manifest, allowed, output):
    if sys.platform not in ('darwin', 'linux') or tuple(sys.version_info[:3]) != (3, 11, 6):
        raise ValueError('CPython3.11.6 POSIX runtime required')
    expected = manifest['portable_host']
    if expected != {'sys_platform': sys.platform, 'machine': platform.machine(), 'python': platform.python_version()}:
        raise ValueError('independently admitted runtime host identity mismatch')
    prefix = Path(output) / 'never-created-bytecode-cache'
    if prefix.exists() or prefix.is_symlink(): raise ValueError('fresh absent bytecode namespace')
    sys.dont_write_bytecode = True; sys.pycache_prefix = str(prefix)
    sys.meta_path.insert(0, ClosedPackageFinder(allowed))
    sys.path.insert(0, manifest['site_packages'])
    os.environ['OMP_NUM_THREADS'] = '1'; os.environ['OPENBLAS_NUM_THREADS'] = '1'
    os.environ['MKL_NUM_THREADS'] = '1'; os.environ['ARROW_NUM_THREADS'] = '1'
    pa = importlib.import_module('pyarrow'); pq = importlib.import_module('pyarrow.parquet')
    if pa.__version__ != '24.0.0': raise ValueError('exact existing PyArrow version')
    np = importlib.import_module('numpy')
    if np.__version__ != '2.4.6': raise ValueError('exact native-conversion NumPy version')
    pa.set_cpu_count(1); pa.set_io_thread_count(1)
    return pa, pq
