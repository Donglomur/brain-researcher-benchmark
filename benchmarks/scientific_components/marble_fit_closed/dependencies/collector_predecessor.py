"""Trusted stopped-producer collector: opaque ordinary files, never state loads."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
import unicodedata

MAGIC = b'MARBLE-BUNDLE-1\n'


def need(ok, message):
    if not ok:
        raise ValueError(message)


def relative(name):
    need(type(name) is str and name and len(name.encode('utf8')) <= 1024
         and '\\' not in name and '\x00' not in name
         and not name.startswith('/') and all(x not in ('', '.', '..') for x in name.split('/')),
         'Canonical bounded relative output name required')
    return name


def normalized(name):
    return unicodedata.normalize('NFC', name).casefold()


def spec_check(spec):
    need(type(spec) is dict and set(spec) == {'phase', 'embeddings', 'state_bytes', 'state_entries',
         'stream_bytes', 'payload_bytes'}, 'Exact collector specification required')
    need(spec['phase'] in ('fit', 'query') and type(spec['embeddings']) is list
         and len(spec['embeddings']) == len(set(spec['embeddings'])) == 4, 'Four selected embeddings required')
    for name in spec['embeddings']:
        need(re.fullmatch(r'(clean|half)-(achilles|buddy|cicero|gatsby)-(train|test)-d(3|32)\.npy', name),
             'Fixed MARBLE embedding name required')
    for name in ('state_bytes', 'state_entries', 'stream_bytes', 'payload_bytes'):
        need(type(spec[name]) is int and 0 <= spec[name] <= 2**63 - 1, 'Selected finite integer bound required')
    need(spec['stream_bytes'] > 0 and spec['payload_bytes'] > 0, 'Positive transport bounds required')
    if spec['phase'] == 'query':
        need(spec['state_bytes'] == spec['state_entries'] == 0, 'No query state output permitted')


def scan(root, spec):
    spec_check(spec)
    root = Path(root)
    need(root.is_absolute() and not any(p.is_symlink() for p in (root, *root.parents)), 'Ordinary absolute root required')
    need(set(os.listdir(root)) == ({'embeddings', 'state'} if spec['phase'] == 'fit' else {'embeddings'}),
         'Exact output roots required')
    files = []; directories = []; seen = set(); total = state_bytes = state_entries = 0
    for directory, names, leaves in os.walk(root, followlinks=False):
        for name in sorted(names + leaves):
            path = Path(directory) / name
            rel = relative(path.relative_to(root).as_posix())
            key = normalized(rel)
            need(key not in seen, 'No filesystem spelling aliases')
            seen.add(key)
            s = path.lstat()
            if stat.S_ISDIR(s.st_mode):
                need(rel in ('embeddings', 'state') or rel.startswith('state/'), 'Only state subdirectories permitted')
                directories.append(rel)
            else:
                need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1, 'Single-link ordinary output file required')
                if rel.startswith('embeddings/'):
                    need(rel.count('/') == 1 and rel.split('/')[1] in spec['embeddings']
                         and 0 < s.st_size <= 20_000_000, 'Exact bounded embedding file required')
                else:
                    need(spec['phase'] == 'fit' and rel.startswith('state/'), 'Only fit state files permitted')
                    state_bytes += s.st_size
                total += s.st_size
                files.append((rel, s.st_size))
            if rel.startswith('state/'):
                state_entries += 1
            need(state_bytes <= spec['state_bytes'] and state_entries <= spec['state_entries']
                 and total <= spec['payload_bytes'], 'Selected complete output bounds')
    need({r.split('/')[1] for r, _ in files if r.startswith('embeddings/')} == set(spec['embeddings']),
         'All four embeddings required')
    need(sum(size for name, size in files if name.startswith('embeddings/')) <= 40_000_000,
         'Unchanged total embedding bound')
    return sorted(directories, key=lambda n: (n.count('/'), n)), sorted(files), total


def stamp(s):
    return tuple(getattr(s, k) for k in ('st_dev', 'st_ino', 'st_size', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns'))


def emit(root, spec, write):
    """One finite stream after producer removal; write is a bounded sink."""
    directories, files, payload = scan(root, spec)
    written = 0
    def send(body):
        nonlocal written
        need(written + len(body) <= spec['stream_bytes'], 'Selected collector stream cap')
        write(body); written += len(body)
    def header(value):
        body = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode() + b'\n'
        need(len(body) <= 8192, 'Bounded frame header')
        send(body)
    send(MAGIC)
    for name in directories:
        header({'kind': 'directory', 'path': name})
    for name, size in files:
        path = Path(root) / name
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb', buffering=0) as stream:
            before = os.fstat(stream.fileno())
            need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == size,
                 'Captured exact output extent')
            h = hashlib.sha256(); count = 0
            while True:
                body = stream.read(min(65536, size + 1 - count))
                if not body:
                    break
                count += len(body); need(count <= size, 'No output growth'); h.update(body)
            need(count == size and stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(path.lstat()),
                 'Stable output before framing')
            header({'kind': 'file', 'path': name, 'bytes': size, 'sha256': h.hexdigest()})
            stream.seek(0); second = hashlib.sha256(); count = 0
            while count < size:
                body = stream.read(min(65536, size - count)); need(body, 'Complete output second pass')
                send(body); second.update(body); count += len(body)
            need(not stream.read(1) and second.digest() == h.digest()
                 and stamp(before) == stamp(os.fstat(stream.fileno())) == stamp(path.lstat()),
                 'Unchanged complete output bytes')
    header({'kind': 'end', 'files': len(files), 'directories': len(directories), 'payload_bytes': payload})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True)
    parser.add_argument('--spec', required=True)
    args = parser.parse_args()
    need(args.root == '/output', 'Fixed keeper output root')
    spec = json.loads(args.spec)
    def write(body):
        view = memoryview(body)
        while view:
            count = os.write(1, view); need(count > 0, 'Complete stream write'); view = view[count:]
    emit(Path(args.root), spec, write)


if __name__ == '__main__':
    main()
