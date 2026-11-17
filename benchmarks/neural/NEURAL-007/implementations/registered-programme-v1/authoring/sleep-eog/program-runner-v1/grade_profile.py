"""Narrow grader-create policy; lifecycle and original profile guard are reused."""
import copy
import json
import stat
from sleep_common import HERE, ROOT, BaseEngine, need, ordinary, load_module

legacy = load_module(ROOT / 'benchmarks/neuroscience/neural-007-whole-night-sleep-scoring/score.py', '_sleep_qualified_score_profile')
IMAGE, THREADS, TMPFS = legacy.IMAGE, legacy.THREADS, legacy.TMPFS
ULIMITS = dict(legacy.ULIMITS, fsize=(1048576, 1048576))


def mounts_for(attempt):
    plan = json.loads(ordinary(ROOT / 'benchmarks/neuroscience/neural-007-whole-night-sleep-scoring/operator_assets.json', 16_384))
    mounts = {'/source/grader.py': str(HERE / 'grade_worker.py'),
              '/source/operator_assets.json': str(ROOT / 'benchmarks/neuroscience/neural-007-whole-night-sleep-scoring/operator_assets.json'),
              '/source/invocation.json': str(attempt / 'grade/invocation.json')}
    mounts.update({'/source/' + name: str(ROOT / pin['path']) for name, pin in plan['source_files'].items()})
    mounts.update({'/comparators/' + name + '.npz': str(ROOT / pin['path']) for name, pin in plan['comparators'].items()})
    mounts.update({'/private/' + name: str(ROOT / pin['path']) for name, pin in plan['private_files'].items()})
    mounts.update({'/submission/' + c['case_id'] + '.npz': str(attempt / c['case_id'] / 'predictions.npz') for c in plan['cases']})
    need(len(mounts) == 12 and all(not any(c in p for c in ',\r\n') for p in mounts.values()), 'Exact twelve literal binds')
    return mounts


def verify(info, name, mounts):
    need(len(mounts) == 12, 'Exactly twelve trusted mounts')
    need(len(info['HostConfig']['Ulimits']) == 4 and
         {x['Name']: (x['Soft'], x['Hard']) for x in info['HostConfig']['Ulimits']} == ULIMITS,
         'Only declared 1MiB aggregate-file extension')
    need(info['HostConfig']['AutoRemove'] is False and set(info.get('NetworkSettings', {}).get('Networks', {})) <= {'none'},
         'No implicit removal or extra network')
    checked = copy.deepcopy(info)
    for row in checked['HostConfig']['Ulimits']:
        if row['Name'] == 'fsize':
            row['Soft'], row['Hard'] = legacy.ULIMITS['fsize']
    environment = json.loads(ordinary(HERE / 'grader_environment.json', 8192))
    legacy.verify(checked, name, mounts, environment)
    return {'status': 'exact_boundary_verified', 'role': 'sleep_two_part_grader', 'file_mounts': 12,
            'qualified_guard_delta': 'fsize 262144 to1048576 for bounded temporary aggregate; no other relaxation'}


class GradeEngine(BaseEngine):
    def create_grade(self, name, mounts):
        argv = ['create', '--pull', 'never', '--name', name, '--network', 'none', '--read-only', '--user', '65534:65534',
                '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--memory', str(4 * 1024**3),
                '--memory-swap', str(4 * 1024**3), '--cpus', '2', '--pids-limit', '32', '--shm-size', '1048576',
                '--restart', 'no', '--log-driver', 'none', '--workdir', '/tmp', '--entrypoint', 'python',
                '--tmpfs', '/tmp:' + TMPFS['/tmp']]
        for key, (soft, hard) in ULIMITS.items():
            argv += ['--ulimit', f'{key}={soft}:{hard}']
        for key in THREADS:
            argv += ['--env', key + '=2']
        argv += ['--env', 'PYTHONDONTWRITEBYTECODE=1']
        for destination, source in mounts.items():
            argv += ['--mount', f'type=bind,src={source},dst={destination},readonly']
        argv += [IMAGE, '-I', '-B', '/source/grader.py']
        self.own('container', name, argv)
        need(self.run(argv).returncode == 0, 'Trusted grader create')
        info = self.inspect('container', name)
        return info, verify(info, name, mounts)
