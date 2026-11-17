"""Three exact task profiles over the qualified ERP interactive lifecycle."""
import copy
import json
from pathlib import Path
from common import HERE, ROOT, Engine, legacy, need, assets, regular, strict, pinned

IMAGE = legacy.IMAGE
LABELS = ('prepare', 'candidate', 'grade')


def mapping(run, label):
    run = Path(run); need(label in LABELS, 'Fixed three-phase roster')
    if label == 'prepare':
        contract = strict(regular(HERE / 'PACKET_INTERFACE.json', 65536))
        value = {destination: (str(ROOT / pin['path']), True) for destination, pin in contract['readonly_mounts'].items()}
        value['/source/PACKET_INTERFACE.json'] = (str(HERE / 'PACKET_INTERFACE.json'), True)
        value['/out'] = (str(run / 'prepared'), False)
        need(len(value) == 11, 'Ten exact preparation RO files plus sole fresh output')
        return value
    if label == 'candidate':
        return {'/program/program.py': (str(run / 'program.py'), True),
                '/training/train_counts.npy': (str(run / 'prepared/train_counts.npy'), True),
                '/training/val_counts.npy': (str(run / 'prepared/val_counts.npy'), True),
                '/training/calibration.json': (str(run / 'prepared/calibration.json'), True),
                '/public/TASK.md': (str(HERE / 'TASK.md'), True)}
    reference = assets()['reference_admission']
    return {'/program/grader.py': (str(HERE / 'grader.py'), True),
            '/source/score_core.py': (str(HERE / 'score_core.py'), True),
            '/source/operator_assets.json': (str(run / 'grade/operator_assets.json'), True),
            '/source/invocation.json': (str(run / 'grade/invocation.json'), True),
            '/submission/probabilities.json': (str(run / 'probabilities.json'), True),
            '/public/cases.json': (str(run / 'prepared/cases.json'), True),
            '/private/labels.json': (str(run / 'prepared/labels.json'), True),
            '/private/references.json': (str(run / 'prepared/references.json'), True),
            '/private/prepare_receipt.json': (str(run / 'prepared/prepare_receipt.json'), True),
            '/private/reference_admission.json': (str(ROOT / reference['path']), True)}


def command(label):
    need(label in LABELS, 'Exact phase command')
    return ['-I', '-B', '/source/prepare.py' if label == 'prepare' else '/program/program.py' if label == 'candidate' else '/program/grader.py']


def limits(label):
    cpu = {'prepare': (39, 40), 'candidate': (119, 120), 'grade': (19, 20)}[label]
    size = 2620000 if label == 'prepare' else 5000000
    return {**legacy.ULIMITS, 'cpu': cpu, 'fsize': (size, size)}


def create_args(name, label, mounts):
    argv = ['create', '--pull', 'never', '--name', name, '--network', 'none', '--read-only', '--user', '65534:65534',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--memory', str(3 * 1024**3),
            '--memory-swap', str(3 * 1024**3), '--cpus', '1.75', '--pids-limit', '32', '--shm-size', '1048576',
            '--log-driver', 'none', '--workdir', '/tmp', '--entrypoint', 'python', '--tmpfs', '/tmp:' + legacy.TMPFS['/tmp']]
    if label == 'candidate': argv += ['-i']
    for key, (lo, hi) in limits(label).items(): argv += ['--ulimit', f'{key}={lo}:{hi}']
    for key in legacy.THREADS: argv += ['--env', key + '=2']
    argv += ['--env', 'PYTHONDONTWRITEBYTECODE=1']
    for destination, (source, ro) in mounts.items():
        need(source.startswith('/') and not any(c in source for c in ',\r\n'), 'Exact literal mount')
        argv += ['--mount', f'type=bind,src={source},dst={destination}' + (',readonly' if ro else '')]
    return argv + [IMAGE, *command(label)]


def verify_exact(info, name, label, mounts, base_env):
    h, c = info['HostConfig'], info['Config']
    need(h['Memory'] == h['MemorySwap'] == 3 * 1024**3 and h['NanoCpus'] == 1750000000,
         'Exact1.75CPU/3GiB inside aggregate2CPU/4GiB')
    need('OomKillDisable' in h and (h['OomKillDisable'] is None or h['OomKillDisable'] is False), 'Strict null/False OOM setting')
    need(c['Cmd'] == command(label) and c.get('StdinOnce') is (label == 'candidate')
         and len(h['Ulimits']) == len(limits(label))
         and {r['Name']: (r['Soft'], r['Hard']) for r in h['Ulimits']} == limits(label), 'Exact task command/limits')
    environment = dict(base_env); environment.update({k: '2' for k in legacy.THREADS}, PYTHONDONTWRITEBYTECODE='1')
    normalized = copy.deepcopy(info)
    normalized['HostConfig']['Memory'] = normalized['HostConfig']['MemorySwap'] = 4 * 1024**3
    normalized['HostConfig']['NanoCpus'] = 2000000000
    normalized['HostConfig']['Ulimits'] = [{'Name': k, 'Soft': lo, 'Hard': hi} for k, (lo, hi) in legacy.ULIMITS.items()]
    program = 'prepare.py' if label == 'prepare' else 'program.py' if label == 'candidate' else 'grader.py'
    normalized['Config']['Cmd'] = ['-I', '-B', '/program/' + program]
    legacy.verify(normalized, name, mounts, environment, '65534:65534', program, label == 'candidate')
    need(h['AutoRemove'] is False, 'Owned removal remains explicit')
    return {'status': 'exact_choice_stream_boundary_verified', 'label': label,
            'readonly_mounts': sum(ro for _, ro in mounts.values()), 'interactive': label == 'candidate',
            'declared_profile_delta_verified': True}


class StreamEngine(Engine):
    def create_task(self, name, label, mounts, environment):
        argv = create_args(name, label, mounts)
        self.own('container', name, argv)
        reply = self.run(argv)
        need(reply.returncode == 0, 'Owned task created')
        inspected = self.inspect('container', name)
        return inspected, verify_exact(inspected, name, label, mounts, environment)
