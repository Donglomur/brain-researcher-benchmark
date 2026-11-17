"""Task-local adapter over qualified ownership/budgets; no scientific imports."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / 'authoring/shared-program-runner-v2'))
from qualified_core import BaseEngine, HostBudget, DOCKER, ENV
from absence import absence
sys.path.insert(0, str(ROOT / 'authoring/shared-program-ownership-v3'))
import process_owner as owner


def need(ok, message):
    if not ok: raise ValueError(message)


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


legacy = module(ROOT / 'authoring/erp-neural-prediction-v1/reference-v1/runtime.py', '_choice_open_profile')
identity = module(ROOT / 'authoring/paper-language-project/phase1-numerical-v1/recovery_guard.py', '_choice_open_identity')


def strict(body):
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'Duplicate metadata key'); result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('Nonfinite JSON constant')))


def stamp(st):
    return tuple(getattr(st, key) for key in
                 ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns'))


def regular(path, cap, empty=False):
    path = Path(path).absolute()
    need('..' not in path.parts and all(not p.is_symlink() for p in (path, *path.parents)), 'Canonical ordinary file')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and (0 if empty else 1) <= before.st_size <= cap,
             'Bounded single-link file')
        with os.fdopen(fd, 'rb', closefd=False) as stream: body = stream.read(cap + 1)
        need(len(body) == before.st_size and stamp(before) == stamp(os.fstat(fd)) == stamp(path.lstat()), 'Stable complete bytes')
        return body
    finally:
        os.close(fd)


def lock(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def pin(path, cap=300000, empty=False):
    return lock(regular(path, cap, empty))


def descriptor(path, cap=300000):
    return {'path': str(Path(path).relative_to(ROOT)), **pin(path, cap)}


def pinned(value, cap=300000):
    need(type(value['path']) is str and not Path(value['path']).is_absolute() and '..' not in Path(value['path']).parts,
         'Relative exact metadata pin')
    body = regular(ROOT / value['path'], cap)
    need(lock(body) == {k: value[k] for k in ('bytes', 'sha256')}, 'Exact pinned metadata')
    return strict(body)


def sync(directory):
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)


def save(path, value, budget, cap=131072):
    body = (json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n').encode()
    need(len(body) <= cap, 'Compact bounded metadata writer')
    budget.write(path, body, receipt=True, mode=0o444)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try: os.fsync(fd)
    finally: os.close(fd)
    sync(Path(path).parent)
    return {'path': str(Path(path).relative_to(ROOT)), **lock(body)}


class Engine(BaseEngine):
    """Executed choice-reference fsync delta; shared qualified sources untouched."""
    def write(self, *args, **kwargs):
        path = super().write(*args, **kwargs)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try: os.fsync(fd)
        finally: os.close(fd)
        sync(Path(path).parent)
        return path

    def journal(self):
        super().journal()
        sync(self.out)


def assets():
    return strict(regular(HERE / 'ASSETS.json', 100000))


def output_hashes(folder, caps):
    """Opaque full-byte hashing/sealing only, including NPY; no array parsing."""
    folder = Path(folder); result = {}; total = 0
    for path in sorted(folder.iterdir()):
        name = path.name
        need(name in caps and not path.is_symlink(), 'Exact output filenames, no partial successful packet')
        value = pin(path, caps[name]); total += value['bytes']
        path.chmod(0o444); result[name] = value
    need(set(result) == set(caps), 'Complete declared output inventory')
    folder.chmod(0o555); sync(folder)
    return result, total
