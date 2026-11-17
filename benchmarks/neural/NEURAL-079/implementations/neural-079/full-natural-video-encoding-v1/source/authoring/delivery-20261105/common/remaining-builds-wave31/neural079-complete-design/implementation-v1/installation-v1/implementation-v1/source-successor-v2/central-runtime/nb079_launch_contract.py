"""Pure, closed launch metadata algebra. No I/O, admission or effects at import.

This module does not establish authority. Its concrete callers must authenticate
the source, original clock, prepared objects and actual observed process/FD.
"""
import copy
import hashlib
import json
from pathlib import PurePosixPath


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names):
    require(type(value) is dict and set(value) == set(names), 'exact fields: ' + ','.join(names))


def integer(value, minimum=0):
    require(type(value) is int and value >= minimum, 'finite non-Boolean integer')
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def pin(raw):
    require(type(raw) is bytes, 'exact immutable byte buffer')
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def checked_pin(value):
    fields(value, ('bytes', 'sha256')); integer(value['bytes'])
    digest = value['sha256']
    require(type(digest) is str and len(digest) == 64 and
            all(c in '0123456789abcdef' for c in digest), 'exact lowercase SHA256')
    return value


def absolute(value):
    require(type(value) is str and value.startswith('/') and '\x00' not in value and
            str(PurePosixPath(value)) == value and '..' not in PurePosixPath(value).parts,
            'canonical absolute path')
    return value


def descriptor(value):
    fields(value, ('path', 'pin')); absolute(value['path']); checked_pin(value['pin'])
    return value


def original_clock(value):
    fields(value, ('origin', 'scientific', 'closeout', 'outer'))
    values = [integer(value[k]) for k in ('origin', 'scientific', 'closeout', 'outer')]
    require(all(a < b for a, b in zip(values, values[1:])), 'one strict original interval')
    return value


def root_reference(root):
    require(type(root) is dict and set(root) in (
        {'path', 'identity'}, {'path', 'identity', 'index_result_key', 'maximum_files', 'maximum_bytes'}),
        'exact reference or full product-root schema')
    absolute(root['path']); fields(root['identity'], ('device', 'inode'))
    integer(root['identity']['device']); integer(root['identity']['inode'], 1)
    if 'maximum_files' in root:
        integer(root['maximum_files'], 1); integer(root['maximum_bytes'])
        require(type(root['index_result_key']) is list and 0 < len(root['index_result_key']) <= 8 and
                all(type(k) is str and k for k in root['index_result_key']), 'fixed bounded result key chain')
    return {'path': root['path'], 'identity': dict(root['identity'])}


_PATHS = (
    ('admission',),
    ('launch', 'admission'),
    ('launch', 'role_blueprints', 'provider', 'inherited_fds'),
    ('composition', 'configuration', 'role_templates', 'provider', 'role_payload', 'credential_fd'))
_MARKERS = ({'$n079_slot': 'finalizer_admission'}, {'$n079_slot': 'finalizer_admission'},
            {'$n079_slot': 'credential_fd_list'}, {'$n079_slot': 'credential_fd'})


def _parent(value, path):
    current = value
    for part in path[:-1]:
        require(type(current) is dict and part in current, 'complete fixed pre-K structure')
        current = current[part]
    require(type(current) is dict and path[-1] in current, 'exact fixed pre-K slot exists')
    return current


def _slot_values(value):
    return [_parent(value, path)[path[-1]] for path in _PATHS]


def _admission(value):
    fields(value, ('schema', 'execution_enabled', 'issuer_receipt', 'source_environment_receipt',
        'custody_receipt', 'history_receipt', 'sources', 'source_manifest_pin', 'profile_pin',
        'role', 'role_identity', 'peers', 'scope_membership', 'boot_id', 'environment'))
    require(value['schema'] == 'ach_typed_source_admission_v1' and value['execution_enabled'] is True and
            value['role'] == 'finalizer', 'actual separately admitted finalizer source selection')
    require(type(value['role_identity']) is dict and type(value['peers']) is dict and
            type(value['environment']) is dict, 'complete observed admission fields')
    for name in ('issuer_receipt', 'source_environment_receipt', 'custody_receipt', 'history_receipt'):
        descriptor(value[name])
    for name in ('source_manifest_pin', 'profile_pin'):
        checked_pin(value[name])
    require(type(value['sources']) is list and value['sources'], 'full exact source roster')
    for source in value['sources']:
        descriptor(source)


def fixed_pre_k_projection(template_or_K):
    values = _slot_values(template_or_K)
    if values != list(_MARKERS):
        _admission(values[0]); require(values[1] == values[0], 'two identical finalizer admissions')
        integer(values[3], 3)
        require(type(values[2]) is list and values[2] == [values[3]], 'same sole provider credential FD')
    result = copy.deepcopy(template_or_K)
    for path in _PATHS:
        del _parent(result, path)[path[-1]]
    return result


def resolve_pre_k(template, finalizer_admission, credential_fd):
    require(_slot_values(template) == list(_MARKERS), 'exact four unresolved source-owned template slots')
    _admission(finalizer_admission); integer(credential_fd, 3)
    result = copy.deepcopy(template)
    for path, value in zip(_PATHS, (finalizer_admission, finalizer_admission, [credential_fd], credential_fd)):
        _parent(result, path)[path[-1]] = copy.deepcopy(value)
    validate_pre_k(template, result, finalizer_admission, credential_fd)
    return result


def validate_pre_k(template, K, finalizer_admission, credential_fd):
    require(_slot_values(template) == list(_MARKERS), 'one original unresolved T')
    _admission(finalizer_admission); integer(credential_fd, 3)
    require(_slot_values(K) == [finalizer_admission, finalizer_admission, [credential_fd], credential_fd],
            'only actual observed four-slot binding')
    require(fixed_pre_k_projection(template) == fixed_pre_k_projection(K),
            'all scientific/configuration/source/root/cap/clock fields unchanged')
    return K


def template_markers():
    """Source-owned declaration only; this does not construct a live template."""
    return {'.'.join(path): copy.deepcopy(marker) for path, marker in zip(_PATHS, _MARKERS)}
