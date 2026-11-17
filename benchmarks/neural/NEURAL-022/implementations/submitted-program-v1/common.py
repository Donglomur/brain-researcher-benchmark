"""Task-local source and ordinary-file boundaries; no scientific imports."""
import hashlib
import json
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
VENDOR = HERE.parent / 'artifact-grading/private/vendor'
PUBLIC = ('training.npz', 'queries.npz', 'cases.json', 'TASK.md')
PACKET = (*PUBLIC, 'reference.private.npz', 'receipt.json')
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'


def need(value, message):
    if not value:
        raise ValueError(message)


def pairs(rows):
    value = {}
    for key, item in rows:
        need(key not in value, 'Duplicate JSON key')
        value[key] = item
    return value


def decode(raw):
    return json.loads(raw.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def ordinary(path):
    path = Path(os.path.abspath(path))
    need(all(not p.is_symlink() for p in (path, *path.parents)), 'Unlinked path and ancestors')
    return path


def capture(path, cap, expected=None):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded ordinary single-link file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(before.st_size + 1)
        after = os.fstat(fd)
        fields = ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
        need(len(body) == before.st_size and all(getattr(before,k) == getattr(after,k) for k in fields),
             'File changed during capture')
        need(expected is None or pin(body) == expected, 'Exact frozen bytes required')
        return body
    finally:
        os.close(fd)


def publish(path, body, mode=0o400):
    path = ordinary(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        if mode == 0o444:
            os.fchmod(stream.fileno(), mode)
        os.fsync(stream.fileno())
    return pin(body)


def authenticate(expected):
    raw = capture(HERE/'SOURCE.json', 65536, expected)
    value = decode(raw)
    need(value['schema'] == 'neural022_submitted_program_source_v1', 'Exact source version')
    for relative, identity in value['files'].items():
        path = Path(relative)
        need(not path.is_absolute() and '..' not in path.parts, 'Repository source path')
        capture(REPO/path, 1048576, identity)
    return pin(raw)


def contract():
    return decode(capture(HERE/'original/CONTRACT.json', 65536))


def file_mount(path, identity, purpose):
    path = ordinary(path)
    return {'path':str(path), 'kind':'file', 'purpose':purpose, 'files':{path.name:identity}}


def scientific_mounts(entrypoint):
    """Explicit original scientific source files; no directory mount."""
    value = contract()
    names = value['entrypoint_sources'][entrypoint]
    mounts = {}
    for name in names:
        source = VENDOR/name if name in ('candidate.py','held_scorer.py','io_support.py','packet.py') else HERE/'original'/name
        mounts['/source/'+name] = file_mount(source, value['local_sources'][name], 'program')
    raw = capture(HERE/'original/CONTRACT.json',65536)
    mounts['/source/CONTRACT.json'] = file_mount(HERE/'original/CONTRACT.json',pin(raw),'contract')
    return mounts
