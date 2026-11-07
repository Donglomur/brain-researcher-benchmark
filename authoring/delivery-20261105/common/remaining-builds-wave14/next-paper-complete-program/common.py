"""Bounded source/custody utilities; no data or process work on import."""
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import time

TASK = 'PAPER-paper-method-add-004'
PROGRAM_CAP = 8*1024**2
META_CAP = 1024**2


def need(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'),
                       allow_nan=False, ensure_ascii=True) + '\n').encode('ascii')


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def parse(body, cap=META_CAP):
    need(type(body) is bytes and len(body) <= cap, 'bounded metadata bytes')
    def pairs(rows):
        result = {}
        for key, value in rows:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    def bad(_):
        raise ValueError('nonfinite JSON')
    def integer(s):
        need(len(s) <= 20, 'bounded JSON integer')
        return int(s)
    def floating(s):
        value = float(s)
        need(math.isfinite(value), 'finite JSON number')
        return value
    # Bound syntax nesting before recursive JSON decoding.
    depth = 0
    quoted = escaped = False
    for c in body.decode('utf-8'):
        if quoted:
            if escaped:
                escaped = False
            elif c == '\\':
                escaped = True
            elif c == '"':
                quoted = False
        elif c == '"':
            quoted = True
        elif c in '[{':
            depth += 1
            need(depth <= 24, 'bounded JSON nesting')
        elif c in ']}':
            depth -= 1
    return json.loads(body, object_pairs_hook=pairs, parse_constant=bad,
                      parse_int=integer, parse_float=floating)


def descriptor(value, cap, *, allow_empty=False):
    need(type(value) is dict and type(value.get('bytes')) is int and
         (0 if allow_empty else 1) <= value['bytes'] <= cap and type(value.get('sha256')) is str and
         re.fullmatch('[a-f0-9]{64}', value['sha256']), 'bounded exact byte identity')
    return {k: value[k] for k in ('bytes', 'sha256')}


def relative(name):
    need(type(name) is str and 0 < len(name) <= 240 and '\\' not in name and
         all(ord(c) >= 32 and c not in ',\x7f' for c in name), 'safe relative name')
    p = Path(name)
    need(not p.is_absolute() and p.as_posix() == name and
         all(x not in ('', '.', '..') for x in name.split('/')) and
         len(p.parts) <= 16, 'exact relative path')
    return p


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size,
            s.st_mtime_ns, s.st_ctime_ns)


def ordinary(path):
    p = Path(path).absolute()
    need('..' not in p.parts and not any(x.is_symlink() for x in (p, *p.parents)),
         'ordinary immutable operator paths required')
    return p


class Budget:
    """Selected-artifact logical bytes; not interpreter or physical I/O totals."""
    def __init__(self, root, end, *, read_cap, write_cap, retained_cap, other_future):
        self.root, self.end = Path(root), end
        self.read_cap, self.write_cap, self.retained_cap = read_cap, write_cap, retained_cap
        self.other_future = other_future
        self.read = self.written = 0
        self.retained_charge = self.metadata_written = 0
    def deadline(self):
        need(time.monotonic() < self.end, 'original whole-command deadline')
    def reading(self, n):
        self.deadline()
        need(type(n) is int and n >= 0 and self.read + n <= self.read_cap, 'cumulative read cap')
        self.read += n
    def writing(self, n):
        self.deadline()
        need(type(n) is int and n >= 0 and self.written + n <= self.write_cap, 'cumulative write cap')
        # Every call precedes one new host file; seventeen directory blocks cover the
        # bounded path depth. Charges survive partial writes and are never reset.
        allocation = ((n+4095)//4096)*4096 + 17*4096
        need(self.retained_charge + allocation <= self.retained_cap, 'whole retained allocation ceiling')
        fs = os.statvfs(self.root)
        need(type(fs.f_frsize) is int and 0 < fs.f_frsize <= 4096 and 4096 % fs.f_frsize == 0,
             'selected filesystem allocation quantum must divide4096')
        need(fs.f_bavail * fs.f_frsize >= 2 * 1024**3 + self.other_future + self.retained_cap-self.retained_charge,
             'prospective physical floor plus OTHER and remaining own retention')
        self.written += n
        self.retained_charge += allocation
    def metadata(self, n):
        need(self.metadata_written+n <= 64*1024**2, 'whole source/program/metadata write subcap')
        self.metadata_written += n
        self.writing(n)
    def release_retired(self, n):
        self.deadline()
        need(type(n) is int and 0 <= n <= self.retained_charge, 'exact completed owned retirement credit')
        self.retained_charge -= n
    def producer_writes(self, n):
        self.deadline()
        need(type(n) is int and n >= 0 and self.written+n <= self.write_cap, 'cumulative tmpfs producer write reservation')
        self.written += n


def capture(path, expected, cap, budget=None, *, retain=True, allow_empty=False):
    p = ordinary(path)
    d = descriptor(expected, cap, allow_empty=allow_empty)
    if budget:
        budget.reading(d['bytes'] + 1)
    fd = os.open(p, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    primary = None
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
             before.st_size == d['bytes'], 'exact ordinary single-link file')
        left, h, pieces = d['bytes'], hashlib.sha256(), []
        while left:
            if budget:
                budget.deadline()
            block = os.read(fd, min(left, 1024**2))
            need(block, 'truncated captured input')
            left -= len(block)
            h.update(block)
            if retain:
                pieces.append(block)
        need(not os.read(fd, 1), 'no trailing byte')
        need(identity(before) == identity(os.fstat(fd)) == identity(p.lstat()) and
             h.hexdigest() == d['sha256'], 'stable complete source identity')
        return b''.join(pieces) if retain else d
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            os.close(fd)
        except BaseException as close_error:
            if primary is None:
                raise
            primary.add_note('Input close uncertainty: ' + type(close_error).__name__)


def save(path, body, budget=None, cap=META_CAP, *, metadata=True):
    need(type(body) is bytes and len(body) <= cap, 'bounded exact output bytes')
    p = ordinary(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    if budget:
        if metadata: budget.metadata(len(body))
        else: budget.writing(len(body))
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    primary = None
    try:
        data = memoryview(body)
        while data:
            if budget:
                budget.deadline()
            n = os.write(fd, data)
            need(n > 0, 'complete output write')
            data = data[n:]
        os.fsync(fd)
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            os.close(fd)
        except BaseException as close_error:
            if primary is None:
                raise
            primary.add_note('Output close uncertainty: ' + type(close_error).__name__)
    directory = os.open(p.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)
    if budget:
        budget.deadline()
    return pin(body)
