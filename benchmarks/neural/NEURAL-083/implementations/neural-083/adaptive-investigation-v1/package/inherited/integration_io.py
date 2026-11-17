"""Small bounded operator I/O. No scientific imports or implicit data operands."""
import contextlib
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time
import types


def need(value, message):
    if not value:
        raise ValueError(message)


def exact(value, fields):
    need(type(value) is dict and set(value) == set(fields), 'exact fields: ' + ','.join(fields))


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                       allow_nan=False) + '\n').encode('ascii')


def parse(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'duplicate JSON field')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'finite JSON'))


def pin(raw):
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def only_pin(value):
    out = {name: value[name] for name in ('bytes', 'sha256')}
    need(type(out['bytes']) is int and 0 < out['bytes'] <= 4_000_000,
         'bounded positive metadata/source extent')
    need(type(out['sha256']) is str and re.fullmatch('[a-f0-9]{64}', out['sha256']),
         'SHA256 pin')
    return out


def path(value):
    need(type(value) in (str, type(Path())), 'path operand')
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts and str(p) == os.path.normpath(str(p)),
         'normalized absolute path')
    need(not any(c in str(p) for c in ('\0', '\n', '\r', ',')), 'unambiguous path')
    return p


def descriptor(value, cap=4_000_000):
    exact(value, ('path', 'bytes', 'sha256'))
    path(value['path'])
    need(only_pin(value)['bytes'] <= cap, 'descriptor extent cap')
    return value


def stamp(s):
    return tuple(getattr(s, k) for k in
                 ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size',
                  'st_uid', 'st_gid', 'st_mtime_ns', 'st_ctime_ns'))


@contextlib.contextmanager
def held_parent(value):
    """Hold each existing ancestor; verify its name still selects that directory."""
    p = path(value)
    fds = [os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)]
    links = []
    try:
        for name in p.parts[1:-1]:
            parent = fds[-1]
            fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                         dir_fd=parent)
            fds.append(fd)
            links.append((parent, name, fd))
        def verify():
            for parent, name, fd in links:
                a, b = os.stat(name, dir_fd=parent, follow_symlinks=False), os.fstat(fd)
                need((a.st_dev, a.st_ino, a.st_mode) == (b.st_dev, b.st_ino, b.st_mode),
                     'directory namespace changed')
        verify()
        yield fds[-1], p.name, verify
        verify()
    finally:
        for fd in reversed(fds):
            os.close(fd)


class Budget:
    def __init__(self, limits, deadline):
        exact(limits, ('read_bytes', 'write_bytes', 'retained_bytes'))
        need(all(type(n) is int and 65_536 <= n <= 64 * 1024**2 for n in limits.values()),
             'finite integration metadata allowance; scientific workload is separately selected')
        need(type(deadline) in (int, float) and math.isfinite(deadline), 'finite enclosing deadline')
        self.limits, self.deadline = dict(limits), deadline
        self.reads = self.writes = 0
        self.tick()

    def tick(self):
        need(time.monotonic() < self.deadline, 'original integration deadline')

    def read(self, n):
        need(type(n) is int and n >= 0 and self.reads + n <= self.limits['read_bytes'],
             'integration read ceiling')
        self.reads += n
        self.tick()

    def write(self, n):
        need(type(n) is int and n >= 0 and self.writes + n <= self.limits['write_bytes']
             and self.writes + n <= self.limits['retained_bytes'], 'integration publication ceiling')
        self.writes += n
        self.tick()

    def record(self):
        return dict(read_reservations=self.reads, write_reservations=self.writes,
                    original_deadline=self.deadline, physical_IO_measured=False)


def capture(spec, budget, cap=4_000_000):
    descriptor(spec, cap)
    budget.read(spec['bytes'] + 1)
    with held_parent(spec['path']) as (parent, leaf, verify):
        fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=parent)
        try:
            first = os.fstat(fd)
            need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1
                 and first.st_size == spec['bytes'], 'pinned ordinary file')
            parts, left = [], spec['bytes'] + 1
            while left:
                budget.tick()
                block = os.read(fd, min(left, 65_536))
                if not block:
                    break
                parts.append(block)
                left -= len(block)
            body = b''.join(parts)
            verify()
            need(stamp(first) == stamp(os.fstat(fd)) ==
                 stamp(os.stat(leaf, dir_fd=parent, follow_symlinks=False)), 'stable complete capture')
            need(pin(body) == only_pin(spec), 'exact content identity')
            return body
        finally:
            os.close(fd)


def observed(value, extent, budget):
    """Capture a newly created selected product with an exact known extent."""
    need(type(extent) is int and 0 < extent <= 4_000_000, 'exact bounded observed extent')
    budget.read(extent + 1)
    with held_parent(value) as (parent, leaf, verify):
        fd = os.open(leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                     dir_fd=parent)
        try:
            first = os.fstat(fd)
            need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and first.st_size == extent,
                 'observed ordinary output extent')
            parts, left = [], extent + 1
            while left:
                budget.tick()
                part = os.read(fd, min(left, 65_536))
                if not part:
                    break
                parts.append(part)
                left -= len(part)
            result = b''.join(parts)
            verify()
            need(len(result) == extent and stamp(first) == stamp(os.fstat(fd)) ==
                 stamp(os.stat(leaf, dir_fd=parent, follow_symlinks=False)), 'stable observed output')
            return result
        finally:
            os.close(fd)


def put(value, body, budget):
    need(type(body) is bytes and 0 < len(body) <= 4_000_000, 'bounded publication')
    budget.write(len(body))
    with held_parent(value) as (parent, leaf, verify):
        fd = os.open(leaf, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o400, dir_fd=parent)
        try:
            tail = memoryview(body)
            while tail:
                budget.tick()
                n = os.write(fd, tail)
                need(n > 0, 'complete output write')
                tail = tail[n:]
            os.fsync(fd)
            verify()
            need(stamp(os.fstat(fd)) == stamp(os.stat(leaf, dir_fd=parent, follow_symlinks=False)),
                 'stable output identity')
            os.fsync(parent)
        finally:
            os.close(fd)
    return dict(path=str(path(value)), **pin(body))


def fresh_directory(value):
    with held_parent(value) as (parent, leaf, verify):
        s = os.fstat(parent)
        need(s.st_uid == os.geteuid() and s.st_mode & 0o022 == 0, 'owned nonshared parent')
        os.mkdir(leaf, 0o700, dir_fd=parent)
        verify()
        os.fsync(parent)
    return path(value)


def module(body, filename, **bindings):
    m = types.ModuleType('neural083_integration_' + Path(filename).stem)
    m.__file__ = str(filename)
    m.__dict__.update(bindings)
    exec(compile(body, str(filename), 'exec'), m.__dict__)
    return m


def source(root, spec, budget):
    raw = capture(spec, budget, 131_072)
    table = parse(raw)
    exact(table, ('schema', 'files'))
    need(table['schema'] == 'neural083_preparation_programme_source_v1'
         and type(table['files']) is dict and 1 <= len(table['files']) <= 64, 'whole source closure')
    bodies = {}
    for name, expected in table['files'].items():
        need(type(name) is str and not name.startswith('/') and '..' not in Path(name).parts
             and Path(name).as_posix() == name, 'closed relative source member')
        only_pin(expected)
        bodies[name] = capture(dict(path=str(path(root) / name), **expected), budget, 1_048_576)
    return table, bodies
