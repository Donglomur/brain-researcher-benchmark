"""Profile-aware immutable-ID recovery for normal units and stopped outer groups.

Required captured-source injections: BaseEngine, HostBudget, regular, digest,
snapshot, absence, contract. The outer supplies its independently reconstructed
program/unit and existing budget; this file never imports task/scientific code.
"""
import copy
import json
import os
from pathlib import Path
import re
import stat
import uuid

ROOT = Path(__file__).resolve().parents[4]
SHARED = ROOT / 'authoring/shared-program-runner-v2'
need = contract.require


def read_json(path, cap=200000):
    path = Path(path).absolute()
    need(path.is_relative_to(ROOT) and '..' not in path.parts and
         all(not x.is_symlink() for x in (path, *path.parents)), 'Unlinked project recovery evidence')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded single-link recovery metadata')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        after = os.fstat(fd)
        need(len(body) == before.st_size and all(getattr(before, k) == getattr(after, k)
             for k in ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')), 'Stable captured metadata')
    finally:
        os.close(fd)
    def unique(pairs):
        result = {}
        for key, value in pairs:
            need(key not in result, 'Unique recovery metadata keys')
            result[key] = value
        return result
    return json.loads(body, object_pairs_hook=unique,
                      parse_constant=lambda unused: need(False, 'Finite recovery metadata'))


def verify_live(info, expected, captured):
    kind, name = expected['kind'], expected['name']
    need(bool(captured), 'Completed saved creation inspection is required')
    if kind == 'volume':
        need(info.get('Name') == name and info.get('Driver') == info.get('Scope') == 'local' and
             info.get('Options') == {'type': 'tmpfs', 'device': 'tmpfs', 'o': contract.VOLUME_OPTIONS} and
             type(info.get('CreatedAt')) is str and bool(info['CreatedAt']) and
             type(info.get('Mountpoint')) is str and bool(info['Mountpoint']), 'Exact local tmpfs identity')
        for old in captured:
            need(all(old.get(k) == info.get(k) for k in
                 ('Name', 'Driver', 'Scope', 'Options', 'CreatedAt', 'Mountpoint')), 'Every captured volume identity agrees')
        return name
    current = contract.normalized_configuration(info)
    identity = current.get('Id')
    need(type(identity) is str and re.fullmatch('[a-f0-9]{64}', identity) and
         type(current.get('Name')) is str and current['Name'].startswith('/') and len(current['Name']) > 1,
         'Exact live immutable ID/current name')
    for old in captured:
        before = contract.normalized_configuration(old)
        need(before.get('Name') == '/' + name and all(before.get(k) == current.get(k)
             for k in ('Id', 'Image', 'Config', 'HostConfig', 'Mounts')), 'Complete captured configuration and mounts agree')
    state = current.get('State')
    need(type(state) is dict and state.get('Status') in
         ('created', 'running', 'paused', 'restarting', 'exited', 'dead', 'removing') and
         type(state.get('Running')) is bool, 'Recognized current lifecycle')
    checked = copy.deepcopy(current)
    # Only a uniquely captured immutable ID may be recovered after a rename.
    checked['Name'] = '/' + name
    checked['State'].update(Status='created', Running=False, Pid=0)
    contract.verify(checked, name, expected['role'], expected['mounts'], expected['profile'])
    return identity


def recover_resource(engine, folder, item, expected):
    """Every exception is unresolved; callers must continue other owned resources."""
    folder = Path(folder)
    kind, name = expected['kind'], expected['name']
    result = {'kind': kind, 'name': name, 'absence_verified': False, 'evidence_files': []}
    token = uuid.uuid4().hex; calls = 0
    def call(argv):
        nonlocal calls
        calls += 1
        need(calls <= 14, 'Bounded recovery command count')
        proc = engine.run(argv, timeout=2, cap=65536)
        stdout = proc.stdout.decode('utf-8', errors='replace')
        stderr = proc.stderr.decode('utf-8', errors='replace')
        need(len(stdout.encode()) <= 65536 and len(stderr.encode()) <= 4096, 'Complete bounded recovery replies')
        row = {'argv': argv, 'returncode': proc.returncode, 'stdout': stdout, 'stderr': stderr}
        path = engine.write('id-recovery-' + token + '-' + str(calls) + '.json', row, cap=150000)
        result['evidence_files'].append(str(path.relative_to(folder)))
        return row
    def missing(row, identity):
        return absence(row['returncode'], row['stdout'], row['stderr'], kind, identity)
    def object_row(row):
        need(row['returncode'] == 0, 'Successful inspection or exact absence')
        rows = json.loads(row['stdout'])
        need(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict, 'One inspected resource')
        return rows[0]
    try:
        need(kind in ('container', 'volume') and re.fullmatch('dmfc-prog-(volume|holder|worker)-[a-f0-9]{32}', name),
             'Exact inherited unit resource namespace')
        need(item.get('kind') == kind and item.get('name') == name and item.get('attempted_before_dispatch') is True and
             item.get('canonical_create_argv') == expected['argv'], 'Durable request matches independently reconstructed constructor')
        prior = read_json(folder / ('precreate-' + name + '.json'))
        need(prior['kind'] == kind and prior['name'] == name and missing(prior, name), 'Exact pre-create absence')
        paths = sorted(folder.glob('inspect-*-' + name + '.json'))
        need(len(paths) <= (192 if expected.get('role') == 'holder' else 8), 'Bounded saved inspection roster')
        captured = []
        for path in paths:
            value = read_json(path)
            if value['returncode'] == 0:
                captured.append(object_row(value))
        inspect_name = ['volume', 'inspect', name] if kind == 'volume' else ['inspect', '--type', 'container', name]
        if kind == 'volume':
            need(bool(captured), 'Attempted volume create without completed identity stays unresolved')
            verify_live(captured[0], expected, captured)
            named = call(inspect_name)
            result['volume_identity_limit'] = 'Exact name/local tmpfs/CreatedAt/Mountpoint; Docker supplies no immutable volume ID.'
            if missing(named, name):
                result.update(absence_verified=True, already_absent_no_removal=True)
                return result
            identity = verify_live(object_row(named), expected, captured)
            call(['volume', 'rm', identity])
            result.update(absence_verified=missing(call(inspect_name), name), verified_identity=identity)
            return result
        created = read_json(folder / ('created-' + name + '.json'), 20000)
        identity = created.get('immutable_id')
        need(created.get('kind') == 'container' and created.get('name') == name and
             created.get('canonical_create_argv') == expected['argv'] and created.get('returncode') == 0 and
             created.get('recorded_before_inspect') is True and type(identity) is str and
             re.fullmatch('[a-f0-9]{64}', identity) and created.get('stdout') in (identity, identity + '\n'),
             'Durable exact immutable create result')
        need(bool(captured) and all(x.get('Id') == identity and x.get('Name') == '/' + name for x in captured),
             'Every successful inspection matches original create ID/name; missing inspection stays unresolved')
        verify_live(captured[0], expected, captured)
        named = call(inspect_name)
        by_id = call(['inspect', '--type', 'container', identity])
        name_absent, id_absent = missing(named, name), missing(by_id, identity)
        if name_absent and id_absent:
            result.update(absence_verified=True, verified_identity=identity, already_absent_no_removal=True,
                          immutable_id_and_name_absence=True)
            return result
        if not name_absent:
            need(object_row(named).get('Id') == identity, 'Original name has not been replaced by another container')
        need(not id_absent, 'Name and immutable ID observations agree')
        current = object_row(by_id)
        need(verify_live(current, expected, captured) == identity, 'Exact captured ID/configuration before removal')
        result['observed_current_name'] = current['Name']
        result['renamed_identity'] = current['Name'] != '/' + name
        call(['rm', '--force', identity])
        id_after = call(['inspect', '--type', 'container', identity]); name_after = call(inspect_name)
        absent = missing(id_after, identity) and missing(name_after, name)
        result.update(absence_verified=absent, verified_identity=identity, container_removed_by_immutable_id=True,
                      configuration_verified_before_removal=True, immutable_id_and_name_absence=absent,
                      saved_inspections_matched=len(captured))
    except BaseException as error:
        result['error'] = repr(error)[:1024]
    return result


def recover_unit(attempt, end, budget, program, unit):
    """Outer calls only after owned group absence; unit/program come from its fixed schedule."""
    attempt = Path(attempt).absolute(); program = Path(program).absolute()
    need(attempt.is_relative_to(ROOT / 'artifacts-build') and all(not p.is_symlink() for p in (attempt, *attempt.parents)) and
         program.is_relative_to(ROOT) and all(not p.is_symlink() for p in (program, *program.parents)), 'Exact unlinked task paths')
    journal = attempt / 'resource_ownership.json'
    if not journal.exists():
        return []  # Original own() journals before every create; stopped group cannot create later.
    rows = read_json(journal, 65536)['owned']
    need(type(rows) is list and len(rows) <= 3, 'At most three attempted unit resources')
    if not rows:
        return []
    suffix = rows[0]['name'].rsplit('-', 1)[-1]
    need(re.fullmatch('[a-f0-9]{32}', suffix) and [(x['kind'], x['name']) for x in rows] ==
         [('volume', 'dmfc-prog-volume-' + suffix), ('container', 'dmfc-prog-holder-' + suffix),
          ('container', 'dmfc-prog-worker-' + suffix)][:len(rows)], 'Exact original creation order and common suffix')
    profile = {'public_destinations': tuple(x['mount_destination'] for x in unit['public_inputs']),
               'output_name': unit['output_filename'], 'max_output_bytes': unit['max_output_bytes']}
    volume = 'dmfc-prog-volume-' + suffix
    expected = {volume: {'kind': 'volume', 'name': volume, 'argv': contract.volume_argv(volume)}}
    for role, prefix in (('holder', 'holder'), ('candidate', 'worker')):
        name = 'dmfc-prog-' + prefix + '-' + suffix
        if role == 'holder':
            mounts = {'/trusted/holder.py': {'type': 'bind', 'source': str(SHARED / 'holder_profile.py'), 'rw': False},
                      '/capture': {'type': 'volume', 'source': volume, 'rw': False}}
        else:
            mounts = {'/program/program.py': {'type': 'bind', 'source': str(program), 'rw': False},
                      '/output': {'type': 'volume', 'source': volume, 'rw': True}}
            mounts.update({x['mount_destination']: {'type': 'bind', 'source': str(ROOT / x['path']), 'rw': False}
                           for x in unit['public_inputs']})
        expected[name] = {'kind': 'container', 'name': name, 'role': role, 'mounts': mounts, 'profile': profile,
                          'argv': contract.create_argv(name, role, mounts, profile)}
    engine = BaseEngine(end, attempt, budget)
    return [recover_resource(engine, attempt, row, expected[row['name']]) for row in reversed(rows)]
