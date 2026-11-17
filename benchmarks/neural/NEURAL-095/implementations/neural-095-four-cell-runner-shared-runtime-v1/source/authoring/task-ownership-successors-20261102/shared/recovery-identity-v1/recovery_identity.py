"""Narrow captured-ID recovery shared by three task-local successors.

Only explicit Docker OomKillDisable false/null is normalized. All other
configuration fields and ordered lists retain exact captured equality. This is
source-proposed recovery, not evidence that any new path has been executed.
"""
import copy
import json
import os
from pathlib import Path
import re
import stat
from types import SimpleNamespace
import uuid
from absence import absence


def need(ok, message):
    if not ok:
        raise ValueError(message)


def read_json(path, cap=200000):
    path = Path(path)
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'Unlinked recovery evidence')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded single-link recovery evidence')
        with os.fdopen(fd, 'rb', closefd=False) as stream:
            body = stream.read(cap + 1)
        after = os.fstat(fd)
        need(all(getattr(before, k) == getattr(after, k) for k in
                 ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns')) and len(body) == before.st_size,
             'Stable recovery evidence')
    finally:
        os.close(fd)
    return json.loads(body)


def normalized_oom_policy(info):
    need(type(info) is dict and type(info.get('HostConfig')) is dict and
         'OomKillDisable' in info['HostConfig'], 'Explicit Docker OOM policy')
    value = info['HostConfig']['OomKillDisable']
    need(value is None or value is False, 'Only explicit null or false OOM policy')
    result = copy.deepcopy(info)
    result['HostConfig']['OomKillDisable'] = False
    return result


class RequestCaptured(Exception):
    pass


def capture_request(engine_class, method, args, profile=None):
    """Same qualified constructor capture: replace every I/O entry point."""
    class Capture(engine_class):
        def own(self, kind, name, argv):
            self.captured = (kind, name, argv)
        def run(self, *unused, **kwargs):
            return SimpleNamespace(returncode=0)
        def inspect(self, *unused):
            raise RequestCaptured()
    instance = object.__new__(Capture)
    if profile is not None:
        instance.profile = profile
    try:
        getattr(instance, method)(*args)
    except RequestCaptured:
        return instance.captured
    raise ValueError('Frozen constructor did not reach captured inspect')


def verify_live(info, expected, captured):
    kind, name = expected['kind'], expected['name']
    if kind == 'volume':
        need(info.get('Name') == name and info.get('Driver') == 'local' and info.get('Scope') == 'local' and
             info.get('Options') == {'type': 'tmpfs', 'device': 'tmpfs', 'o': expected['module'].VOLUME_OPTIONS} and
             type(info.get('CreatedAt')) is str and bool(info['CreatedAt']) and
             type(info.get('Mountpoint')) is str and bool(info['Mountpoint']), 'Exact live local tmpfs volume')
        for before in captured:
            need(all(before.get(key) == info.get(key) for key in
                     ('Name', 'Driver', 'Scope', 'Options', 'CreatedAt', 'Mountpoint')),
                 'Volume matches every captured creation identity')
        return name
    current = normalized_oom_policy(info)
    need(type(current.get('Id')) is str and re.fullmatch('[a-f0-9]{64}', current['Id']) and
         type(current.get('Name')) is str and current['Name'].startswith('/') and len(current['Name']) > 1,
         'Exact live immutable ID and recorded current name')
    need(bool(captured), 'Container creation identity must have been durably captured')
    for old in captured:
        before = normalized_oom_policy(old)
        need(before.get('Name') == '/' + name and
             all(before.get(key) == current.get(key) for key in ('Id', 'Image', 'Config', 'HostConfig')),
             'Live immutable ID/configuration matches every captured inspect')
    state = current.get('State')
    need(type(state) is dict and state.get('Status') in
         ('created', 'running', 'paused', 'restarting', 'exited', 'dead', 'removing') and
         type(state.get('Running')) is bool, 'Recognized current lifecycle')
    checked = copy.deepcopy(current)
    # Captured immutable ID authorizes a renamed resource; no new name is owned.
    # The unchanged constructor profile still checks its original declared name.
    checked['Name'] = '/' + name
    checked['State'].update(Status='created', Running=False, Pid=0)
    if 'role' in expected:
        expected['module'].verify(checked, name, expected['role'], expected['mounts'], expected['profile'])
    else:
        expected['module'].verify(checked, name, expected['mounts'])
    return current['Id']


def recover_one(engine, folder, item, expected):
    """Return unresolved on every error; callers must still recover other items."""
    folder = Path(folder)
    kind, name = expected['kind'], expected['name']
    result = {'kind': kind, 'name': name, 'absence_verified': False, 'evidence_files': []}
    calls = 0
    token = uuid.uuid4().hex
    def call(argv):
        nonlocal calls
        calls += 1
        need(calls <= 14, 'Bounded captured-ID recovery calls')
        proc = engine.run(argv, timeout=2, cap=65536)
        stdout = proc.stdout.decode(errors='replace') if isinstance(proc.stdout, bytes) else proc.stdout
        stderr = proc.stderr.decode(errors='replace') if isinstance(proc.stderr, bytes) else proc.stderr
        need(type(stdout) is str and type(stderr) is str and len(stdout.encode()) <= 65536 and
             len(stderr.encode()) <= 4096, 'Complete bounded recovery replies')
        row = {'argv': argv, 'returncode': proc.returncode, 'stdout': stdout, 'stderr': stderr}
        evidence = engine.write('id-recovery-' + token + '-' + str(calls) + '.json', row, cap=150000)
        result['evidence_files'].append(str(evidence))
        return row
    def is_absent(row, identifier):
        return absence(row['returncode'], row['stdout'], row['stderr'], kind, identifier)
    def object_row(row):
        need(row['returncode'] == 0, 'Successful inspect or exact absence required')
        value = json.loads(row['stdout'])
        need(type(value) is list and len(value) == 1 and type(value[0]) is dict, 'Exactly one inspected resource')
        return value[0]
    try:
        need(kind in ('container', 'volume') and type(name) is str and
             re.fullmatch('[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', name), 'Fixed resource namespace')
        need(item.get('kind') == kind and item.get('name') == name and
             item.get('attempted_before_dispatch') is True and item.get('canonical_create_argv') == expected['argv'],
             'Original ownership request matches independent fixed constructor')
        prior = read_json(folder / ('precreate-' + name + '.json'))
        need(prior['kind'] == kind and prior['name'] == name and is_absent(prior, name),
             'Exact resource absence before creation intent')
        paths = sorted(folder.glob('inspect-*-' + name + '.json'))
        inspection_cap = 192 if expected.get('role') == 'holder' else 8
        need(len(paths) <= inspection_cap, 'Bounded captured inspection inventory (holder readiness polls included)')
        captured = []
        for path in paths:
            saved = read_json(path)
            if saved['returncode'] == 0:
                captured.append(object_row(saved))
        inspect_name = ['volume', 'inspect', name] if kind == 'volume' else ['inspect', '--type', 'container', name]
        named = call(inspect_name)
        if kind == 'volume':
            result['volume_identity_policy'] = 'Name plus exact local tmpfs/captured CreatedAt and Mountpoint; Docker has no volume immutable ID'
            need(bool(captured), 'Volume create without captured completed identity remains unresolved')
            verify_live(captured[0], expected, captured)
            if is_absent(named, name):
                result.update(absence_verified=True, already_absent_no_removal=True)
                return result
            identity = verify_live(object_row(named), expected, captured)
            call(['volume', 'rm', identity])
            result.update(absence_verified=is_absent(call(inspect_name), name), verified_identity=identity)
            return result
        ids = sorted(set(row.get('Id') for row in captured if type(row.get('Id')) is str))
        need(len(ids) <= 8 and all(re.fullmatch('[a-f0-9]{64}', x) for x in ids), 'Captured immutable container IDs')
        result['captured_ids'] = ids
        # Probe every captured ID before deciding whether identity evidence is coherent.
        id_rows = [(identity, call(['inspect', '--type', 'container', identity])) for identity in ids]
        need(all(type(row.get('Id')) is str and re.fullmatch('[a-f0-9]{64}', row['Id']) and
                 row.get('Name') == '/' + name for row in captured),
             'Every successful saved inspect retains its original name and valid ID')
        need(len(ids) == 1, 'Attempted create without one captured ID remains unresolved')
        identity, by_id = id_rows[0]
        name_absent = is_absent(named, name)
        id_absent = is_absent(by_id, identity)
        if name_absent and id_absent:
            result.update(absence_verified=True, verified_identity=identity, already_absent_no_removal=True,
                          immutable_id_and_name_absence=True)
            return result
        if not name_absent:
            need(object_row(named).get('Id') == identity, 'Original name still refers to captured immutable ID')
        need(not id_absent, 'Name and captured ID observations must agree')
        current = object_row(by_id)
        verified = verify_live(current, expected, captured)
        need(verified == identity, 'Removal identifier is the uniquely captured ID')
        result['observed_current_name'] = current['Name']
        result['renamed_identity'] = current['Name'] != '/' + name
        call(['rm', '--force', identity])
        id_after = call(['inspect', '--type', 'container', identity])
        name_after = call(inspect_name)
        result.update(absence_verified=is_absent(id_after, identity) and is_absent(name_after, name),
                      verified_identity=identity, container_removed_by_immutable_id=True,
                      configuration_verified_before_removal=True, saved_inspections_matched=len(captured),
                      immutable_id_and_name_absence=is_absent(id_after, identity) and is_absent(name_after, name))
    except BaseException as error:
        result['error'] = repr(error)
    return result
