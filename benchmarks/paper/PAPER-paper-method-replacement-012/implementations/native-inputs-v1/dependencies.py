"""Authenticate the existing source split and readout implementation."""
import builtins
from functools import lru_cache
import hashlib
import os
from pathlib import Path
import stat
import sys
from types import ModuleType, SimpleNamespace
import uuid

PINS = {
    'source-splits-v2/inert_pickle.py': '54e089fe4622608463af31ccae804e62e77e1177af6a04bcb31f3c28e7790618',
    'source-splits-v2/source_splits.py': '31a0be5d7ab2ea950fd330d24de6467c00a9da03e9c78e68b02d51ae4e590fc2',
    'initial-evaluator-v1/evaluator.py': '36706ae9e37fcfeae0ed46740f3c5601c13052fe316ba164bf2d22f64aed6797',
}


class SourceError(ValueError):
    pass


def need(value, message):
    if not value:
        raise SourceError(message)


def identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def read_file(path, limit, sha256=None):
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as handle:
        before = os.fstat(handle.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= limit,
             'bounded ordinary unaliased file required')
        body = handle.read(limit + 1)
        need(identity(before) == identity(os.fstat(handle.fileno())) and len(body) == before.st_size <= limit,
             'file changed or exceeded byte limit')
    if sha256 is not None:
        need(hashlib.sha256(body).hexdigest() == sha256, 'file SHA256 differs: ' + Path(path).name)
    return body


def _module(path, body, namespace, imports):
    name = namespace + '.' + path.stem
    module = ModuleType(name)
    module.__file__, module.__package__ = str(path), namespace
    original = builtins.__import__

    def importer(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in imports:
            return imports[name]
        return original(name, globals, locals, fromlist, level)

    module.__dict__['__builtins__'] = dict(vars(builtins), __import__=importer)
    sys.modules[name] = module
    try:
        exec(compile(body, str(path), 'exec'), module.__dict__)
    except BaseException:
        del sys.modules[name]
        raise
    return module


@lru_cache(maxsize=1)
def load_dependencies():
    root = Path(__file__).resolve().parents[1]
    bodies = {name: read_file(root / name, 1024 * 1024, sha) for name, sha in PINS.items()}
    namespace = '_nuclr_input_source_' + uuid.uuid4().hex
    inert = _module(root / 'source-splits-v2/inert_pickle.py', bodies['source-splits-v2/inert_pickle.py'], namespace, {})
    splits = _module(root / 'source-splits-v2/source_splits.py', bodies['source-splits-v2/source_splits.py'], namespace,
                     {'inert_pickle': inert})
    evaluator = _module(root / 'initial-evaluator-v1/evaluator.py', bodies['initial-evaluator-v1/evaluator.py'], namespace, {})
    # Keep all later topology/selection checks on the authenticated module.
    # The historical on-disk source is unchanged; this private loaded instance
    # must not reopen a mutable path through its original importlib helper.
    splits._evaluator = lambda: evaluator
    return SimpleNamespace(splits=splits, evaluator=evaluator, pins=dict(PINS))
