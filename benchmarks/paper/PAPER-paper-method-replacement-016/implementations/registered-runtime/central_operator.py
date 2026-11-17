"""Inactive fixed-task bridge to the complete ordinary Four source package."""
import hashlib
import os
from pathlib import Path
import stat
import sys
from types import ModuleType

TASK = 'PAPER-paper-method-replacement-016'
SOURCE = (21412, '6f35ea43692f88eb8247f98c67fd350e4b78005c2fde63c2747e05ccf8b17f6f')
NAME = '_four_inactive_central_source_v1'

def _load():
    if not (sys.flags.isolated and sys.dont_write_bytecode):
        raise RuntimeError('source entry requires a fresh python -I -B host')
    root = Path(__file__).absolute().parent.parent / '_four_programmes_source_v1'
    path = root / 'central_source.py'
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError('ordinary installed source ancestry')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not (stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == SOURCE[0]):
            raise RuntimeError('exact central source extent')
        raw = bytearray()
        while len(raw) < SOURCE[0]:
            b = os.read(fd, min(65536, SOURCE[0] - len(raw)))
            if not b:raise RuntimeError('complete central source')
            raw.extend(b)
        after = os.fstat(fd)
        if os.read(fd, 1) or (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise RuntimeError('unchanged central source')
        if hashlib.sha256(raw).hexdigest() != SOURCE[1]:raise RuntimeError('exact central source identity')
    finally:os.close(fd)
    existing = sys.modules.get(NAME)
    if existing is not None:
        if type(existing) is not ModuleType or vars(existing).get('__file__') != str(path) or vars(existing).get('_CENTRAL_SOURCE_ID') != SOURCE:
            raise RuntimeError('no foreign central module alias')
        return existing
    module = ModuleType(NAME)
    module.__file__ = str(path)
    module._CENTRAL_SOURCE_ID = SOURCE
    sys.modules[NAME] = module
    try:exec(compile(bytes(raw), str(path), 'exec'), module.__dict__)
    except BaseException:
        if sys.modules.get(NAME) is module:del sys.modules[NAME]
        raise
    return module

_SOURCE = _load()

class HostRuntime(_SOURCE.HostRuntime):
    def __init__(self):super().__init__(TASK)

def inspect():return _SOURCE.inspect_source(TASK)

if __name__ == '__main__':raise SystemExit(_SOURCE.main(TASK))
