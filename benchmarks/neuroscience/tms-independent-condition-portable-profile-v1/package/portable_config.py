"""TMS-specific, owner-selected portable paths. No discovery or native dispatch."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import stat
import sys

PROFILE = 'tms_exact_real_248_method_specified_reconstruction_v1'
IMAGE = 'sha256:4703adf8fdd93b1441114e4f87ce2c62f7373fc5f88bda6a546c551625bcc71c'
ASSETS = {'input_manifest', 'input_values', 'projection_receipt', 'projection_outcome',
          'projection_review', 'identity', 'paper', 'driver', 'helper', 'runtime_review',
          'reference_review'}
PINS = {
 'identity': (5214, '4491f48145c8b9cddc7fcf7f7193a671117038583b234552cfa3bf85a23e262c'),
 'paper': (1996585, '8c8cc3ca22cdeb08459ad3688e86b43b95ef0b052572f319994d1235ae3676fc'),
 'driver': (1872, '41861a53e44b7e316374515739fff12b80b4f4676b3bc0b8086476357b4b8b1e'),
 'helper': (2546, 'c62c71d3f96c8399d9cd578c91b9fa6a3a99cdb449e8dbedd683c5c5490c0e23')}
_STATE = None

def need(ok, reason):
    if not ok:
        raise ValueError(reason)

def decode(body):
    def pairs(rows):
        out = {}
        for k, v in rows:
            need(k not in out, 'duplicate configuration key: ' + k)
            out[k] = v
        return out
    return json.loads(body.decode('utf-8'), object_pairs_hook=pairs,
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError('nonfinite JSON')))

def path(value):
    need(type(value) is str and value and '\0' not in value, 'ordinary absolute path required')
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts and ',' not in value and '\n' not in value,
         'absolute path without traversal or mount separators required')
    need(not any(x.is_symlink() for x in (p, *p.parents)), 'symlink path refused: ' + value)
    return p

def pin(value, cap=1 << 30):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'}, 'closed content pin required')
    need(type(value['bytes']) is int and 0 < value['bytes'] <= cap, 'bounded nonzero extent required')
    need(type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None,
         'lowercase SHA256 required')
    return value

def locator(value, cap=1 << 30):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'closed owner locator required')
    path(value['path']); pin({k: value[k] for k in ('bytes', 'sha256')}, cap)
    return value

def snapshot(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)

def read(entry, cap, mode=None):
    locator(entry, cap); p = path(entry['path'])
    try:
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError as exc:
        raise ValueError('missing owner-provided asset: ' + str(p)) from exc
    try:
        first = os.fstat(fd)
        need(stat.S_ISREG(first.st_mode) and first.st_nlink == 1 and first.st_size == entry['bytes'],
             'asset must be a regular single-link file with exact extent: ' + str(p))
        need(mode is None or stat.S_IMODE(first.st_mode) == mode, 'asset mode mismatch: ' + str(p))
        blocks = []; left = first.st_size
        while left:
            block = os.read(fd, min(left, 65536)); need(bool(block), 'short asset read')
            blocks.append(block); left -= len(block)
        need(snapshot(first) == snapshot(os.fstat(fd)) == snapshot(p.lstat()), 'asset changed during capture')
        body = b''.join(blocks)
        need(hashlib.sha256(body).hexdigest() == entry['sha256'], 'asset SHA256 mismatch: ' + str(p))
        return body
    finally:
        os.close(fd)

def validate(value):
    need(type(value) is dict and set(value) == {'schema', 'profile', 'private_use_authorized',
         'workspace', 'runtime', 'assets', 'reference'}, 'closed TMS owner configuration required')
    need(value['schema'] == 'tms_portable_owner_config_v1' and value['profile'] == PROFILE
         and value['private_use_authorized'] is True, 'explicit authorized private endpoint required')
    work = path(value['workspace'])
    rt = value['runtime']
    need(type(rt) is dict and set(rt) == {'host_python', 'host_version', 'host_system', 'docker',
         'socket', 'socket_identity', 'image', 'container_user'}, 'closed runtime policy required')
    locator(rt['host_python'], 64 << 20); locator(rt['docker'], 128 << 20)
    need(rt['host_version'] == [3, 11, 6] and all(type(x) is int for x in rt['host_version'])
         and rt['host_system'] in ('Darwin', 'Linux'), 'declared Python3.11.6 POSIX owner required')
    need(rt['image'] == IMAGE, 'only the admitted immutable candidate image is supported')
    path(rt['socket'])
    si = rt['socket_identity']
    need(type(si) is dict and set(si) == {'dev', 'inode', 'mode', 'uid', 'gid', 'nlink'}
         and all(type(x) is int and x >= 0 for x in si.values()), 'typed exact socket identity required')
    need(type(rt['container_user']) is str and re.fullmatch(r'[0-9]+:[0-9]+', rt['container_user']) is not None,
         'explicit numeric container UID:GID required')
    a = value['assets']; need(type(a) is dict and set(a) == ASSETS, 'all eleven owner-provided assets required')
    for name, entry in a.items():
        locator(entry, 16 << 20)
        if name in PINS:
            need((entry['bytes'], entry['sha256']) == PINS[name], 'fixed source-material identity: ' + name)
    need(a['input_values']['bytes'] == 11665920 and a['input_manifest']['bytes'] <= 65536,
         'complete 1458240-value projection required; source MAT alone is not a prepared input')
    inp = path(a['input_manifest']['path']).parent
    need(path(a['input_manifest']['path']) == inp / 'INPUT.json' and
         path(a['input_values']['path']) == inp / 'values.f64', 'exact input-pair filenames required')
    ref = value['reference']
    need(type(ref) is dict and set(ref) == {'root', 'descriptor', 'source_lock_sha256'}, 'closed owner-private reference selection required')
    root = path(ref['root']); pin(ref['descriptor'], 65536)
    need(type(ref['source_lock_sha256']) is str and re.fullmatch('[0-9a-f]{64}', ref['source_lock_sha256']),
         'historical accepted reference source identity required')
    need(not inp.is_relative_to(root) and not root.is_relative_to(inp), 'reference must be disjoint from candidate input')
    need(not work.is_relative_to(root) and not root.is_relative_to(work), 'reference and attempts must be disjoint')
    need(not work.is_relative_to(inp) and not inp.is_relative_to(work), 'input and attempts must be disjoint')
    for name, entry in a.items():
        if name not in ('input_manifest', 'input_values'):
            need(not path(entry['path']).is_relative_to(inp), 'no auxiliary or protected input members: ' + name)
    need(not path(a['reference_review']['path']).is_relative_to(inp), 'reference review cannot be candidate-visible')
    return value

def load(pathname, expected_sha, *, source_bodies=None):
    global _STATE
    p = path(pathname)
    try:
        n = p.lstat().st_size
    except FileNotFoundError as exc:
        raise ValueError('missing owner configuration; fill the non-executable example with authorized assets') from exc
    body = read({'path':str(p), 'bytes':n, 'sha256':expected_sha}, 65536, 0o400)
    value = validate(decode(body))
    _STATE = {'config': value, 'path': str(p), 'sha256': expected_sha,
              'source_bodies': source_bodies, 'config_bytes': len(body)}
    return value

def current():
    need(_STATE is not None, 'owner configuration was not authenticated')
    return _STATE['config']

def state():
    need(_STATE is not None, 'owner configuration was not authenticated')
    return _STATE

def admit_host(cfg):
    rt = cfg['runtime']
    need(list(sys.version_info[:3]) == rt['host_version'] and platform.system() == rt['host_system']
         and sys.flags.isolated == 1 and sys.flags.no_site == 1 and sys.dont_write_bytecode,
         'declared isolated host interpreter/platform required')
    need(Path(os.path.realpath(sys.executable)) == path(rt['host_python']['path']), 'selected interpreter path mismatch')
    need(rt['container_user'] == str(os.getuid()) + ':' + str(os.getgid()),
         'container UID:GID must match current owner for sealed-file readability')
    read(rt['host_python'], 64 << 20); read(rt['docker'], 128 << 20)
    return rt['host_python']['bytes'] + rt['docker']['bytes']

def preflight_assets(cfg):
    """Metadata-only absence checks; reference contents stay closed until scoring."""
    for name, entry in cfg['assets'].items():
        p = path(entry['path'])
        try:
            s = p.lstat()
        except FileNotFoundError as exc:
            raise ValueError('missing owner-provided ' + name + ': ' + str(p)) from exc
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_size == entry['bytes'],
             'wrong ordinary asset extent: ' + name)
    rr = path(cfg['reference']['root'])
    for name in ('OWNED_REFERENCE.json', 'LAUNCH_RESULT.json', 'work/RUNTIME_OBSERVED.json',
                 'work/RESULT.json', 'work/REFERENCE.private.json', 'work/SUPPORT.private.bin'):
        need((rr/name).is_file() and not (rr/name).is_symlink(), 'missing protected reference operand: ' + name)
    return True

def load_source(source_root, expected_sha):
    p = path(str(source_root)) / 'PORTABLE_SOURCE_LOCK.json'
    n = p.lstat().st_size
    raw = read({'path':str(p), 'bytes':n, 'sha256':expected_sha}, 65536)
    j = decode(raw)
    need(type(j) is dict and set(j) == {'schema', 'members'} and j['schema'] == 'tms_portable_source_lock_v1'
         and type(j['members']) is dict and 1 <= len(j['members']) <= 128, 'complete portable source lock required')
    bodies = {}; total = len(raw)
    for name, entry in j['members'].items():
        need(type(name) is str and not name.startswith('/') and '..' not in Path(name).parts,
             'ordinary relative source member required')
        pin(entry, 1 << 20)
        body = read({'path':str(p.parent/name), **entry}, 1 << 20)
        total += len(body); need(total <= 2 << 20, 'portable source closure exceeds2MiB')
        bodies[name] = body
    return bodies, total
