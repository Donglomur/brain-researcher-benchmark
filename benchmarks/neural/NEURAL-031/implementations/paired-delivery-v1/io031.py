"""Small bounded operator I/O; this module is not a participant sandbox."""
import hashlib
import io
import json
import os
from pathlib import Path
import re
import stat
import zipfile


def need(value, message):
    if not value:
        raise ValueError(message)


def unique(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, 'Duplicate JSON key')
        result[key] = value
    return result


def decode(body):
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def descriptor(value, cap):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
         type(value['bytes']) is int and 0 < value['bytes'] <= cap and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'Exact bounded content descriptor')
    return value


def read(path, cap, expected=None):
    if expected is not None:
        descriptor(expected, cap)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        need(stat.S_ISREG(info.st_mode) and 0 < info.st_size <= cap, 'Bounded regular file')
        body = stream.read(cap + 1)
        need(len(body) == info.st_size and len(body) <= cap, 'Stable bounded file extent')
    if expected is not None:
        need(pin(body) == expected, 'Exact expected file bytes and SHA-256')
    return body


def join(root, relative):
    """Fixed operator-relative paths, rejecting symlinks below the source root."""
    root = Path(root)
    need(root.is_dir() and not root.is_symlink(), 'Ordinary source root')
    parts = Path(relative).parts
    need(parts and not Path(relative).is_absolute() and all(p not in ('.', '..') for p in parts),
         'Fixed relative source path')
    current = root
    for part in parts:
        current = current / part
        need(not current.is_symlink(), 'No symlink source component')
    return current


def archive(np, values):
    need(all(type(v) is np.ndarray and not v.dtype.hasobject for v in values.values()),
         'Nonobject arrays only')
    stream = io.BytesIO()
    np.savez(stream, **values)
    return stream.getvalue()


def arrays(np, body, keys):
    # Pins are checked before this function. Bound inflated entry extents too.
    with zipfile.ZipFile(io.BytesIO(body)) as z:
        names = [key + '.npy' for key in keys]
        need(sorted(z.namelist()) == sorted(names), 'Exactly six numeric arrays')
        need(all(0 < i.file_size <= 65536 and i.compress_type in
                 (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED) for i in z.infolist()),
             'Bounded archive expansion')
    with np.load(io.BytesIO(body), allow_pickle=False) as z:
        result = {key: z[key] for key in keys}
    need(all(type(v) is np.ndarray and v.dtype.kind in 'fiu' and not v.dtype.hasobject and
             v.ndim <= 2 and v.size <= 6858 for v in result.values()), 'Bounded numeric arrays')
    return result


class Writer:
    def __init__(self, root, cap):
        self.root, self.cap, self.used, self.files = Path(root), cap, 0, {}
        self.root.mkdir(mode=0o700, parents=False, exist_ok=False)

    def write(self, relative, body, cap):
        need(0 < len(body) <= cap and self.used + len(body) <= self.cap,
             'Per-file and cumulative output bounds')
        path = self.root / relative
        need(not Path(relative).is_absolute() and '..' not in Path(relative).parts,
             'Relative output name')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        path.chmod(0o444)
        self.used += len(body)
        self.files[relative] = pin(body)
        return self.files[relative]
