"""Load the exact additive completion and unchanged spinal delivery sources."""
import builtins
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
import types

HERE = Path(__file__).resolve().parent
BASE = HERE.parent / 'current-condition-delivery-v1'
BASE_SHA = 'a4bb4152fcbc86de70a8aa9c63eef204a42f1af30b34ef0970415c2a5bc059c2'
BANK_SHA = '33085162e9ba9ea64ef9862f681ec6f43c7065256b89430c313e5ac0dab5c726'
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'


def need(value, message):
    if not value:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def decode(body):
    def pairs(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'duplicate JSON key')
            value[key] = item
        return value
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, 'finite JSON required'))


def capture(path, limit, expected=None):
    path = Path(path)
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'unlinked input path')
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1
             and 0 <= before.st_size <= limit, 'bounded ordinary single-link file')
        body = stream.read(before.st_size + 1)
        after = os.fstat(stream.fileno())
        named = path.stat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')
    need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k)
         == getattr(named, k) for k in fields), 'stable file capture')
    if expected is not None:
        need(pin(body) == expected, 'exact file identity')
    return body


def save(path, body, cap=100_000):
    path = Path(path)
    need(isinstance(body, bytes) and len(body) <= cap, 'bounded private receipt')
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'unlinked receipt path')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    return pin(body)


def _relative(value):
    p = PurePosixPath(value)
    need(str(p) == value and not p.is_absolute() and '..' not in p.parts,
         'canonical relative source member')
    return value


def load_source(expected_sha):
    """No dataset, Docker or model access; imports only authenticated local code."""
    raw = capture(HERE / 'SOURCE.json', 200_000)
    need(pin(raw)['sha256'] == expected_sha, 'operator-selected completion source')
    manifest = decode(raw)
    need(manifest['schema'] == 'spinal_current_completion_source_v1'
         and manifest['delivery_manifest_sha256'] == BASE_SHA,
         'exact predecessor source binding')
    names = set()
    for row in manifest['files']:
        name = _relative(row['path'])
        need(name not in names, 'unique source roster')
        names.add(name)
        capture(HERE / name, 100_000, {k: row[k] for k in ('bytes', 'sha256')})
    need({'source.py', 'profile.py', 'observer.py', 'run.py', 'grade.py',
          'control/program.py'} <= names, 'complete executable source closure')
    for row in manifest['dependencies']:
        capture(HERE.parent / _relative(row['path']), 200_000,
                {k: row[k] for k in ('bytes', 'sha256')})
    base_raw = capture(BASE / 'SOURCE_MANIFEST.json', 100_000)
    need(pin(base_raw)['sha256'] == BASE_SHA, 'unchanged delivery manifest')
    base = decode(base_raw)
    source_rows = {row['path']: row for row in base['files']}
    modules = {}
    ordinary_import = builtins.__import__

    def bound_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name in modules:
            return modules[name]
        return ordinary_import(name, globals, locals, fromlist, level)

    previous_path = list(sys.path)
    try:
        for name in ('contract', 'materials', 'collect', 'transport'):
            row = source_rows[name + '.py']
            body = capture(BASE / row['path'], 100_000,
                           {k: row[k] for k in ('bytes', 'sha256')})
            module = types.ModuleType('_spinal_completion_' + name)
            module.__file__ = str(BASE / row['path'])
            module.__dict__['__builtins__'] = dict(vars(builtins), __import__=bound_import)
            exec(compile(body, module.__file__, 'exec'), module.__dict__)
            modules[name] = module
        delivery_pin = modules['transport'].verify_source(BASE_SHA)
        current = modules['materials'].load_current()
    finally:
        sys.path[:] = previous_path
    profile_module = types.ModuleType('_spinal_completion_bound_profile')
    profile_module.__file__ = str(HERE / 'profile.py')
    source_api = types.SimpleNamespace(BANK_SHA=BANK_SHA, IMAGE=IMAGE, need=need)
    def profile_import(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 0 and name == 'source':
            return source_api
        return ordinary_import(name, globals, locals, fromlist, level)
    profile_module.__dict__['__builtins__'] = dict(vars(builtins), __import__=profile_import)
    profile_row = next(row for row in manifest['files'] if row['path'] == 'profile.py')
    profile_body = capture(HERE / 'profile.py', 100_000,
                           {k: profile_row[k] for k in ('bytes', 'sha256')})
    exec(compile(profile_body, profile_module.__file__, 'exec'), profile_module.__dict__)
    return types.SimpleNamespace(**modules, current=current,
                                 completion_pin=pin(raw), delivery_pin=delivery_pin,
                                 collector=modules['collect'], source_pin=pin(raw),
                                 delivery_source_pin=delivery_pin,
                                 manifest=manifest, profile=profile_module,
                                 capture=capture, pin=pin, decode=decode)
