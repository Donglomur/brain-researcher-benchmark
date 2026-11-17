"""Task-specific ownership reconstruction, with frozen generic identity checks."""
import json
import re
from sleep_common import HERE, ROOT, SHARED, BaseEngine, ProfileEngine, contract_profile, runtime, units
from sleep_common import recovery_core, need, ordinary, save
import grade_profile


def contract(attempt, folder, item):
    name, kind = item['name'], item['kind']
    capture = recovery_core.capture_request
    if folder == attempt / 'grade':
        need(kind == 'container' and re.fullmatch('sleep-score-[a-f0-9]{32}', name), 'Exact trusted grader namespace')
        mounts = grade_profile.mounts_for(attempt)
        observed = capture(grade_profile.GradeEngine, 'create_grade', (name, mounts))
        return {'argv': observed[2], 'kind': kind, 'name': name, 'module': grade_profile, 'mounts': mounts}
    unit = next((u for u in units() if folder == attempt / u['unit_id']), None)
    need(unit is not None, 'Exact two fixed unit folders')
    suffix = name.rsplit('-', 1)[-1]
    need(re.fullmatch('[a-f0-9]{32}', suffix), 'Exact random resource suffix')
    volume = 'dmfc-prog-volume-' + suffix
    if kind == 'volume':
        need(name == volume, 'Exact output volume')
        observed = capture(BaseEngine, 'volume', (name,))
        return {'argv': observed[2], 'kind': kind, 'name': name, 'module': contract_profile}
    need(kind == 'container' and name in ('dmfc-prog-holder-' + suffix, 'dmfc-prog-worker-' + suffix), 'Exact unit role')
    role = 'holder' if name.startswith('dmfc-prog-holder-') else 'candidate'
    if role == 'holder':
        mounts = {'/trusted/holder.py': {'type': 'bind', 'source': str(SHARED / 'holder_profile.py'), 'rw': False},
                  '/capture': {'type': 'volume', 'source': volume, 'rw': False}}
    else:
        mounts = {'/program/program.py': {'type': 'bind', 'source': str(attempt / 'program.py'), 'rw': False},
                  '/output': {'type': 'volume', 'source': volume, 'rw': True}}
        mounts.update({x['mount_destination']: {'type': 'bind', 'source': str(ROOT / x['path']), 'rw': False}
                       for x in unit['public_inputs']})
    profile = runtime(unit)
    observed = capture(ProfileEngine, 'create', (name, role, mounts), profile)
    return {'argv': observed[2], 'kind': kind, 'name': name, 'module': contract_profile,
            'mounts': mounts, 'role': role, 'profile': profile}


def recover(attempt, folder, item, engine, budget):
    """Caller must stop all activated host groups before invoking this function."""
    from absence import absence
    expected = contract(attempt, folder, item)
    kind, name = expected['kind'], expected['name']
    need(item['attempted_before_dispatch'] is True and item['canonical_create_argv'] == expected['argv'],
         'Original creation equals independently reconstructed task request')
    prior = json.loads(ordinary(folder / ('precreate-' + name + '.json'), 200_000))
    need(prior['kind'] == kind and prior['name'] == name and
         absence(prior['returncode'], prior['stdout'], prior['stderr'], kind, name), 'Original exact-name absence')
    count = 0
    def call(argv):
        nonlocal count
        count += 1
        need(count <= 4, 'Bounded inspect/remove/dual-absence recovery')
        proc = engine.run(argv, timeout=2, cap=100_000)
        row = {'argv': argv, 'returncode': proc.returncode,
               'stdout': proc.stdout.decode(errors='replace'), 'stderr': proc.stderr.decode(errors='replace')}
        save(engine.out / ('recovery-' + name + '-' + str(count) + '.json'), row, budget, cap=220_000)
        return row
    inspect = ['volume', 'inspect', name] if kind == 'volume' else ['inspect', '--type', 'container', name]
    first = call(inspect)
    if absence(first['returncode'], first['stdout'], first['stderr'], kind, name):
        return {'kind': kind, 'name': name, 'absence_verified': True, 'already_absent_no_removal': True}
    need(first['returncode'] == 0, 'Live exact inspection or strict absence')
    rows = json.loads(first['stdout'])
    need(type(rows) is list and len(rows) == 1, 'One live resource')
    captured = []
    paths = list(folder.glob('inspect-*-' + name + '.json'))
    need(len(paths) <= 8, 'Bounded saved inspection count')
    for path in paths:
        saved = json.loads(ordinary(path, 200_000))
        if saved['returncode'] == 0:
            values = json.loads(saved['stdout'])
            need(type(values) is list and len(values) == 1, 'One captured resource')
            captured.append(values[0])
    identity = recovery_core.verify_live(rows[0], expected, captured)
    call(['volume', 'rm', identity] if kind == 'volume' else ['rm', '--force', identity])
    by_id = call(['inspect', '--type', 'container', identity]) if kind == 'container' else None
    by_name = call(inspect)
    absent = absence(by_name['returncode'], by_name['stdout'], by_name['stderr'], kind, name)
    if by_id is not None:
        absent &= absence(by_id['returncode'], by_id['stdout'], by_id['stderr'], kind, identity)
    return {'kind': kind, 'name': name, 'verified_identity': identity, 'absence_verified': absent,
            'configuration_checked_before_removal': True, 'captured_identity_matches': len(captured),
            'volume_identity_limit': 'Docker has no immutable volume ID; name, exact tmpfs options and saved CreatedAt/Mountpoint are checked.' if kind == 'volume' else None}


def inventory(attempt):
    result = []
    for label in ('development-001', 'development-002', 'grade'):
        folder = attempt / label
        path = folder / 'resource_ownership.json'
        if not path.exists():
            continue
        rows = json.loads(ordinary(path, 65_536))['owned']
        need(type(rows) is list and len(rows) <= (1 if label == 'grade' else 3), 'Bounded ownership journal')
        if label != 'grade' and rows:
            suffix = rows[0]['name'].rsplit('-', 1)[-1]
            need([(x['kind'], x['name']) for x in rows] ==
                 [('volume', 'dmfc-prog-volume-' + suffix), ('container', 'dmfc-prog-holder-' + suffix),
                  ('container', 'dmfc-prog-worker-' + suffix)][:len(rows)], 'Exact sequential unit ownership')
        result.extend((folder, item) for item in rows)
    need(len({item['name'] for folder, item in result}) == len(result), 'Unique resources in one attempt')
    return result
