#!/usr/bin/env python3
"""Verify source bytes without executing candidate code, Docker or scientific data."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys

HERE = Path(__file__).absolute().parent
if len(sys.argv) != 2:
    raise SystemExit('usage: verify_source.py EXPECTED_SOURCE_LOCK_SHA256')
def read(path, cap):
    if any(p.is_symlink() for p in (path, *path.parents)): raise ValueError('source alias')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > cap:
            raise ValueError('bounded ordinary source')
        with os.fdopen(fd, 'rb', closefd=False) as stream: body = stream.read(cap + 1)
        stamp = lambda s: (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if stamp(before) != stamp(os.fstat(fd)) or stamp(before) != stamp(path.lstat()) or len(body) != before.st_size:
            raise ValueError('changed source')
        return body
    finally: os.close(fd)

raw = read(HERE / 'SOURCE_LOCK.json', 65536)
if hashlib.sha256(raw).hexdigest() != sys.argv[1]: raise ValueError('unselected source lock')
lock = json.loads(raw); total = len(raw)
if set(lock) != {'schema', 'members'} or lock['schema'] != 'purkinje-portable-program-source/v1':
    raise ValueError('source lock schema')
for name, pin in lock['members'].items():
    if Path(name).name != name or name in ('.', '..') or type(pin['bytes']) is not int or not 0 < pin['bytes'] <= 1048576:
        raise ValueError('source member descriptor')
    body = read(HERE / name, pin['bytes']); total += len(body)
    if total > 2 * 1024 ** 2 or len(body) != pin['bytes'] or hashlib.sha256(body).hexdigest() != pin['sha256']:
        raise ValueError('source identity')
    if name.endswith('.py'): compile(body, name, 'exec')
print('Verified', len(lock['members']), 'operative source members;', total, 'managed source bytes; no scientific execution.')
