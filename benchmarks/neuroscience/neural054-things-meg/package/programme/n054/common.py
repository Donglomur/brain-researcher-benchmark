"""Strict ordinary-file transport and data-only JSON. Never import candidate code."""
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat

class Refusal(ValueError):
    pass

def need(ok, message):
    if not ok:
        raise Refusal(message)

def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()

def encoded(value):
    """Canonical JSON in bounded encoder pieces; same bytes as canonical()."""
    for piece in json.JSONEncoder(sort_keys=True, separators=(',', ':'), allow_nan=False).iterencode(value):
        yield piece.encode()
    yield b'\n'

def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}

def digest(value):
    h = hashlib.sha256()
    for piece in encoded(value): h.update(piece)
    return h.hexdigest()

def stream_pin(path, ceiling):
    before = ordinary(path); need(before.st_size <= ceiling, 'Pinned stream ceiling')
    h = hashlib.sha256(); count = 0
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(65536), b''):
            count += len(b); need(count <= ceiling, 'Pinned stream grew'); h.update(b)
    after = ordinary(path)
    need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Changed stream')
    return {'bytes': count, 'sha256': h.hexdigest()}

def copy_verified(source, destination, ceiling, expected):
    """No full-body request copy; exact source extent and digest before admission."""
    before = ordinary(source); need(before.st_size == expected['bytes'] <= ceiling, 'Copy extent')
    h = hashlib.sha256(); count = 0
    with Path(source).open('rb') as src, Path(destination).open('xb') as dst:
        for b in iter(lambda: src.read(65536), b''):
            count += len(b); need(count <= ceiling, 'Copy ceiling'); dst.write(b); h.update(b)
        dst.flush(); os.fsync(dst.fileno())
    after = ordinary(source)
    need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Changed copy source')
    need({'bytes': count, 'sha256': h.hexdigest()} == expected, 'Copy identity')
    return expected

def exact(obj, keys):
    need(type(obj) is dict and set(obj) == set(keys), 'Unexpected or absent fields')

def number(v, lo=-1e100, hi=1e100):
    return type(v) in (int, float) and math.isfinite(v) and lo <= v <= hi

def relative(name):
    p = PurePosixPath(name)
    need(type(name) is str and name and not p.is_absolute() and str(p) == name,
         'Canonical relative path required')
    need(all(x not in ('', '.', '..') and x.casefold() != '.git' for x in p.parts), 'Forbidden path')
    need(not any(x.casefold() in ('targets', 'private-evaluation') for x in p.parts), 'Private namespace')
    return p

def ordinary(path):
    path = Path(path)
    for p in (path, *path.parents):
        need(not p.is_symlink(), 'Symlink path forbidden')
    s = path.stat()
    need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'Ordinary unique file required')
    return s

def read(path, ceiling=16 << 20, expected=None):
    s = ordinary(path)
    need(s.st_size <= ceiling, 'Read ceiling')
    b = Path(path).read_bytes()
    need(len(b) == s.st_size, 'Changed during read')
    if expected is not None:
        need(pin(b) == expected, 'Exact bytes mismatch')
    return b

def verify(path, expected, ceiling):
    before = ordinary(path)
    need(before.st_size == expected['bytes'] and before.st_size <= ceiling, 'Pinned stream extent')
    h = hashlib.sha256(); count = 0
    with Path(path).open('rb') as f:
        while True:
            b = f.read(65536)
            if not b: break
            count += len(b); need(count <= ceiling, 'Streaming read ceiling'); h.update(b)
    after = ordinary(path)
    need((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
         (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'Changed stream')
    need({'bytes': count, 'sha256': h.hexdigest()} == expected, 'Stream content mismatch')
    return expected


def load(path, ceiling=16 << 20, expected=None):
    def pairs(items):
        out = {}
        for k, v in items:
            need(k not in out, 'Duplicate JSON key')
            out[k] = v
        return out
    return json.loads(read(path, ceiling, expected), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(Refusal('Nonfinite JSON')))

def put(path, value, ceiling=16 << 20):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256(); count = 0
    with p.open('xb') as f:
        for b in encoded(value):
            count += len(b); need(count <= ceiling, 'Write ceiling')
            f.write(b); h.update(b)
        f.flush(); os.fsync(f.fileno())
    return {'bytes': count, 'sha256': h.hexdigest()}

def tree(root, byte_cap, file_cap):
    root = Path(root)
    need(root.is_dir() and not root.is_symlink(), 'Ordinary directory required')
    out = []
    total = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            path = Path(directory) / name
            relative(path.relative_to(root).as_posix())
            need(not path.is_symlink(), 'Directory alias forbidden')
        for name in files:
            path = Path(directory) / name
            rel = path.relative_to(root).as_posix()
            relative(rel)
            size = ordinary(path).st_size
            total += size
            need(total <= byte_cap and len(out) < file_cap, 'Tree quota')
            out.append({'path': rel, **stream_pin(path, byte_cap)})
    return sorted(out, key=lambda x: x['path'])

def same_tree(root, records, byte_cap, file_cap):
    need(tree(root, byte_cap, file_cap) == records, 'Frozen tree changed')

def probabilities(v):
    need(type(v) is list and len(v) == 27 and all(number(x, 0, 1) for x in v),
         'Exactly 27 independent finite Bernoulli probabilities')
    return v


def extent(root):
    """Metadata-only streaming accounting, including an already over-budget failed tree."""
    root = Path(root); need(root.is_dir() and not root.is_symlink(), 'Ordinary extent root')
    count = total = 0; stack = [os.scandir(root)]
    try:
        while stack:
            try: entry = next(stack[-1])
            except StopIteration: stack.pop().close(); continue
            path = Path(entry.path); relative(path.relative_to(root).as_posix())
            need(not entry.is_symlink(), 'Extent alias')
            if entry.is_dir(follow_symlinks=False): stack.append(os.scandir(path))
            else:
                total += ordinary(path).st_size; count += 1
    finally:
        for iterator in stack: iterator.close()
    return {'bytes': total, 'files': count}
