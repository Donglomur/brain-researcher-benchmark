"""Small task-local file and source bindings; no candidate execution."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
ARMS = ('EEG_clock', 'EEG_EOG_clock')
CASES = dict(zip(('train-001', 'train-002', 'train-003', 'train-004', 'train-005', 'train-006',
                 'development-001', 'development-002'), (2630, 2740, 2690, 2740, 2740, 2750, 2780, 2670)))
CLASSES = ['W', 'N1', 'N2', 'N3', 'R']


def need(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def unique(pairs):
    out = {}
    for key, value in pairs:
        need(key not in out, 'Duplicate JSON key')
        out[key] = value
    return out


def decode(body):
    return json.loads(body.decode('utf-8'), object_pairs_hook=unique,
                      parse_constant=lambda _: need(False, 'Nonfinite JSON'))


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def ordinary(path):
    path = Path(os.path.abspath(path))
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'No linked path or parent')
    return path


def read(path, cap, expected=None):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded ordinary single-link file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        after = os.fstat(fd)
        need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
             (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
             and len(body) == before.st_size, 'Stable complete read')
        need(expected is None or pin(body) == expected, 'Exact file identity')
        return body
    finally:
        os.close(fd)


def publish(path, body):
    path = ordinary(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return pin(body)


def source(expected=None):
    raw = read(HERE / 'SOURCE.json', 32768, expected)
    manifest = decode(raw)
    need(manifest['schema'] == 'neural008_paired_program_source_v1', 'Exact source manifest')
    for name, identity in manifest['files'].items():
        need(not name.startswith('/') and '..' not in Path(name).parts, 'Repository-relative source')
        read(REPO / name, 1048576, identity)
    return pin(raw)


def scorer():
    path = HERE.parent / 'finite-paired-scorer' / 'score.py'
    spec = importlib.util.spec_from_file_location('neural008_finite_scorer', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def file_mount(path, expected, purpose='input'):
    path = ordinary(path)
    return {'path': str(path), 'kind': 'file', 'purpose': purpose, 'files': {path.name: expected}}
