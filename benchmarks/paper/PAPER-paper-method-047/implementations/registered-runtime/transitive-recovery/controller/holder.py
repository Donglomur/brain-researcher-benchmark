"""Trusted stopped-producer inventory and bounded chunks; no candidate imports."""
import base64
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import time

MODEL = 268435456
PREDICTION = 67108864
VOLUME = 335544320
CHUNK = 4194304


def need(ok, message):
    if not ok:
        raise ValueError(message)


def guard():
    c = Path('/sys/fs/cgroup')
    need(os.getuid() == 65534 and
         (c / 'memory.max').read_text().strip() == '134217728' and
         (c / 'memory.swap.max').read_text().strip() == '0' and
         (c / 'pids.max').read_text().strip() == '64', 'holder cgroups')
    quota, period = map(int, (c / 'cpu.max').read_text().split())
    need(quota == period and period > 0, 'holder one CPU')
    rows = [r for r in Path('/proc/self/mountinfo').read_text().splitlines()
            if r.split(' - ', 1)[0].split()[4] == '/capture']
    need(len(rows) == 1, 'one capture mount')
    left, right = rows[0].split(' - ', 1)
    need(right.split()[0] == 'tmpfs' and
         {'ro', 'noexec', 'nosuid', 'nodev'} <= set(left.split()[5].split(',')),
         'read-only bounded tmpfs')
    s = os.statvfs('/capture')
    need(s.f_blocks * s.f_frsize == VOLUME, 'volume capacity')


def regular(root, name):
    p = PurePosixPath(name)
    need(not p.is_absolute() and p.as_posix() == name and
         all(x not in ('', '.', '..') for x in p.parts) and
         len(name) <= 240 and '\\' not in name and
         all(ord(x) >= 32 and x not in ',\x7f' for x in name), 'model member name')
    target = root / name
    need(all(not q.is_symlink() for q in (target, *target.parents)), 'no symlinks')
    return target


def fingerprint(p, cap):
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        a = os.fstat(fd)
        need(stat.S_ISREG(a.st_mode) and a.st_nlink == 1 and
             0 < a.st_size <= cap, 'bounded single-link regular state')
        h = hashlib.sha256()
        count = 0
        while count <= a.st_size:
            chunk = os.read(fd, min(CHUNK, a.st_size + 1 - count))
            if not chunk:
                break
            h.update(chunk)
            count += len(chunk)
        z = os.fstat(fd)
        n = p.lstat()
        keys = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
        need(count == a.st_size and all(getattr(a, k) == getattr(z, k) == getattr(n, k)
                                       for k in keys), 'stopped stable state')
        return {'bytes': count, 'sha256': h.hexdigest()}
    finally:
        os.close(fd)


def inventory(root, phase):
    need(phase in ('train', 'predict'), 'phase')
    stack = [root]
    files = {}
    directories = []
    total = 0
    count = 0
    while stack:
        parent = stack.pop()
        with os.scandir(parent) as scan:
            for row in scan:
                count += 1
                need(count <= 512, 'bounded state inventory')
                name = (parent / row.name).relative_to(root).as_posix()
                p = regular(root, name)
                s = p.lstat()
                if stat.S_ISDIR(s.st_mode):
                    need(phase == 'train' and len(PurePosixPath(name).parts) <= 8,
                         'model directory depth')
                    stack.append(p)
                    directories.append(name)
                else:
                    need(len(files) < 256, 'state member count')
                    f = fingerprint(p, MODEL if phase == 'train' else PREDICTION)
                    total += f['bytes']
                    need(total <= (MODEL if phase == 'train' else PREDICTION), 'state total')
                    files[name] = f
    need(bool(files), 'nonempty complete state')
    if phase == 'predict':
        need(set(files) == {'prediction.json'}, 'single unchanged scientific artifact')
    return {'schema': 'gcamp8_stopped_inventory_v1', 'phase': phase,
            'files': dict(sorted(files.items())), 'directories': sorted(directories),
            'bytes': total}


def chunk(root, name, offset, expected):
    p = regular(root, name)
    need(type(offset) is int and 0 <= offset < expected['bytes'], 'chunk offset')
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        s = os.fstat(fd)
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size == expected['bytes'],
             'same stopped extent')
        os.lseek(fd, offset, os.SEEK_SET)
        raw = os.read(fd, min(CHUNK, s.st_size - offset))
        need(len(raw) == min(CHUNK, s.st_size - offset), 'complete chunk')
        return {'name': name, 'offset': offset, 'bytes': len(raw),
                'base64': base64.b64encode(raw).decode('ascii')}
    finally:
        os.close(fd)


def main():
    guard()
    action = sys.argv[1]
    root = Path('/capture')
    if action == 'hold':
        with os.scandir(root) as scan:
            need(next(scan, None) is None, 'fresh volume')
        while True:
            time.sleep(1)
    elif action == 'ready':
        print('{"ready":true}')
    elif action == 'inventory':
        print(json.dumps(inventory(root, sys.argv[2]), separators=(',', ':')))
    elif action == 'chunk':
        expected = {'bytes': int(sys.argv[4])}
        print(json.dumps(chunk(root, sys.argv[2], int(sys.argv[3]), expected), separators=(',', ':')))
    else:
        raise ValueError('action')


if __name__ == '__main__':
    main()
