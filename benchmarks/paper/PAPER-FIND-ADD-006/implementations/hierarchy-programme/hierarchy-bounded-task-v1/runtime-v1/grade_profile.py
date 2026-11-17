"""Task-local hierarchy grader profile over the held summary lifecycle.

Only /grade is writable. Private files receive extent/path checks on the host;
the trusted worker authenticates their bytes after complete public admission.
"""
import json
import os
from pathlib import Path
import re
import stat
from common import BaseEngine, ROOT, need, ordinary, pinned, strict_json
from files import path as repo
from absence import absence

IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
MEMORY = 1024 ** 3
NANO_CPUS = 1_000_000_000
SCORE_CAP = 1_000_000
TERMINAL_CAP = 16384
GRADE_SECONDS = 60
THREADS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT',
           'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS', 'NUMEXPR_NUM_THREADS')
COMMAND = ['-I', '-B', '/source/grader.py', '--submission', '/submission/submission.json',
           '--schema', '/source/OUTPUT_SCHEMA.json', '--references', '/source/REFERENCES.json',
           '--output', '/grade/score.json']
TMPFS = {'/tmp': 'rw,noexec,nosuid,nodev,size=16777216,mode=1777'}
ULIMITS = {'cpu': (40, 41), 'nofile': (128, 128), 'core': (0, 0),
           'fsize': (SCORE_CAP, SCORE_CAP)}
PRIVATE = {'/reference/linkages.npz', '/reference/report.json'}
READONLY = {'/source/grader.py', '/source/scorer_core.py', '/source/generated_checks.py',
            '/source/reference_core.py',
            '/source/OUTPUT_SCHEMA.json', '/source/REFERENCES.json', '/source/invocation.json',
            *PRIVATE}


def mounts_for(profile, submission):
    submission = Path(submission).absolute()
    need(profile['candidate_bytes'] == 4000000 and profile['worker_output_bytes'] == TERMINAL_CAP
         and profile['full_score_bytes'] == SCORE_CAP and set(profile['fixed_mounts']) == READONLY,
         'Exact hierarchy grader files and caps')
    mounts = {}
    for destination, item in sorted(profile['fixed_mounts'].items()):
        path = repo(item['path'])
        if destination in PRIVATE:
            need(set(item) == {'path', 'bytes', 'sha256'} and not Path(item['path']).is_absolute()
                 and '..' not in Path(item['path']).parts and path == path.resolve(),
                 'Literal private descriptor; payload remains unopened')
            info = path.lstat()
            need(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                 and type(item['bytes']) is int and 0 < info.st_size == item['bytes']
                 and info.st_mode & 0o004 and type(item['sha256']) is str
                 and re.fullmatch('[a-f0-9]{64}', item['sha256']) is not None,
                 'Readable single-link private extent, no host content read')
        else:
            pinned(item)
        mounts[destination] = str(path)
    ordinary(submission, profile['candidate_bytes'], empty=True)
    mounts['/submission/submission.json'] = str(submission)
    grade = Path(profile['grade_output_dir'])
    need(grade.is_absolute() and grade == submission.parent.parent / 'grade'
         and all(not p.is_symlink() for p in (grade, *grade.parents)) and grade.is_dir(),
         'Exact trusted-only grade output directory')
    mounts['/grade'] = str(grade)
    need(all(not any(char in path for char in (',', '\n', '\r')) for path in mounts.values())
         and sum(len(value) for value in mounts.values()) <= 8192, 'Bounded canonical grader mounts')
    return dict(sorted(mounts.items()))


def verify(info, name, mounts):
    need(set(mounts) == READONLY | {'/submission/submission.json', '/grade'},
         'Exactly ten readonly mounts and one trusted output directory')
    host, config, state = info['HostConfig'], info['Config'], info['State']
    need(info['Name'] == '/' + name and info['Image'] == config['Image'] == IMAGE
         and config['Entrypoint'] == ['python'] and config['Cmd'] == COMMAND
         and config['WorkingDir'] == '/', 'Exact trusted image and fixed grader command')
    need(state['Status'] == 'created' and state['Running'] is False and state['Pid'] == 0
         and state['OOMKilled'] is False, 'Stopped prestart inspection')
    need(host['NetworkMode'] == 'none' and host['ReadonlyRootfs'] is True
         and host['Privileged'] is False and config['User'] == '65534:65534', 'Offline nonroot readonly worker')
    need('OomKillDisable' in host and
         (host['OomKillDisable'] is None or host['OomKillDisable'] is False), 'Present strict null/false OOM setting')
    need(host.get('CapDrop') == ['ALL'] and not host.get('CapAdd')
         and host.get('SecurityOpt') == ['no-new-privileges:true'] and not host.get('Devices')
         and not host.get('DeviceRequests') and not host.get('DeviceCgroupRules')
         and not host.get('PortBindings') and host.get('PidMode') != 'host'
         and host.get('IpcMode') != 'host', 'No privileged devices or namespaces')
    need(set(info.get('NetworkSettings', {}).get('Networks', {})) <= {'none'}
         and host['AutoRemove'] is False and host['RestartPolicy']['Name'] in ('', 'no'), 'Exact lifecycle')
    need(host['Memory'] == host['MemorySwap'] == MEMORY and host['NanoCpus'] == NANO_CPUS
         and host['PidsLimit'] == 32, 'Exact 1 GiB / 1 CPU / 32 PID grader')
    need((host.get('Tmpfs') or {}) == TMPFS, 'Exact 16 MiB scratch inventory')
    need(host['LogConfig'] == {'Type': 'local', 'Config': {'max-size': '64k', 'max-file': '1', 'compress': 'false'}},
         'Unchanged bounded Docker terminal log')
    need(len(host['Ulimits']) == len(ULIMITS) and
         {x['Name']: (x['Soft'], x['Hard']) for x in host['Ulimits']} == ULIMITS, 'Exact grader ulimits')
    pairs = [x.split('=', 1) for x in config['Env']]
    need(len(pairs) == len({x[0] for x in pairs}), 'Unique environment keys')
    environment = dict(pairs)
    need(all(environment.get(key) == '1' for key in THREADS)
         and environment.get('PYTHONDONTWRITEBYTECODE') == '1', 'Exact thread/bytecode policy')
    for label, rows, key in [('daemon', host.get('Mounts', []), 'Target'),
                             ('effective', [x for x in info['Mounts'] if x['Type'] != 'tmpfs'], 'Destination')]:
        need(len(rows) == len(mounts) and len({row[key] for row in rows}) == len(rows)
             and {row[key] for row in rows} == set(mounts), 'Exact unique mount inventory')
        for row in rows:
            expected = mounts[row[key]]; writable = row[key] == '/grade'
            need(row['Type'] == 'bind' and (row['Source'] == expected or
                 expected.startswith('/Users/') and row['Source'] == '/host_mnt' + expected),
                 'Exact canonical source or documented Docker alias')
            if label == 'daemon':
                readonly = row.get('ReadOnly', False)
                need(type(readonly) is bool and readonly is (not writable), 'Only /grade writable')
            else:
                need(row.get('RW') is writable, 'Exact effective write boundary')
    need(len({row['Destination'] for row in info['Mounts']}) == len(info['Mounts'])
         and all(row['Destination'] in TMPFS and row['RW'] is True
                 for row in info['Mounts'] if row['Type'] == 'tmpfs'), 'No extra effective mount')
    return {'status': 'exact_boundary_verified', 'role': 'hierarchy_trusted_grader',
            'readonly_mounts': 10, 'writable_output_mounts': 1}


class SummaryEngine(BaseEngine):
    """Held CLI lifecycle with durable created-ID evidence and dual absence."""
    def run(self, argv, timeout=5, cap=200000):
        return super().run(argv, timeout=timeout, cap=min(cap, 32768))

    def write(self, name, obj, cap=200000):
        limit = 131072 if name.startswith('create-result-') else 65536 if name.startswith('inspect-') else 32768
        return super().write(name, obj, cap=min(cap, limit))

    def journal(self):
        need(len(self.owned) <= 1 and len((json.dumps({'owned': self.owned}, indent=2) + '\n').encode()) <= 32768,
             'Single bounded grader ownership record')
        super().journal()
        self.sync_directory()

    def sync_directory(self):
        descriptor = os.open(self.out, os.O_RDONLY)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)

    def record_create_result(self, name, created):
        """Capture-only recovery subclasses override this method with no I/O."""
        text = created.stdout.decode('ascii')
        valid = (type(created.returncode) is int and created.returncode == 0 and created.stderr == b''
                 and re.fullmatch('[a-f0-9]{64}\\n?', text) is not None)
        created_id = text.rstrip('\n') if valid else None
        path = self.write('create-result-' + name + '.json', {
            'kind': 'container', 'name': name, 'returncode': created.returncode,
            'stdout': text, 'stderr': created.stderr.decode(errors='replace'), 'created_id': created_id}, 131072)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try: os.fsync(descriptor)
        finally: os.close(descriptor)
        self.sync_directory()
        need(valid, 'Successful create returned exactly one immutable ID')
        return created_id

    def create_summary(self, name, mounts):
        need(set(mounts) == READONLY | {'/submission/submission.json', '/grade'}, 'Exact create mount roster')
        argv = ['create', '--pull', 'never', '--name', name, '--network', 'none', '--read-only',
                '--user', '65534:65534', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true',
                '--memory', str(MEMORY), '--memory-swap', str(MEMORY), '--cpus', '1', '--pids-limit', '32',
                '--restart', 'no', '--workdir', '/', '--log-driver', 'local', '--log-opt', 'max-size=64k',
                '--log-opt', 'max-file=1', '--log-opt', 'compress=false']
        for key, (soft, hard) in ULIMITS.items(): argv += ['--ulimit', f'{key}={soft}:{hard}']
        for destination, source in sorted(mounts.items()):
            argv += ['--mount', f'type=bind,src={source},dst={destination}' + ('' if destination == '/grade' else ',readonly')]
        for destination, options in TMPFS.items(): argv += ['--tmpfs', destination + ':' + options]
        for key in THREADS: argv += ['--env', key + '=1']
        argv += ['--env', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', 'python', IMAGE, *COMMAND]
        need(sum(len(value) for value in argv) <= 12288, 'Bounded canonical grader creation metadata')
        self.own('container', name, argv)
        created_id = self.record_create_result(name, self.run(argv))
        inspected = self.inspect('container', name)
        need(inspected['Id'] == created_id, 'Create return and inspected immutable ID agree')
        return inspected, verify(inspected, name, mounts)

    def cleanup(self, kind, name):
        # Full constructor/saved/live identity checks precede removal.
        from panel_recovery import recover
        row = {'kind': kind, 'name': name, 'absence_verified': False,
               'create_extent_unknown': True, 'id_absent': False, 'name_absent': False}
        try:
            need(kind == 'container', 'Only one trusted grader container')
            item = next(item for item in self.owned if item['kind'] == kind and item['name'] == name)
            value = recover(self.out.parent.parent, self.out, item, self, self.budget)
            targets = value['required_absence_targets']
            identifiers = [target for target in targets if re.fullmatch('[a-f0-9]{64}', target)]
            need(len(identifiers) == 1 and set(targets) == {name, identifiers[0]},
                 'Strict recovery retained exact name and immutable ID')
            observed = value['absence_observations']
            return {**row, **value, 'immutable_id': identifiers[0], 'create_extent_unknown': False,
                    'id_absent': observed.get(identifiers[0]) is True,
                    'name_absent': observed.get(name) is True}
        except BaseException as error:
            row['ownership_error'] = repr(error)[:2000]
            return row
