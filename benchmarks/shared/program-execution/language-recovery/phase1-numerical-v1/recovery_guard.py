"""Task-local exact recovery policy, reusing immutable lifecycle/profile code.

No candidate imports or input-value reads. Calling code stops all owned host
groups first. Raw daemon replies are retained before any semantic assertion.
"""
import copy
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def need(ok, message):
    if not ok:
        raise ValueError(message)


class RequestCaptured(Exception):
    pass


def capture_request(engine_class, method, args, profile=None):
    """Execute only the frozen request constructor; every I/O method is replaced."""
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


def contract(stage, run, folder, item, ordinary, build_result=None):
    """Reconstruct paths from this fixed task; never trust journal mount paths."""
    from common import BaseEngine
    import runtime as summary
    name, kind = item['name'], item['kind']
    if stage == 'qualify':
        need(folder.parent == run / 'metadata' and kind == 'container' and
             re.fullmatch('summary-score-[a-f0-9]{12}', name), 'Exact summary namespace')
        need(build_result is not None, 'Reviewed build result required for summary recovery')
        reference = build_result['reference']
        mounts = {
            '/grader/worker.py': str(HERE / 'worker.py'),
            '/grader/score_core.py': str(HERE / 'score_core.py'),
            '/grader/PUBLIC_CONTRACT.json': str(HERE / 'PUBLIC_CONTRACT.json'),
            '/grader/worker_inputs.json': str(run / 'worker_inputs.json'),
            '/private/reference.json': str(ROOT / reference['path']),
            '/candidate/submission.json': str(run / 'inputs' / (folder.name + '.json'))}
        observed = capture_request(summary.SummaryEngine, 'create_summary', (name, mounts))
        return {'argv': observed[2], 'kind': kind, 'name': name, 'module': summary, 'mounts': mounts}
    need(stage == 'build' and folder == run / 'unit', 'Exact builder namespace')
    sys.path.insert(0, str(ROOT / 'authoring/shared-program-runner-v2'))
    try:
        from engine_profile import ProfileEngine
        import contract_profile as program
    finally:
        sys.path.remove(str(ROOT / 'authoring/shared-program-runner-v2'))
    suffix = name.rsplit('-', 1)[-1]
    need(re.fullmatch('[a-f0-9]{32}', suffix), 'Exact random builder suffix')
    volume = 'dmfc-prog-volume-' + suffix
    if kind == 'volume':
        need(name == volume, 'Exact volume name')
        observed = capture_request(BaseEngine, 'volume', (name,))
        return {'argv': observed[2], 'kind': kind, 'name': name, 'module': program}
    need(kind == 'container' and name in ('dmfc-prog-holder-' + suffix, 'dmfc-prog-worker-' + suffix),
         'Exact builder role')
    manifest = json.loads(ordinary(HERE / 'ALLOWED_INPUTS.json', 32_768))
    destinations = ['/input/' + alias + '.data' for alias in manifest['files']]
    destinations += ['/input/' + file for file in ('reference_builder.py', 'ALLOWED_INPUTS.json', 'PUBLIC_CONTRACT.json')]
    profile = {'public_destinations': tuple(destinations), 'output_name': 'reference.json', 'max_output_bytes': 500_000}
    if name.startswith('dmfc-prog-holder-'):
        role = 'holder'
        mounts = {'/trusted/holder.py': {'type': 'bind', 'source': str(ROOT / 'authoring/shared-program-runner-v2/holder_profile.py'), 'rw': False},
                  '/capture': {'type': 'volume', 'source': volume, 'rw': False}}
    else:
        role = 'candidate'
        mounts = {'/program/program.py': {'type': 'bind', 'source': str(HERE / 'build_program.py'), 'rw': False},
                  '/output': {'type': 'volume', 'source': volume, 'rw': True}}
        mounts.update({'/input/' + alias + '.data': {'type': 'bind', 'source': str(ROOT / pin['path']), 'rw': False}
                       for alias, pin in manifest['files'].items()})
        mounts.update({'/input/' + file: {'type': 'bind', 'source': str(HERE / file), 'rw': False}
                       for file in ('reference_builder.py', 'ALLOWED_INPUTS.json', 'PUBLIC_CONTRACT.json')})
    observed = capture_request(ProfileEngine, 'create', (name, role, mounts), profile)
    return {'argv': observed[2], 'kind': kind, 'name': name, 'module': program, 'mounts': mounts,
            'role': role, 'profile': profile}


def verify_live(info, expected, captured):
    kind, name = expected['kind'], expected['name']
    if kind == 'volume':
        module = expected['module']
        need(info.get('Name') == name and info.get('Driver') == 'local' and info.get('Scope') == 'local' and
             info.get('Options') == {'type': 'tmpfs', 'device': 'tmpfs', 'o': module.VOLUME_OPTIONS} and
             type(info.get('CreatedAt')) is str and bool(info['CreatedAt']) and
             type(info.get('Mountpoint')) is str and bool(info['Mountpoint']), 'Exact live local tmpfs volume')
        for before in captured:
            need(all(before.get(key) == info.get(key) for key in ('Name', 'Driver', 'Scope', 'Options', 'CreatedAt', 'Mountpoint')),
                 'Volume matches all captured creation identities')
        return name
    identity = info.get('Id')
    need(type(identity) is str and re.fullmatch('[a-f0-9]{64}', identity) and info.get('Name') == '/' + name,
         'Exact live immutable container ID and name')
    for before in captured:
        need(all(before.get(key) == info.get(key) for key in ('Id', 'Name', 'Image', 'Config', 'HostConfig')),
             'Live identity/configuration matches all captured inspections')
    state = info.get('State')
    need(type(state) is dict and state.get('Status') in ('created', 'running', 'paused', 'restarting', 'exited', 'dead', 'removing') and
         type(state.get('Running')) is bool, 'Recognized current lifecycle')
    checked = copy.deepcopy(info)
    checked['State'].update(Status='created', Running=False, Pid=0)
    if 'role' in expected:
        expected['module'].verify(checked, name, expected['role'], expected['mounts'], expected['profile'])
    else:
        expected['module'].verify(checked, name, expected['mounts'])
    return identity


def recover(stage, run, folder, item, engine, ordinary, budget, build_result=None):
    from absence import absence
    expected = contract(stage, run, folder, item, ordinary, build_result)
    kind, name = expected['kind'], expected['name']
    need(item['attempted_before_dispatch'] is True and item['canonical_create_argv'] == expected['argv'],
         'Journal request matches exact immutable constructor and task paths')
    prior = json.loads(ordinary(folder / ('precreate-' + name + '.json'), 200_000))
    need(prior['kind'] == kind and prior['name'] == name and
         absence(prior['returncode'], prior['stdout'], prior['stderr'], kind, name), 'Exact absence before creation intent')
    files, calls = [], 0
    def call(argv):
        nonlocal calls
        calls += 1
        need(calls <= 4, 'At most inspect/remove/ID absence/name absence')
        proc = engine.run(argv, timeout=2, cap=65_536)
        need(len(proc.stdout) <= 65_536 and len(proc.stderr) <= 4096, 'Complete bounded recovery reply')
        row = {'argv': argv, 'returncode': proc.returncode,
               'stdout': proc.stdout.decode(errors='replace'), 'stderr': proc.stderr.decode(errors='replace')}
        body = (json.dumps(row, indent=2) + '\n').encode()
        need(len(body) <= 150_000, 'Recovery raw evidence cap')
        path = run / ('recovery-' + name + '-' + str(calls) + '.json')
        budget.write(path, body, receipt=True, mode=0o444)
        files.append(str(path.relative_to(run)))
        return row
    inspect = ['volume', 'inspect', name] if kind == 'volume' else ['inspect', '--type', 'container', name]
    first = call(inspect)
    result = {'kind': kind, 'name': name, 'absence_verified': False, 'evidence_files': files}
    if absence(first['returncode'], first['stdout'], first['stderr'], kind, name):
        return {**result, 'absence_verified': True, 'already_absent_no_removal': True}
    need(first['returncode'] == 0, 'Successful live inspect or exact absence required')
    rows = json.loads(first['stdout']); need(type(rows) is list and len(rows) == 1, 'Exactly one inspected object')
    paths = list(folder.glob('inspect-*-' + name + '.json'))
    need(len(paths) <= 8, 'Bounded saved inspection inventory')
    captured = []
    for path in paths:
        saved = json.loads(ordinary(path, 200_000))
        if saved['returncode'] == 0:
            previous = json.loads(saved['stdout'])
            need(type(previous) is list and len(previous) == 1, 'Exactly one saved object')
            captured.append(previous[0])
    identity = verify_live(rows[0], expected, captured)
    call(['volume', 'rm', identity] if kind == 'volume' else ['rm', '--force', identity])
    if kind == 'container':
        by_id = call(['inspect', '--type', 'container', identity])
        by_name = call(inspect)
        absent = absence(by_id['returncode'], by_id['stdout'], by_id['stderr'], kind, identity) and \
                 absence(by_name['returncode'], by_name['stdout'], by_name['stderr'], kind, name)
    else:
        by_name = call(inspect)
        absent = absence(by_name['returncode'], by_name['stdout'], by_name['stderr'], kind, name)
    return {**result, 'absence_verified': absent, 'verified_identity': identity,
            'container_removed_by_immutable_id': kind == 'container',
            'volume_identity_policy': 'Name plus local tmpfs configuration and captured CreatedAt/Mountpoint; Docker volume API has no immutable ID' if kind == 'volume' else None,
            'saved_inspections_matched': len(captured), 'configuration_verified_before_removal': True}
