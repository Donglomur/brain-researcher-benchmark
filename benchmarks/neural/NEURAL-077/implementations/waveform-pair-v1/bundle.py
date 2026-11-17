"""Finite participant Python/config capture for the existing waveform transport.

Only declared top-level Python modules and config.json are captured. The launcher
imports these modules from authenticated memory under the transport's -I -S -B
runtime. This closes declared participant source/config, not the interpreter,
whole operating system, remote-provider identity, or arbitrary self-modification.
The operator must freeze the returned bundle identity before showing prompts.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import sys

SCHEMA = 'neural077_python_bundle_v1'
FROZEN_SCHEMA = 'neural077_frozen_python_bundle_v1'
CLIENT_CAP = 1048576
MODULE_CAP = 131072
CONFIG_CAP = 65536
RAW_CAP = 524288
FROZEN_CAP = 1048576
MAX_MODULES = 32
CONFIG_MODULE = 'neural077_config'
RUNTIME_SCOPE = ('Declared participant Python/config closure only; standard-library runtime supplied '
                 'externally by the existing isolated transport; no whole-runtime or provider-policy proof.')


def need(ok, message):
    if not ok:
        raise ValueError(message)


def pin(body):
    return {'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


def encoded(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False,
                       separators=(',', ':')) + '\n').encode('ascii')


def decode(body):
    def unique(items):
        result = {}
        for key, value in items:
            need(key not in result, 'Duplicate JSON key')
            result[key] = value
        return result
    def constant(value):
        raise ValueError('Nonfinite JSON: ' + value)
    try:
        return json.loads(body.decode('utf-8'), object_pairs_hook=unique, parse_constant=constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as error:
        raise ValueError('Strict UTF-8 JSON required') from error


def configuration(body):
    need(type(body) is bytes and 0 < len(body) <= CONFIG_CAP, 'Bounded JSON configuration')
    value = decode(body)
    need(type(value) is dict, 'Configuration must be a JSON object')
    count = 0
    def visit(item, depth):
        nonlocal count
        count += 1
        need(depth <= 16 and count <= 8192, 'Bounded configuration structure')
        need(type(item) in (dict, list, str, int, float, bool, type(None)), 'JSON values only')
        if type(item) is dict:
            need(all(type(key) is str for key in item), 'String JSON keys')
            for child in item.values():
                visit(child, depth + 1)
        elif type(item) is list:
            for child in item:
                visit(child, depth + 1)
        elif type(item) is float:
            need(math.isfinite(item), 'Finite JSON numbers')
    visit(value, 0)
    return value


def manifest(value):
    need(type(value) is dict and set(value) == {'schema', 'entry_module', 'modules', 'config'} and
         value['schema'] == SCHEMA and value['config'] == 'config.json', 'Exact bundle manifest')
    names = value['modules']
    need(type(names) is list and 1 <= len(names) <= MAX_MODULES and
         all(type(name) is str for name in names), 'Finite declared module list')
    need(names == sorted(set(names)), 'Unique modules in sorted filename order')
    reserved = set(sys.stdlib_module_names) | set(sys.builtin_module_names) | {CONFIG_MODULE}
    for name in names:
        need(re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*\.py', name) is not None and
             not name.startswith('__') and name[:-3] not in reserved,
             'Top-level nonreserved Python module names only')
    need(type(value['entry_module']) is str and value['entry_module'] + '.py' in names,
         'Entry module must be a declared top-level module')
    return {'schema': SCHEMA, 'entry_module': value['entry_module'],
            'modules': list(names), 'config': 'config.json'}


def descriptor(value, cap):
    need(type(value) is dict and set(value) == {'bytes', 'sha256'} and
         type(value['bytes']) is int and 0 < value['bytes'] <= cap and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']) is not None,
         'Exact bounded content descriptor')


def unlinked(path):
    path = Path(path).absolute()
    need(all(not item.is_symlink() for item in (path, *path.parents)), 'Linked path refused')
    return path


def fields(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, info.st_nlink)


def read_member(directory_fd, name, cap):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory_fd)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded ordinary singly linked bundle member')
        body = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
        final = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        need(len(body) == before.st_size and fields(before) == fields(after) == fields(final),
             'Bundle member changed during capture')
    return body, fields(before)


def source(body, name):
    need(type(body) is bytes and 0 < len(body) <= MODULE_CAP, 'Bounded Python module')
    try:
        body.decode('utf-8')
        compile(body, 'frozen://' + name, 'exec', dont_inherit=True)
    except (UnicodeError, SyntaxError, ValueError) as error:
        raise ValueError('Valid UTF-8 Python source required: ' + name) from error


_BOOTSTRAP = r'''# Frozen NEURAL-077 declared-source bundle; transport supplies isolation.
import base64 as _base64
import hashlib as _hashlib
import importlib as _importlib
import importlib.util as _util
import json as _json
import sys as _sys
import types as _types

_payload = _json.loads(__PAYLOAD_LITERAL__)
_modules = {}
for _name, _member in _payload['modules'].items():
    _body = _base64.b64decode(_member['base64'], validate=True)
    if len(_body) != _member['bytes'] or _hashlib.sha256(_body).hexdigest() != _member['sha256']:
        raise ValueError('Embedded source changed')
    _modules[_name] = _body
_config_body = _base64.b64decode(_payload['config']['base64'], validate=True)
if (len(_config_body) != _payload['config']['bytes'] or
        _hashlib.sha256(_config_body).hexdigest() != _payload['config']['sha256']):
    raise ValueError('Embedded config changed')

def _freeze(value):
    if type(value) is dict:
        return _types.MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if type(value) is list:
        return tuple(_freeze(item) for item in value)
    return value

class _ConfigModule(_types.ModuleType):
    def __setattr__(self, name, value):
        raise TypeError('Frozen configuration module')
    def __delattr__(self, name):
        raise TypeError('Frozen configuration module')

_config_module = _ConfigModule('neural077_config')
_types.ModuleType.__setattr__(_config_module, 'CONFIG', _freeze(_json.loads(_config_body)))
_sys.modules['neural077_config'] = _config_module
_stdlib = frozenset(_sys.stdlib_module_names) | frozenset(_sys.builtin_module_names)

class _BundledLoader:
    def find_spec(self, fullname, path=None, target=None):
        if fullname in _modules:
            return _util.spec_from_loader(fullname, self, origin='frozen://' + fullname + '.py')
        if fullname.partition('.')[0] not in _stdlib:
            raise ModuleNotFoundError('Undeclared participant module: ' + fullname)
        return None

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        module.__file__ = 'frozen://' + module.__name__ + '.py'
        module.__cached__ = None
        exec(compile(_modules[module.__name__], module.__file__, 'exec', dont_inherit=True), module.__dict__)

_sys.meta_path.insert(0, _BundledLoader())
_entry = _importlib.import_module(_payload['entry_module'])
if not callable(getattr(_entry, 'main', None)):
    raise ValueError('Declared entry module must provide main()')
raise SystemExit(_entry.main())
'''


def launcher(spec, members):
    payload = {'entry_module': spec['entry_module'],
               'modules': {name[:-3]: members[name] for name in spec['modules']},
               'config': members['config.json']}
    body = _BOOTSTRAP.replace('__PAYLOAD_LITERAL__', repr(encoded(payload).decode('ascii'))).encode('utf-8')
    need(0 < len(body) <= CLIENT_CAP, 'Launcher exceeds existing transport client cap')
    return body


def capture(root, declaration):
    """Capture once before prompts; return a fully JSON-serializable frozen dict.

    The manifest is supplied by the operator outside the member directory. The
    directory contains exactly its declared .py modules and config.json, with
    no packages, vendor trees, cache files, runtime files or extra manifests.
    """
    spec = manifest(declaration)
    root = unlinked(root)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        before = os.fstat(fd)
        expected = sorted(spec['modules'] + ['config.json'])
        need(stat.S_ISDIR(before.st_mode) and sorted(os.listdir(fd)) == expected,
             'Bundle root must contain exactly declared files')
        members, states, total = {}, {}, 0
        for name in expected:
            body, states[name] = read_member(fd, name, CONFIG_CAP if name == 'config.json' else MODULE_CAP)
            total += len(body)
            need(total <= RAW_CAP, 'Total captured source/config cap')
            if name == 'config.json':
                config = configuration(body)
            else:
                source(body, name)
            members[name] = {**pin(body), 'base64': base64.b64encode(body).decode('ascii')}
        need(sorted(os.listdir(fd)) == expected and fields(before) == fields(os.fstat(fd)) == fields(root.lstat()),
             'Bundle directory changed during capture')
        need(all(fields(os.stat(name, dir_fd=fd, follow_symlinks=False)) == states[name] for name in expected),
             'Bundle member changed before complete capture')
    finally:
        os.close(fd)
    client = launcher(spec, members)
    core = {'schema': FROZEN_SCHEMA, 'manifest': spec, 'members': members,
            'config': config, 'launcher': pin(client), 'runtime_scope': RUNTIME_SCOPE}
    result = {**core, 'bundle_identity': pin(encoded(core))}
    need(len(encoded(result)) <= FROZEN_CAP, 'Frozen bundle JSON cap')
    return result


def verify(frozen):
    """Verify a captured JSON record and return exact deterministic CLIENT bytes.

    This checks internal integrity. The caller must separately compare the
    bundle_identity to the operator's pre-prompt commitment; an entirely new
    self-consistent bundle is a different bundle, not prior authorization.
    """
    need(type(frozen) is dict and set(frozen) == {'schema', 'manifest', 'members', 'config',
         'launcher', 'runtime_scope', 'bundle_identity'} and frozen['schema'] == FROZEN_SCHEMA and
         frozen['runtime_scope'] == RUNTIME_SCOPE, 'Exact frozen bundle schema')
    need(len(encoded(frozen)) <= FROZEN_CAP, 'Frozen bundle JSON cap')
    spec = manifest(frozen['manifest'])
    need(type(frozen['members']) is dict and set(frozen['members']) == set(spec['modules'] + ['config.json']),
         'Exact declared captured members')
    total = 0
    for name, member in frozen['members'].items():
        need(type(member) is dict and set(member) == {'bytes', 'sha256', 'base64'} and
             type(member['base64']) is str, 'Exact captured member descriptor')
        cap = CONFIG_CAP if name == 'config.json' else MODULE_CAP
        expected = {key: member[key] for key in ('bytes', 'sha256')}
        descriptor(expected, cap)
        need(len(member['base64']) <= 4 * ((cap + 2) // 3), 'Bounded encoded source')
        try:
            body = base64.b64decode(member['base64'], validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError('Strict member base64 required') from error
        need(base64.b64encode(body).decode('ascii') == member['base64'] and pin(body) == expected,
             'Captured member identity changed')
        total += len(body)
        need(total <= RAW_CAP, 'Total captured source/config cap')
        if name == 'config.json':
            need(encoded(configuration(body)) == encoded(frozen['config']), 'Captured parsed config changed')
        else:
            source(body, name)
    body = launcher(spec, frozen['members'])
    descriptor(frozen['launcher'], CLIENT_CAP)
    need(pin(body) == frozen['launcher'], 'Frozen launcher source changed')
    core = {key: value for key, value in frozen.items() if key != 'bundle_identity'}
    descriptor(frozen['bundle_identity'], FROZEN_CAP)
    need(pin(encoded(core)) == frozen['bundle_identity'], 'Frozen bundle identity changed')
    return body


def verify_source(root, frozen):
    """Optional pre-prompt recapture to refuse source-directory drift."""
    verify(frozen)
    current = capture(root, frozen['manifest'])
    need(current == frozen, 'Source/config directory changed after capture')
    return dict(frozen['bundle_identity'])


def restore(frozen, fresh_output):
    """Write only CLIENT.py in a fresh private directory; never reopen sources."""
    body = verify(frozen)
    directory = unlinked(fresh_output)
    directory.mkdir(mode=0o700, parents=False, exist_ok=False)
    os.chmod(directory, 0o700)
    path = directory / 'CLIENT.py'
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o400)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(body)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(path, 0o400)
    return {'path': str(path), 'pin': pin(body), 'bundle_identity': dict(frozen['bundle_identity'])}
