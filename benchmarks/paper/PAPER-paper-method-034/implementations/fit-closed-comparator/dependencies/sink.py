"""Streaming quarantine receiver; publication belongs to the closed parent phase."""
import hashlib
import json
import os
from pathlib import Path
import re
import time
import unicodedata

MAGIC = b'MARBLE-BUNDLE-1\n'


def need(ok, message):
    if not ok:
        raise ValueError(message)


class Receiver:
    def __init__(self, root, spec, deadline, clock=time.monotonic):
        self.root = Path(root); self.spec = spec; self.deadline = deadline; self.clock = clock
        need(self.root.is_absolute() and not os.path.lexists(self.root)
             and not any(p.is_symlink() for p in (self.root, *self.root.parents)), 'Fresh ordinary quarantine required')
        self.root.mkdir(mode=0o700)
        self.buffer = bytearray(); self.magic = False; self.ended = False
        self.total = self.payload = self.state_bytes = 0
        self.files = []; self.directories = []; self.names = set(); self.current = None

    def guard(self):
        need(self.clock() < self.deadline, 'Original phase deadline includes quarantine')

    def path(self, value):
        need(type(value) is str and value and len(value.encode('utf8')) <= 1024 and '\\' not in value
             and '\x00' not in value and not value.startswith('/')
             and all(x not in ('', '.', '..') for x in value.split('/')), 'Canonical output path required')
        need(value in ('embeddings', 'state') or value.startswith(('embeddings/', 'state/')), 'Only selected roots')
        key = unicodedata.normalize('NFC', value).casefold()
        need(key not in self.names, 'No duplicate or spelling-alias output')
        self.names.add(key)
        parent = value.rsplit('/', 1)[0] if '/' in value else None
        need(parent is None or parent in self.directories, 'Parent directory must precede file')
        return self.root / value

    def feed(self, body):
        self.guard()
        need(type(body) is bytes and 0 < len(body) <= 65536 and not self.ended, 'Bounded nonempty stream chunk')
        self.total += len(body); need(self.total <= self.spec['stream_bytes'], 'Selected whole stream bound')
        self.buffer.extend(body)
        if not self.magic:
            if len(self.buffer) < len(MAGIC):
                return
            need(bytes(self.buffer[:len(MAGIC)]) == MAGIC, 'Exact framed stream identity')
            del self.buffer[:len(MAGIC)]; self.magic = True
        while self.buffer or self.current is not None:
            self.guard()
            if self.current is not None:
                row, handle, h, remain = self.current
                if remain:
                    if not self.buffer:
                        break
                    amount = min(len(self.buffer), remain)
                    data = bytes(self.buffer[:amount]); del self.buffer[:amount]
                    view = memoryview(data)
                    while view:
                        count = os.write(handle, view); need(count > 0, 'Complete quarantine write'); view = view[count:]
                    h.update(data); self.current[3] -= amount
                    continue
                need(h.hexdigest() == row['sha256'], 'Exact captured output hash')
                os.fsync(handle); os.close(handle); self.current = None
                self.files.append(row)
                continue
            newline = self.buffer.find(b'\n')
            if newline < 0:
                need(len(self.buffer) <= 8192, 'Bounded incomplete frame header'); break
            need(newline < 8192, 'Bounded frame header')
            raw = bytes(self.buffer[:newline]); del self.buffer[:newline + 1]
            def pairs(items):
                value = {}
                for key, item in items:
                    need(key not in value, 'No duplicate frame key'); value[key] = item
                return value
            row = json.loads(raw, object_pairs_hook=pairs)
            need(type(row) is dict and row.get('kind') in ('file', 'directory', 'end'), 'Typed frame required')
            if row['kind'] == 'end':
                need(set(row) == {'kind', 'files', 'directories', 'payload_bytes'}
                     and all(type(row[k]) is int for k in ('files', 'directories', 'payload_bytes'))
                     and row['files'] == len(self.files) and row['directories'] == len(self.directories)
                     and row['payload_bytes'] == self.payload and not self.buffer, 'Complete exact terminal frame')
                self.ended = True; break
            path = self.path(row.get('path'))
            if row['kind'] == 'directory':
                need(set(row) == {'kind', 'path'} and (row['path'] == 'embeddings'
                     or self.spec['phase'] == 'fit' and (row['path'] == 'state' or row['path'].startswith('state/'))),
                     'Only selected directories')
                path.mkdir(mode=0o700); self.directories.append(row['path'])
            else:
                need(set(row) == {'kind', 'path', 'bytes', 'sha256'} and type(row['bytes']) is int
                     and row['bytes'] >= 0 and type(row['sha256']) is str
                     and re.fullmatch('[0-9a-f]{64}', row['sha256']), 'Exact finite file identity')
                if row['path'].startswith('embeddings/'):
                    need(row['path'].count('/') == 1 and row['path'].split('/')[1] in self.spec['embeddings']
                         and 0 < row['bytes'] <= 20_000_000, 'Selected embedding file')
                else:
                    need(self.spec['phase'] == 'fit' and row['path'].startswith('state/'), 'Only fit state outputs')
                    self.state_bytes += row['bytes']; need(self.state_bytes <= self.spec['state_bytes'], 'State extent cap')
                self.payload += row['bytes']; need(self.payload <= self.spec['payload_bytes'], 'Payload extent cap')
                handle = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
                self.current = [row, handle, hashlib.sha256(), row['bytes']]
            state_count = sum(n.startswith('state/') for n in self.directories) + sum(
                r['path'].startswith('state/') for r in self.files)
            if self.current is not None and self.current[0]['path'].startswith('state/'):
                state_count += 1
            need(state_count <= self.spec['state_entries'], 'State entry cap')

    def finish(self):
        self.guard()
        need(self.magic and self.ended and not self.buffer and self.current is None, 'Complete stream required')
        need({x for x in self.directories if '/' not in x}
             == ({'embeddings', 'state'} if self.spec['phase'] == 'fit' else {'embeddings'}),
             'Complete exact phase output roots')
        need({r['path'].split('/')[1] for r in self.files if r['path'].startswith('embeddings/')}
             == set(self.spec['embeddings']), 'All four embeddings required')
        need(sum(r['bytes'] for r in self.files if r['path'].startswith('embeddings/')) <= 40_000_000,
             'Unchanged embedding bound')
        for name in sorted(self.directories, key=lambda x: x.count('/'), reverse=True) + ['']:
            fd = os.open(self.root / name, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        self.guard()
        return {'files': self.files, 'directories': self.directories,
                'payload_bytes': self.payload, 'stream_bytes': self.total}

    def close(self):
        if self.current is not None:
            os.close(self.current[1]); self.current = None
