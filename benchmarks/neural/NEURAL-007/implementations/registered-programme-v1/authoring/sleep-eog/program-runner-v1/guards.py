"""Generated mutations of actual inspected metadata; no scientific data reads."""
import copy
import json
from sleep_common import HERE, ROOT, SHARED, need, ordinary, units, runtime, contract_profile, recovery_core, load_module
import grade_profile


def created(folder, name):
    for path in folder.glob('inspect-*-' + name + '.json'):
        saved = json.loads(ordinary(path, 200_000))
        if saved['returncode'] == 0:
            rows = json.loads(saved['stdout'])
            if len(rows) == 1 and rows[0].get('State', {}).get('Status') == 'created':
                return rows[0]
    raise ValueError('Original created-state inspection required')


def check(reference_attempt):
    task_recovery = load_module(HERE / 'recovery.py', '_sleep_guard_recovery')
    unit = units()[0]
    folder = reference_attempt / unit['unit_id']
    rows = json.loads(ordinary(folder / 'resource_ownership.json', 65_536))['owned']
    item = rows[-1]
    expected = task_recovery.contract(reference_attempt, folder, item)
    info = created(folder, item['name'])
    contract_profile.verify(info, item['name'], 'candidate', expected['mounts'], expected['profile'])
    changes = [
        ('network', lambda v: v['HostConfig'].__setitem__('NetworkMode', 'bridge')),
        ('writable_root', lambda v: v['HostConfig'].__setitem__('ReadonlyRootfs', False)),
        ('privileged', lambda v: v['HostConfig'].__setitem__('Privileged', True)),
        ('memory', lambda v: v['HostConfig'].__setitem__('Memory', 1)),
        ('command', lambda v: v['Config'].__setitem__('Cmd', ['-c', 'pass'])),
        ('training_writable', lambda v: next(r for r in v['Mounts'] if r['Destination'].startswith('/training/')).__setitem__('RW', True)),
        ('missing_training', lambda v: v['Mounts'].pop()),
        ('wrong_active_source', lambda v: next(r for r in v['Mounts'] if r['Destination'] == '/input/features.npz').__setitem__('Source', '/wrong-case.npz')),
        ('already_running', lambda v: v['State'].__setitem__('Running', True)),
    ]
    evidence = []
    for label, change in changes:
        bad = copy.deepcopy(info)
        change(bad)
        try:
            contract_profile.verify(bad, item['name'], 'candidate', expected['mounts'], expected['profile'])
        except (ValueError, KeyError):
            evidence.append({'name': label, 'rejected': True})
        else:
            raise ValueError('Boundary mutation accepted: ' + label)
    previous = copy.deepcopy(info)
    previous['Id'] = 'f' * 64 if info['Id'] != 'f' * 64 else 'e' * 64
    try:
        recovery_core.verify_live(info, expected, [previous])
    except ValueError:
        evidence.append({'name': 'replacement_id_refused', 'rejected': True})
    else:
        raise ValueError('Changed captured immutable ID accepted')
    grader = reference_attempt / 'grade'
    grader_item = json.loads(ordinary(grader / 'resource_ownership.json', 65_536))['owned'][0]
    grade_info = created(grader, grader_item['name'])
    grade_mounts = grade_profile.mounts_for(reference_attempt)
    for label, change in [
        ('grader_wrong_fsize', lambda v: next(r for r in v['HostConfig']['Ulimits'] if r['Name'] == 'fsize').__setitem__('Soft', 262144)),
        ('grader_private_writable', lambda v: next(r for r in v['Mounts'] if r['Destination'].startswith('/private/')).__setitem__('RW', True))]:
        bad = copy.deepcopy(grade_info)
        change(bad)
        try:
            grade_profile.verify(bad, grader_item['name'], grade_mounts)
        except ValueError:
            evidence.append({'name': label, 'rejected': True})
        else:
            raise ValueError('Trusted grader mutation accepted: ' + label)
    need(len(evidence) == 12, 'All twelve generated runtime guards')
    both = units()
    train = lambda u: [x for x in u['public_inputs'] if x['mount_destination'].startswith('/training/')]
    need(train(both[0]) == train(both[1]) and len(train(both[0])) == 20, 'Identical six-person training and helpers')
    active = lambda u: {x['path'] for x in u['public_inputs'] if x['mount_destination'] in ('/input/features.npz', '/input/model.npz')}
    need(active(both[0]).isdisjoint(active(both[1])), 'Two case-specific active file sets')
    return {'generated_runtime_guards': evidence, 'identical_training_file_count': 20, 'active_cases_disjoint': True}
