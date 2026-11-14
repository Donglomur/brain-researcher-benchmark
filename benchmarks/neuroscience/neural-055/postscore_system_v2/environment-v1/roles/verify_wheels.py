"""Verify exact prepared wheel bytes using the reviewed shared file-owner primitives."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import stat

HELPER_BYTES = 13770
HELPER_SHA256 = '82cb2002dfaed427f5ef1bfc03fa00d0a443ff5ad1b285c99bcaa04ba0397a83'

def need(ok, message):
    if not ok:
        raise ValueError(message)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--helper', required=True)
    p.add_argument('--lock', required=True)
    p.add_argument('--wheelhouse', required=True)
    a = p.parse_args()
    helper = Path(a.helper)
    before = helper.lstat()
    need(stat.S_ISREG(before.st_mode) and not helper.is_symlink() and
         before.st_size == HELPER_BYTES, 'selected shared source extent')
    stream = helper.open('rb'); first = None; raw = None
    try:
        raw = stream.read(HELPER_BYTES + 1)
    except BaseException as error:
        first = error
    finally:
        try:
            stream.close()
        except BaseException as error:
            if first is None:
                first = error
            else:
                first.__dict__.setdefault('cleanup_failures', []).append(error)
    if first is not None:
        raise first
    need(len(raw) == HELPER_BYTES and hashlib.sha256(raw).hexdigest() == HELPER_SHA256,
         'exact reviewed shared source')
    namespace = {'__name__': 'n055_environment_file_primitives', '__file__': str(helper)}
    exec(compile(raw, str(helper), 'exec'), namespace)
    literal, owned, hash_open, identity = (namespace[k] for k in
                                          ('literal', 'owned', 'hash_open', 'identity'))
    lockpath = literal(a.lock)
    need(lockpath.stat().st_size <= 131072, 'bounded exact role lock')
    lock = namespace['read_json'](str(lockpath))
    need(lock['schema'] == 'neural055-role-environment-lock-v1' and
         lock['role'] in ('ingestion', 'controller', 'campaign'),
         'one selected modern role')
    packages = lock['packages']
    need(type(packages) is list and 0 < len(packages) <= 64, 'finite selected wheel roster')
    chosen = {}
    for row in packages:
        name = row['filename']
        need(type(name) is str and re.fullmatch(r'[A-Za-z0-9_.+\-]+\.whl', name) and
             name not in chosen and re.fullmatch(r'[0-9a-f]{64}', row['sha256']),
             'unique exact wheel identity')
        chosen[name] = row
    root = literal(a.wheelhouse)
    entries = []
    for path in root.iterdir():
        need(len(entries) < len(chosen), 'no additional wheelhouse entry')
        entries.append(path)
    need({x.name for x in entries} == set(chosen), 'complete exact wheelhouse namespace')
    observed = []; total = 0
    for path in sorted(entries):
        row = chosen[path.name]
        path = literal(str(path)); state = path.stat()
        need(type(row['maximum_bytes']) is int and 0 < row['maximum_bytes'] <= 1073741824 and
             state.st_size <= row['maximum_bytes'], 'selected artifact byte ceiling')
        with owned(path.open('rb')) as stream:
            pin = hash_open(stream, state, 2147483648 - total)
            need(pin['sha256'] == row['sha256'] and
                 (row['published_bytes'] is None or pin['bytes'] == row['published_bytes']) and
                 identity(path.stat()) == identity(state), 'exact complete selected wheel')
        total += pin['bytes']
        observed.append({'filename': path.name, **pin})
    print(json.dumps({'schema': 'neural055-role-wheel-observation-v1', 'role': lock['role'],
                      'files': observed, 'explicit_hash_bytes': total,
                      'wheel_metadata_parsed': False, 'installed_or_imported': False,
                      'qualified': False}, sort_keys=True))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
