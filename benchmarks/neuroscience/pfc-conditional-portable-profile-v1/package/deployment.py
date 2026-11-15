"""Relocation checks only. Scientific kernels and full case scope stay fixed."""
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys
from profile import (PROFILE, IMAGE, PACKET, SCIENCE, ASSISTANCE, OFFICIAL,
                     RUNTIME_FILES, LINEAGE_ROLES, EXECUTION_SCOPE, BASELINE, NEGATIVE)

MIB = 1024 ** 2


def need(ok, message):
    if not ok:
        raise ValueError(message)


def absolute(value):
    need(type(value) is str and not any(c in value for c in '\0\r\n,'),
         'ordinary path cannot contain Docker mount separators or controls')
    p = Path(value)
    need(p.is_absolute() and '..' not in p.parts and
         not any(x.is_symlink() for x in (p, *p.parents)), 'ordinary absolute path')
    return p


def descriptor(value, cap=MIB):
    need(type(value) is dict and set(value) == {'path', 'bytes', 'sha256'}, 'exact descriptor fields')
    absolute(value['path'])
    need(type(value['bytes']) is int and 0 < value['bytes'] <= cap and
         type(value['sha256']) is str and re.fullmatch('[0-9a-f]{64}', value['sha256']),
         'bounded descriptor length and SHA256')
    return value


def read_pin(value, cap=MIB):
    descriptor(value, cap)
    p = absolute(value['path'])
    try:
        before = p.lstat()
    except FileNotFoundError as error:
        raise FileNotFoundError('Missing owner-provided asset: ' + str(p)) from error
    need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and
         before.st_size == value['bytes'], 'single-link exact asset extent: ' + str(p))
    with p.open('rb') as stream:
        body = stream.read(value['bytes'] + 1)
    after = p.lstat()
    need(len(body) == value['bytes'] and hashlib.sha256(body).hexdigest() == value['sha256'] and
         all(getattr(before, k) == getattr(after, k) for k in
             ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')),
         'stable exact asset identity: ' + str(p))
    return body


def decode(body):
    def pairs(items):
        result = {}
        for key, value in items:
            need(key not in result, 'duplicate JSON key')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=pairs,
                      parse_constant=lambda v: (_ for _ in ()).throw(ValueError(v)))


def same_identity(pin, expected):
    descriptor(pin, 16 * MIB)
    need((pin['bytes'], pin['sha256']) == expected, 'accepted complete profile identity')


def validate_deployment(d):
    need(type(d) is dict and set(d) == {'host_python', 'docker_cli', 'docker_host',
         'daemon_id', 'attempts_root', 'uid', 'gid'}, 'complete deployment fields')
    descriptor(d['host_python'], 16 * MIB)
    descriptor(d['docker_cli'], 64 * MIB)
    root = absolute(d['attempts_root'])
    need(str(root) != '/', 'specific attempt parent required')
    need(type(d['docker_host']) is str and d['docker_host'].startswith('unix:///'),
         'explicit local Unix Docker endpoint only')
    absolute(d['docker_host'][7:])
    need(type(d['daemon_id']) is str and
         re.fullmatch('[A-Za-z0-9:_-]{1,128}', d['daemon_id']), 'explicit admitted daemon identity')
    need(type(d['uid']) is int and 0 < d['uid'] < 2**31 and
         type(d['gid']) is int and 0 < d['gid'] < 2**31, 'explicit nonroot UID/GID')


def validate_request_metadata(r, p, here):
    need(type(r) is dict and set(r) == {'schema', 'attempt', 'policy', 'source_files',
         'programs', 'execution_scope', 'deployment', 'source_lock', 'compatibility'}, 'request fields')
    need(r['schema'] == 'PFC_PORTABLE_PARTICIPANT_REQUEST_V1' and
         type(r['attempt']) is str and re.fullmatch('[a-z0-9][a-z0-9-]{0,47}', r['attempt']),
         'request schema and fresh attempt identifier')
    descriptor(r['policy']); descriptor(r['source_lock'])
    validate_deployment(r['deployment'])
    need(set(r['source_files']) == RUNTIME_FILES, 'complete portable runtime source graph')
    for name, pin in r['source_files'].items():
        descriptor(pin)
        need(pin['path'] == str(here / name), 'relocated source must be in selected package')
    need(set(r['programs']) == {'A', 'B'} and r['execution_scope'] == EXECUTION_SCOPE,
         'complete two-arm scope')
    for pin in r['programs'].values():
        descriptor(pin)
    need(type(r['compatibility']) is bool, 'explicit compatibility versus participant mode')
    if r['compatibility']:
        for pin in r['programs'].values():
            same_identity(pin, BASELINE)
    expected_policy = {'schema', 'profile', 'image', 'packet', 'scorer_sources',
         'common_assistance', 'additional_B_assistance', 'inherited_owner',
         'inherited_outer', 'source_input_selection', 'assistance_interpretation', 'rights', 'negative_source'}
    need(type(p) is dict and set(p) == expected_policy and
         p['schema'] == 'PFC_PORTABLE_PARTICIPANT_POLICY_V1' and
         p['profile'] == PROFILE and p['image'] == IMAGE, 'fixed conditional profile')
    same_identity(p['packet'], PACKET)
    need(set(p['scorer_sources']) == set(SCIENCE), 'unchanged complete scientific scorer')
    for name, identity in SCIENCE.items():
        same_identity(p['scorer_sources'][name], identity)
        need(p['scorer_sources'][name]['path'] == str(here / 'science' / name), 'local unchanged science path')
    need(set(p['common_assistance']) == set(ASSISTANCE) and
         set(p['additional_B_assistance']) == set(OFFICIAL), 'same declared assistance')
    for name, identity in ASSISTANCE.items():
        same_identity(p['common_assistance'][name], identity)
    for name, identity in OFFICIAL.items():
        same_identity(p['additional_B_assistance'][name], identity)
    for role, name in [('inherited_owner', 'lifecycle_owner.py'), ('inherited_outer', 'lifecycle_outer.py')]:
        need(p[role] == r['source_files'][name], 'selected lifecycle source join')
    descriptor(p['source_input_selection'])
    same_identity(p['negative_source'], NEGATIVE)
    need(p['negative_source']['path'] == str(here / 'science' / 'make_negative_submission.py'), 'unchanged negative source')
    attempt_root = absolute(r['deployment']['attempts_root'])
    protected_inputs = [r['policy'], r['source_lock'], *r['source_files'].values(),
        *r['programs'].values(), p['packet'], p['source_input_selection'],
        *p['scorer_sources'].values(), *p['common_assistance'].values(),
        *p['additional_B_assistance'].values(), p['negative_source']]
    for pin in protected_inputs:
        need(not absolute(pin['path']).is_relative_to(attempt_root),
             'input/source files must stay outside all owned output attempts')
    selected = limits(r)
    need(preflight_reservation(r) + sum(selected['managed_stages']) * MIB <= selected['managed_cap'],
         'whole selected managed-read envelope')


def authenticate_source_graph(r, here):
    lock = decode(read_pin(r['source_lock']))
    need(lock['schema'] == 'PFC_PORTABLE_SOURCE_LOCK_V1' and
         type(lock['files']) is list and 1 <= len(lock['files']) <= 64, 'finite selected source lock')
    known = {}; total = 0
    for row in lock['files']:
        need(set(row) == {'relative_path', 'bytes', 'sha256'} and
             type(row['relative_path']) is str, 'source lock row')
        rel = Path(row['relative_path'])
        need(not rel.is_absolute() and '..' not in rel.parts and
             str(rel) not in known and rel.parts[0] == 'package', 'unique package-confined source')
        pin = {'path': str(here.parent / rel), 'bytes': row['bytes'], 'sha256': row['sha256']}
        total += row['bytes']; need(total <= 2 * MIB, 'complete source batch limit')
        read_pin(pin)
        known[str(rel)] = pin
    for name, pin in r['source_files'].items():
        need(known.get('package/' + name) == pin, 'request source joined to selected lock')
    return lock


def authenticate_host_python(d):
    need(str(Path(sys.executable).resolve()) == d['host_python']['path'], 'selected actual host interpreter')
    need(sys.flags.isolated and sys.flags.no_site and sys.flags.dont_write_bytecode,
         'isolated no-site no-bytecode host interpreter')
    read_pin(d['host_python'], 16 * MIB)


def authenticate_assets(p):
    # The complete historical selection is private metadata, not candidate input.
    # Do not follow its paths or reopen its nine scientific bodies here.
    lineage = decode(read_pin(p['source_input_selection']))
    need(lineage['schema'] == 'PFC_FULL99_CONDITIONAL_INPUT_SELECTION_V1' and
         set(lineage['inputs']) == LINEAGE_ROLES and
         lineage['total_encoded_bytes'] == sum(v['bytes'] for v in lineage['inputs'].values()) == 22183624,
         'exact complete owner-selected nine-input lineage manifest')
    for pin in lineage['inputs'].values():
        descriptor(pin, 32 * MIB)
    for pin in list(p['common_assistance'].values()) + list(p['additional_B_assistance'].values()):
        read_pin(pin)
    read_pin(p['packet'], 16 * MIB)


def authenticate_deployment(r, p, postflight=False):
    d = r['deployment']; authenticate_host_python(d)
    read_pin(d['docker_cli'], 64 * MIB)
    socket = absolute(d['docker_host'][7:]).lstat()
    need(stat.S_ISSOCK(socket.st_mode), 'selected existing Docker Unix socket')
    if not postflight:
        authenticate_assets(p)


def preflight_reservation(r):
    d = r['deployment']
    return 48 * MIB + 2 * (d['host_python']['bytes'] + d['docker_cli']['bytes'])


def limits(r):
    base = {'deadlines': (60, 180, 180, 660, 660),
            'output_caps': (0, 128*MIB, 128*MIB, 64*MIB, 64*MIB),
            'managed_stages': (16, 304, 304, 368, 368),
            'owner_seconds': 1830, 'outer_seconds': 1860,
            'managed_cap': 1536*MIB, 'retained_cap': 512*MIB}
    if r['compatibility']:
        base.update(deadlines=base['deadlines']+(60, 660),
                    output_caps=base['output_caps']+(128*MIB, 64*MIB),
                    managed_stages=(16,304,304,432,432,272,432),
                    owner_seconds=2550, outer_seconds=2580,
                    managed_cap=2560*MIB, retained_cap=768*MIB)
    return base


def safe_environment():
    return {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'LC_ALL': 'C',
            'PYTHONDONTWRITEBYTECODE': '1'}


def configure_client(engine, r, root):
    from route_binding import write_new
    directory = root / 'docker-client'
    directory.mkdir(mode=0o700, exist_ok=False)
    write_new(directory / 'config.json', {'auths': {}})
    d = r['deployment']
    engine.DOCKER_ARGV = [d['docker_cli']['path'], '--config', str(directory), '--host', d['docker_host']]
    engine.COMMAND_ENV = safe_environment()
