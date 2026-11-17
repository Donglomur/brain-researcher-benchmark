"""Read-only keeper for stopped producers; host must establish producer closure first.

Inventory contains metadata only. Numeric artifacts leave via the bounded
local Docker archive stream, never CLI stdout. The host establishes producer
closure before capture and checks a final exact inventory.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import time

READY_CAP = 256
READY_ROOT = Path('/ready')
READY_SCHEMA = 'h_holder_ready_v1'
FIELDS = ('st_dev', 'st_ino', 'st_mode', 'st_size', 'st_nlink', 'st_uid',
          'st_gid', 'st_mtime_ns', 'st_ctime_ns')
POLICY = None
DEPTH = 8
NAME_BYTES = 512


def need(ok, message):
    if not ok:
        raise ValueError(message)


def profile(role):
    need(POLICY is not None and role == POLICY['role'], 'Operator-bound holder profile')
    return POLICY


def owner_token(value):
    need(type(value) is str and re.fullmatch(r'h-[a-f0-9]{24}/holder', value),
         'bounded current holder owner token')
    return value


def stamp(s):
    return [getattr(s, field) for field in FIELDS]


def expected_stamp(value):
    need(type(value) is list and len(value) == len(FIELDS) and
         all(type(v) is int and v >= 0 for v in value), 'exact typed metadata stamp')
    return value


def names(value):
    need(type(value) is str and 0 < len(value.encode('utf-8')) <= NAME_BYTES,
         'bounded relative capture name')
    parts = value.split('/')
    need(len(parts) <= DEPTH and all(re.fullmatch(r'[A-Za-z0-9_](?:[A-Za-z0-9._ -]*[A-Za-z0-9._-])?', p)
                                  and p not in ('.', '..') for p in parts),
         'ordinary relative components only')
    return parts


def ordinary(s, directory=False):
    need((stat.S_ISDIR(s.st_mode) if directory else stat.S_ISREG(s.st_mode)) and
         s.st_uid == s.st_gid == 65534 and
         (s.st_nlink >= 1 if directory else s.st_nlink == 1),
         'ordinary owned directory or single-link regular file')


def mount_guard(root, capacity, readonly):
    rows = [x for x in Path('/proc/self/mountinfo').read_text().splitlines()
            if x.split(' - ', 1)[0].split()[4] == str(root)]
    need(len(rows) == 1, 'exact private mount')
    left, right = rows[0].split(' - ', 1)
    options = set(left.split()[5].split(','))
    mode = 'ro' if readonly else 'rw'
    need(right.split()[0] == 'tmpfs' and {mode, 'noexec', 'nosuid', 'nodev'} <= options
         and ('rw' if readonly else 'ro') not in options, 'exact tmpfs mount policy')
    fs = os.statvfs(root)
    need(fs.f_blocks * fs.f_frsize == capacity, 'exact bounded tmpfs')


def guard(role, root=Path('/capture')):
    p = profile(role)
    cg = Path('/sys/fs/cgroup')
    need(os.getuid() == 65534 and (cg / 'memory.max').read_text().strip() == '134217728'
         and (cg / 'memory.swap.max').read_text().strip() == '0'
         and (cg / 'pids.max').read_text().strip() == '64', 'observed holder cgroup bounds')
    quota, period = map(int, (cg / 'cpu.max').read_text().split())
    need(quota == period and period > 0, 'observed holder one CPU')
    mount_guard(root, p['total_cap'], True)
    mount_guard(READY_ROOT, 4096, False)
    sr = READY_ROOT.lstat()
    ordinary(sr, True)
    need(stat.S_IMODE(sr.st_mode) == 0o700, 'private readiness mode')
    return root


def marker_bytes(owner):
    return (json.dumps({'schema': READY_SCHEMA, 'owner': owner_token(owner)},
                       sort_keys=True, separators=(',', ':')) + '\n').encode('ascii')


def publish_ready(root, owner, ready_root=READY_ROOT):
    need(os.getpid() == 1, 'only initial keeper PID1 publishes readiness')
    with os.scandir(root) as scan:
        need(next(scan, None) is None, 'fresh output volume before readiness')
    with os.scandir(ready_root) as scan:
        need(next(scan, None) is None, 'fresh holder-private ready root')
    body = marker_bytes(owner)
    need(len(body) <= READY_CAP, 'bounded marker')
    pending = ready_root / '.pending'
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        at = 0
        while at < len(body):
            n = os.write(fd, body[at:])
            need(n > 0, 'complete marker write')
            at += n
        os.fsync(fd)
    finally:
        os.close(fd)
    os.rename(pending, ready_root / 'READY')
    fd = os.open(ready_root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def ready(owner, ready_root=READY_ROOT):
    expected = marker_bytes(owner)
    path = ready_root / 'READY'
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    except FileNotFoundError:
        return False
    try:
        first = os.fstat(fd)
        ordinary(first)
        need(stat.S_IMODE(first.st_mode) == 0o600 and 0 < first.st_size <= READY_CAP,
             'bounded private marker with exact mode0600')
        raw = os.read(fd, READY_CAP + 1)
        need(len(raw) == first.st_size and
             stamp(first) == stamp(os.fstat(fd)) == stamp(path.lstat()), 'stable complete marker')
        need(raw == expected, 'exact current-attempt readiness marker')
    finally:
        os.close(fd)
    return True


@contextmanager
def anchored(root, parts=()):
    """Keep every ancestor open and require its original directory identity at exit."""
    root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    opened = []
    try:
        initial = os.fstat(root_fd)
        ordinary(initial, True)
        need(stamp(initial) == stamp(os.stat(root, follow_symlinks=False)), 'exact capture root')
        current = root_fd
        for name in parts:
            before = os.stat(name, dir_fd=current, follow_symlinks=False)
            ordinary(before, True)
            child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=current)
            opened.append((current, name, child, stamp(before)))
            need(stamp(os.fstat(child)) == stamp(before), 'stable opened ancestor')
            current = child
        yield current
        for parent, name, child, expected in reversed(opened):
            need(stamp(os.fstat(child)) == expected ==
                 stamp(os.stat(name, dir_fd=parent, follow_symlinks=False)), 'stable capture ancestor')
        need(stamp(os.fstat(root_fd)) == stamp(initial) ==
             stamp(os.stat(root, follow_symlinks=False)), 'stable named capture root')
    finally:
        for _, _, child, _ in reversed(opened):
            os.close(child)
        os.close(root_fd)


def inventory(root, owner, role):
    limits = profile(role)
    need(ready(owner), 'capture requires prior keeper readiness')
    files, directories = [], []
    total = 0

    def walk(fd, prefix):
        nonlocal total
        first = os.fstat(fd)
        ordinary(first, True)
        count = 0
        with os.scandir(fd) as scan:
            for entry in scan:
                count += 1
                need(count <= limits['files'] + limits['directories'] - 1, 'bounded directory entries')
                rel = '/'.join(prefix + [entry.name])
                names(rel)
                before = os.stat(entry.name, dir_fd=fd, follow_symlinks=False)
                if stat.S_ISDIR(before.st_mode):
                    ordinary(before, True)
                    need(len(directories) + 1 < limits['directories'], 'bounded directory count including root')
                    directories.append({'name': rel, 'stamp': stamp(before)})
                    child = os.open(entry.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        need(stamp(os.fstat(child)) == stamp(before), 'exact opened inventory directory')
                        walk(child, prefix + [entry.name])
                        need(stamp(os.fstat(child)) == stamp(before) ==
                             stamp(os.stat(entry.name, dir_fd=fd, follow_symlinks=False)),
                             'stable inventory directory')
                    finally:
                        os.close(child)
                else:
                    ordinary(before)
                    need(len(files) < limits['files'] and 0 <= before.st_size <= limits['file_cap'],
                         'bounded file count and extent')
                    total += before.st_size
                    need(total <= limits['total_cap'], 'bounded aggregate extent')
                    files.append({'name': rel, 'bytes': before.st_size, 'stamp': stamp(before)})
        need(stamp(os.fstat(fd)) == stamp(first), 'stable inventory directory metadata')

    with anchored(root) as fd:
        root_stamp = stamp(os.fstat(fd))
        walk(fd, [])
    need(files, 'nonempty capture inventory')
    return {'schema': 'h_capture_inventory_v1', 'owner': owner_token(owner), 'role': role,
            'root_stamp': root_stamp, 'directories': sorted(directories, key=lambda x: x['name']),
            'files': sorted(files, key=lambda x: x['name']), 'total_bytes': total}



def load_policy(filename, expected):
    need(re.fullmatch('[0-9a-f]{64}',expected),'Immutable policy digest')
    fd=os.open(filename,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    try:
        s=os.fstat(fd);need(stat.S_ISREG(s.st_mode) and 0<s.st_size<=65536,'Bounded trusted policy')
        raw=os.read(fd,65537)
        need(len(raw)==s.st_size and stamp(s)==stamp(os.fstat(fd)),'Stable complete policy')
    finally:os.close(fd)
    need(hashlib.sha256(raw).hexdigest()==expected,'Pinned holder policy')
    value=json.loads(raw)
    need(set(value)=={'schema','phase_id','role','file_cap','total_cap','files','directories'}
         and value['schema']=='h_holder_policy_v1','Exact operator policy')
    need(value['role'] in ('A','B','reference','operator'),'Role bound')
    for k in ('file_cap','total_cap','files','directories'):
        need(type(value[k]) is int and value[k]>0,'Explicit finite output bounds')
    return value


def main():
    global POLICY
    parser=argparse.ArgumentParser(allow_abbrev=False)
    parser.add_argument('action',choices=('hold','ready','inventory'))
    parser.add_argument('--owner-token',required=True)
    parser.add_argument('--role',required=True)
    parser.add_argument('--policy',required=True)
    parser.add_argument('--policy-sha256',required=True)
    args=parser.parse_args();POLICY=load_policy(args.policy,args.policy_sha256)
    owner=owner_token(args.owner_token);root=guard(args.role)
    if args.action=='hold':
        publish_ready(root,owner)
        while True:time.sleep(1)
    elif args.action=='ready':print(json.dumps({'ready':ready(owner)},separators=(',',':')))
    else:print(json.dumps(inventory(root,owner,args.role),separators=(',',':')))


if __name__=='__main__':main()
