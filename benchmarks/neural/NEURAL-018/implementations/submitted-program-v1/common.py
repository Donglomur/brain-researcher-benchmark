"""Source and file boundaries for the original finite NEURAL-018 programme."""
import hashlib
import json
import os
from pathlib import Path
import stat

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
SCORER = HERE.parent / 'registered-runtime/scoring-v2'
MAX_OUTPUT = 34 * 1024**2
PUBLIC = {'past': '/input/past.npz', 'training_future': '/input/training_future.npz',
          'manifest': '/input/public_manifest.json'}


def need(value, message):
    if not value:
        raise ValueError(message)


def pairs(rows):
    result = {}
    for key, value in rows:
        need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def decode(body):
    return json.loads(body.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON')))


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def ordinary(path):
    path = Path(os.path.abspath(path))
    need(all(not item.is_symlink() for item in (path, *path.parents)), 'Unlinked file and ancestors')
    return path


def fingerprint(value):
    return (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns)


def capture(path, cap, expected=None):
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded ordinary single-link file')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(before.st_size + 1)
        need(len(body) == before.st_size and fingerprint(before) == fingerprint(os.fstat(fd)),
             'File changed during capture')
        need(expected is None or pin(body) == expected, 'Frozen byte identity differs')
        return body
    finally:
        os.close(fd)


def prepare_grader_prediction(path, expected):
    """Authenticate the stopped capture and make only it readable to UID 65534."""
    path = ordinary(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and before.st_uid == os.geteuid() and 0 < before.st_size <= MAX_OUTPUT,
             'Owned bounded single-link prediction')
        digest = hashlib.sha256()
        count = 0
        while count <= before.st_size:
            block = os.read(fd, min(1024**2, before.st_size + 1 - count))
            if not block:
                break
            digest.update(block)
            count += len(block)
        identity = {'bytes': count, 'sha256': digest.hexdigest()}
        need(count == before.st_size and identity == expected,
             'Frozen prediction identity differs before grader access')
        need(fingerprint(before) == fingerprint(os.fstat(fd))
             == fingerprint(os.stat(path, follow_symlinks=False)),
             'Prediction changed before permission finalization')
        os.fchmod(fd, 0o444)
        os.fsync(fd)
        after = os.fstat(fd)
        need(fingerprint(before)[:4] == fingerprint(after)[:4]
             and stat.S_ISREG(after.st_mode) and after.st_nlink == 1
             and after.st_uid == os.geteuid() and stat.S_IMODE(after.st_mode) == 0o444
             and fingerprint(after) == fingerprint(os.stat(path, follow_symlinks=False)),
             'Exact prediction descriptor and public mode after finalization')
        return identity
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
    raw = capture(HERE / 'SOURCE.json', 65536, expected)
    manifest = decode(raw)
    need(manifest['schema'] == 'neural018_submitted_program_source_v1', 'Exact source version')
    for relative, identity in manifest['files'].items():
        path = Path(relative)
        need(not path.is_absolute() and '..' not in path.parts, 'Repository source path')
        capture(REPO / path, 1048576, identity)
    return pin(raw)


def assets():
    return decode(capture(SCORER / 'assets.json', 32768))


def file_mount(path, identity, purpose):
    path = ordinary(path)
    return {'path': str(path), 'kind': 'file', 'purpose': purpose, 'files': {path.name: identity}}
