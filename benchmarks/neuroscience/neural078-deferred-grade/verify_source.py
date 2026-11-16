"""Closed portable source verification and offline authored-producer installation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

SCHEMA = 'neural078_deferred_grade_source_v1'
PRODUCER_RELATIVE = 'authoring/delivery-20261105/common/neural078-holder-readiness-successor-v1'
ADAPTER_PIN = {'bytes': 472, 'sha256': 'a5912bbdb00ed898e67cd15e6e9f1fe75ddf1eb29c5807e78ef5ad8a50845e8f'}
PROGRAM_PIN = {'bytes': 1801, 'sha256': '8a1b62ca449c5d3c089407fbe76345910fcc4684a3cbaf2811f6e043adb9dc6d'}
MANIFEST_CAP = 65536
MEMBER_CAP = 1000000
TOTAL_CAP = 2000000
READ_BYTES = 0


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def descriptor(value, cap=MEMBER_CAP):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'exact pin fields')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= cap, 'bounded integer extent')
    need(type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']), 'lowercase SHA-256')
    return value


def parse(raw):
    def pairs(rows):
        out = {}
        for key, value in rows:
            need(key not in out, 'duplicate JSON key')
            out[key] = value
        return out
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'nonfinite JSON'))


def canonical(value):
    need(isinstance(value, (str, Path)), 'literal absolute path')
    value = str(value)
    need(0 < len(value.encode()) <= 1024 and not any(c in value for c in '\0\r\n'),
         'bounded literal path')
    path = Path(value)
    need(path.is_absolute() and str(path) == value and '..' not in path.parts,
         'canonical absolute path')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'unlinked path ancestry')
    return path


def member(value):
    need(type(value) is str and len(value) <= 256
         and re.fullmatch(r'[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*', value)
         and all(p not in ('.', '..') for p in value.split('/')), 'confined member path')
    return value


def capture(path, cap, expected=None):
    global READ_BYTES
    path = canonical(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 < before.st_size <= cap, 'bounded single-link ordinary file')
        if expected is not None:
            need(before.st_size == descriptor(expected, cap)['bytes'], 'selected extent')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            raw = stream.read(before.st_size + 1)
        READ_BYTES += len(raw)
        after = os.fstat(fd)
        named = path.lstat()
        keys = ('st_dev', 'st_ino', 'st_mode', 'st_nlink', 'st_size',
                'st_uid', 'st_gid', 'st_mtime_ns', 'st_ctime_ns')
        need(len(raw) == before.st_size
             and all(getattr(before, k) == getattr(after, k) == getattr(named, k) for k in keys),
             'stable same-open source')
        need(expected is None or pin(raw) == expected, 'selected body digest')
        return raw
    finally:
        os.close(fd)


def inventory(root):
    files, directories, pending = set(), set(), [root]
    entries = 0
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as listing:
            for entry in listing:
                entries += 1
                need(entries <= 128, 'bounded complete source inventory')
                path = Path(entry.path)
                name = member(path.relative_to(root).as_posix())
                info = entry.stat(follow_symlinks=False)
                if stat.S_ISDIR(info.st_mode):
                    directories.add(name)
                    need(len(directories) <= 16, 'bounded directory count')
                    pending.append(path)
                else:
                    need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
                         'ordinary single-link inventory members')
                    files.add(name)
    return files, directories


def producer_members(bodies):
    expected = set()
    for prefix, selected in [('producer/', ADAPTER_PIN),
                             ('producer/program/', PROGRAM_PIN)]:
        raw = bodies[prefix + 'SOURCE_MANIFEST.json']
        need(pin(raw) == selected, 'unchanged accepted producer manifest')
        inner = parse(raw)
        need(set(inner) == {'schema', 'files'} and type(inner['files']) is dict,
             'original producer manifest shape')
        expected.add(prefix + 'SOURCE_MANIFEST.json')
        for name, selected_member in inner['files'].items():
            name = member(name)
            need('/' not in name, 'flat original producer source')
            relative = prefix + name
            need(pin(bodies[relative]) == descriptor(selected_member),
                 'unchanged accepted producer member')
            expected.add(relative)
    need(len(expected) == 18 and expected == {n for n in bodies if n.startswith('producer/')},
         'complete exact eighteen-file authored producer closure')
    return sorted(expected)


def verify(root, expected):
    root = canonical(root)
    need(root.is_dir(), 'existing source directory')
    descriptor(expected, MANIFEST_CAP)
    manifest_raw = capture(root / 'SOURCE_MANIFEST.json', MANIFEST_CAP, expected)
    manifest = parse(manifest_raw)
    need(type(manifest) is dict and set(manifest) == {'schema', 'files'}
         and manifest['schema'] == SCHEMA and type(manifest['files']) is list
         and 1 <= len(manifest['files']) <= 64, 'closed source manifest format')
    selected, total = {}, len(manifest_raw)
    for row in manifest['files']:
        need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'exact source row')
        name = member(row['path'])
        need(name != 'SOURCE_MANIFEST.json' and name not in selected, 'unique non-self source member')
        selected[name] = descriptor({k: row[k] for k in ('bytes', 'sha256')})
        total += row['bytes']
        need(total <= TOTAL_CAP, 'complete captured source ceiling')
    directories = {str(p) for n in selected for p in Path(n).parents if str(p) != '.'}
    expected_inventory = (set(selected) | {'SOURCE_MANIFEST.json'}, directories)
    need(inventory(root) == expected_inventory, 'no missing or extra source entries')
    bodies = {n: capture(root / n, MEMBER_CAP, selected[n]) for n in sorted(selected)}
    need(inventory(root) == expected_inventory, 'stable closed inventory')
    producer_members(bodies)
    return bodies, manifest_raw


def write_new(path, raw):
    canonical(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, 'wb', closefd=False) as stream:
            stream.write(raw)
            stream.flush()
        os.fsync(fd)
    finally:
        os.close(fd)


def install_producer(operator_root, source_root, bodies, source_pin):
    """Internal source assembly; caller must first authenticate the closed release."""
    operator_root, source_root = canonical(operator_root), canonical(source_root)
    names = producer_members(bodies)
    descriptor(source_pin, MANIFEST_CAP)
    need(not os.path.lexists(operator_root) and operator_root.parent.is_dir(),
         'fresh operator root under an existing directory')
    need(operator_root != source_root and source_root not in operator_root.parents
         and operator_root not in source_root.parents, 'separate operator and release custody')
    operator_root.mkdir(mode=0o700)
    installed, created = [], {operator_root}
    for name in names:
        relative = Path(PRODUCER_RELATIVE) / name.removeprefix('producer/')
        destination = operator_root / relative
        missing = []
        parent = destination.parent
        while parent not in created:
            missing.append(parent)
            parent = parent.parent
        for parent in reversed(missing):
            canonical(parent)
            parent.mkdir(mode=0o700)
            created.add(parent)
        write_new(destination, bodies[name])
        installed.append({'path': relative.as_posix(), **pin(bodies[name])})
    receipt = {
        'schema': 'neural078_authored_source_installation_v1',
        'task_id': 'NEURAL-078', 'source': source_pin, 'source_root': str(source_root),
        'operator_root': str(operator_root), 'files': installed,
        'source_only': True, 'data_provisioned': False, 'runtime_qualified': False,
        'observer_authority_supplied': False, 'scientific_qualified': False,
        'candidate_or_grader_executed': False,
    }
    raw = (json.dumps(receipt, sort_keys=True, indent=2) + '\n').encode()
    need(len(raw) <= 16384, 'bounded installation receipt')
    write_new(operator_root / 'SOURCE_INSTALLATION.json', raw)
    for directory in sorted(created, key=lambda p: len(p.parts), reverse=True) + [operator_root.parent]:
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('verify', 'install-producer'))
    parser.add_argument('--source-bytes', required=True, type=int)
    parser.add_argument('--source-sha256', required=True)
    parser.add_argument('--operator-root')
    args = parser.parse_args(argv)
    need(sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode, 'use -I -S -B')
    source_root = Path(os.path.abspath(__file__)).parent
    expected = {'bytes': args.source_bytes, 'sha256': args.source_sha256}
    bodies, _ = verify(source_root, expected)
    if args.mode == 'install-producer':
        need(args.operator_root is not None, 'explicit fresh operator root')
        receipt = install_producer(args.operator_root, source_root, bodies, expected)
        print(json.dumps({'status': 'authored_source_installed', 'members': len(receipt['files']),
                          'operator_root': receipt['operator_root'], 'source_only': True}))
    else:
        need(args.operator_root is None, 'operator root only for installation')
        print(json.dumps({'status': 'closed_source_verified', 'members': len(bodies),
                          'source': expected, 'participants': 8, 'required_fields': 195,
                          'source_only': True, 'runtime_qualified': False}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
