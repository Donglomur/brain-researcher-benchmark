"""Exact prospective postscore-v2 source capture and restoration; no scientific module is imported here."""
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import types
import uuid

MANIFEST = {'bytes': 18592, 'sha256': '583ae551b6a4f185675b3f44eeed720dbb185b11ada7d61f1b3b86bcfdbd10e8'}
PREPARATION_ROLES = (
    'private/preparation/stage_source.py', 'private/preparation/source_io.py',
    'private/preparation/metadata_core.py', 'private/preparation/build_case.py',
    'private/preparation/build_panel.py', 'public/interface.py')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pairs(rows):
    out = {}
    for key, value in rows:
        need(key not in out, 'duplicate metadata key')
        out[key] = value
    return out


def parse(raw):
    return json.loads(raw.decode('utf8'), object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite metadata')))


def identity(s):
    return (s.st_dev, s.st_ino, s.st_mode, s.st_nlink, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def absolute(path):
    p = Path(path)
    need(p.is_absolute() and '..' not in p.parts and str(p) == str(path), 'canonical absolute path')
    need(not any(x.is_symlink() for x in (p, *p.parents)), 'path aliases forbidden')
    return p


def relative(path):
    p = Path(path)
    need(type(path) is str and path and not p.is_absolute() and '..' not in p.parts
         and str(p) == path and '\\' not in path, 'canonical relative path')
    return p


def read_exact(path, expected, maximum, charge):
    """One bounded stable ordinary body, charged prospectively and never refunded."""
    p = absolute(path)
    n = expected['bytes']; digest = expected['sha256']
    need(type(n) is int and 0 < n <= maximum and type(digest) is str
         and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'bounded exact file pin')
    before = p.lstat()
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size == n,
         'ordinary single-link exact file')
    if 'mode' in expected:
        need(stat.S_IMODE(before.st_mode) == int(expected['mode'], 8), 'exact selected file mode')
    charge(n + 1)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        need(identity(os.fstat(fd)) == identity(before), 'same opened source identity')
        body = bytearray()
        while len(body) <= n:
            chunk = os.read(fd, min(65536, n + 1 - len(body)))
            if not chunk:
                break
            body.extend(chunk)
        need(identity(os.fstat(fd)) == identity(before) == identity(p.lstat()), 'stable complete source identity')
    finally:
        os.close(fd)
    raw = bytes(body)
    need(len(raw) == n and hashlib.sha256(raw).hexdigest() == digest, 'complete exact body')
    return raw


def capture_runtime(root, manifest_pin, read_cap):
    root = absolute(root)
    need(manifest_pin == MANIFEST, 'exact selected postscore-v2 runtime manifest')
    need(type(read_cap) is int and read_cap > 0, 'explicit source read ceiling')
    spent = 0
    def charge(n):
        nonlocal spent
        need(spent + n <= read_cap, 'source capture ceiling before open')
        spent += n
    raw = read_exact(root / 'RUNTIME_SOURCE_MANIFEST.json', dict(manifest_pin, mode='0o644'), 1048576, charge)
    manifest = parse(raw)
    need(set(manifest) == {'schema', 'files'} and manifest['schema'] == 'neural055-complete-runtime-source-v1'
         and len(manifest['files']) == 87, 'complete exact postscore-v2 source closure')
    bodies = {}
    for row in manifest['files']:
        need(set(row) == {'path', 'bytes', 'sha256', 'mode', 'role'}, 'closed source descriptor')
        name = row['path']; relative(name)
        need(name not in bodies and row['role'] in ('runtime_source', 'legacy_source', 'source_contract', 'public_instructions'),
             'unique ordinary source role')
        bodies[name] = read_exact(root / name, row, 1048576, charge)
    descriptor = dict(path='RUNTIME_SOURCE_MANIFEST.json', **manifest_pin,
                      mode='0o644', role='complete_runtime_manifest')
    return {'source_manifest': descriptor, 'identity': manifest_pin['sha256'], 'source_bodies': bodies}, spent


def preparation_bodies(context):
    """Resolve the existing finite role map; restore names, never rewrite algorithms."""
    bodies = context['source_bodies']; roles = parse(bodies['LEGACY_ROLES.json'])
    selected = {}
    for role in PREPARATION_ROLES:
        d = roles[role]; raw = bodies[d['path']]
        need(len(raw) == d['bytes'] and hashlib.sha256(raw).hexdigest() == d['sha256'], 'exact retained preparation body')
        selected[role] = raw
    return selected


class RuntimeSupport:
    """Reuse only captured stdlib controller/metadata support, in an owned namespace."""
    NAMES = ('common', 'budget', 'journal', 'process', 'source', 'inputs')

    def __init__(self, context):
        self.name = '_n055_operator_' + uuid.uuid4().hex
        self.modules = {}; self.inserted = []
        try:
            package = types.ModuleType(self.name); package.__path__ = []
            sys.modules[self.name] = package; self.inserted.append(self.name)
            for name in self.NAMES:
                fullname = self.name + '.' + name
                module = types.ModuleType(fullname)
                module.__package__ = self.name
                module.__file__ = 'captured://n055/' + name + '.py'
                sys.modules[fullname] = module; self.inserted.append(fullname)
                self.modules[name] = module
                exec(compile(context['source_bodies']['n055/' + name + '.py'], module.__file__, 'exec'), module.__dict__)
        except BaseException:
            self.close()
            raise

    def source_snapshot(self, context, root, budget):
        """Already-captured exact source consumed by the unmodified legacy loader."""
        cls = self.modules['source'].Sources
        value = object.__new__(cls)
        value.root = Path(root); value.budget = budget; value.identity = context['identity']
        value.bodies = context['source_bodies']; value.legacy = parse(value.bodies['LEGACY_ROLES.json'])
        value.loaded = {}; value.actor_root = None; value.actor_descriptors = {}
        return value

    def close(self):
        for name in reversed(self.inserted):
            sys.modules.pop(name, None)
        self.inserted.clear()
