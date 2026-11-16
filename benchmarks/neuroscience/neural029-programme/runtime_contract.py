"""Concrete requested/effective Docker boundary for the full NEURAL029 output."""
from pathlib import Path

OUTPUT_BYTES = 100000000
VOLUME_BYTES = 134217728
VOLUME_OPTIONS = 'size=134217728,nr_inodes=32,uid=65534,gid=65534,mode=0700,noexec,nosuid,nodev'
THREADS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT',
           'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS', 'NUMEXPR_NUM_THREADS')
TMPFS = {'/tmp': 'rw,noexec,nosuid,nodev,size=67108864,mode=1777'}


def need(value, text):
    if not value:
        raise ValueError(text)


def command(role):
    return (['-I', '-B', '/trusted/holder.py', 'hold'] if role == 'holder' else
            ['-I', '-B', '/program/candidate.py', '--input', '/input',
             '--output', '/output/submission.json'])


def limits(role, request):
    if role == 'holder':
        return {'memory': 134217728, 'nano_cpus': 250000000, 'pids': 16, 'cpu': 20}
    return {'memory': request['candidate_memory_bytes'],
            'nano_cpus': request['candidate_nano_cpus'], 'pids': 64,
            'cpu': request['candidate_cpu_seconds']}


def canonical(role, mounts):
    names = ({'/trusted/holder.py', '/capture', '/export'} if role == 'holder' else
             {'/program/candidate.py', '/input/public', '/output'})
    need(role in ('holder', 'candidate') and set(mounts) == names, 'Exact role mounts')
    for dest, row in mounts.items():
        need(set(row) == {'type', 'source', 'rw'} and type(row['rw']) is bool and
             type(row['source']) is str and row['source'] and
             not any(c in row['source'] for c in ',\n\r\x00'), 'Canonical mount row')
        need(row['type'] == ('volume' if dest in ('/output', '/capture') else 'bind'),
             'Exact mount kind')
        need(row['rw'] is (dest in ('/output', '/export')), 'Exact mount permission')
        if row['type'] == 'bind':
            need(Path(row['source']).is_absolute() and '..' not in Path(row['source']).parts,
                 'Absolute bind source')


def create_argv(name, role, mounts, request):
    canonical(role, mounts); lim = limits(role, request)
    # No --pid inheritance requests Docker's new private PID namespace;
    # effective PidMode must be exactly empty. IPC is requested explicitly.
    argv = ['create', '--pull', 'never', '--name', name, '--network', 'none', '--ipc', 'private',
            '--read-only', '--user', '65534:65534', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges:true', '--memory', str(lim['memory']),
            '--memory-swap', str(lim['memory']), '--cpus', str(lim['nano_cpus'] / 1e9),
            '--pids-limit', str(lim['pids']), '--restart', 'no', '--log-driver', 'local',
            '--log-opt', 'max-size=64k', '--log-opt', 'max-file=1', '--log-opt',
            'compress=false', '--ulimit', f"cpu={lim['cpu']}:{lim['cpu']+2}",
            '--ulimit', 'nofile=1024:1024', '--ulimit', 'core=0:0', '--ulimit',
            'fsize=100000000:100000000', '--workdir', '/' if role == 'holder' else '/output']
    for dest, row in mounts.items():
        value = f"type={row['type']},src={row['source']},dst={dest}"
        if row['type'] == 'volume':
            value += ',volume-nocopy'
        if not row['rw']:
            value += ',readonly'
        argv += ['--mount', value]
    if role == 'candidate':
        for dest, options in TMPFS.items():
            argv += ['--tmpfs', dest + ':' + options]
    for key in THREADS:
        argv += ['--env', key + '=1']
    return argv + ['--env', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', 'python',
                   request['image'], *command(role)]


def verify(info, name, role, mounts, request):
    canonical(role, mounts); lim = limits(role, request)
    h, c, s = info['HostConfig'], info['Config'], info['State']
    need(info['Name'] == '/' + name and info['Image'] == c['Image'] == request['image']
         and c['Entrypoint'] == ['python'] and c['Cmd'] == command(role),
         'Exact image, role and command')
    need(c['WorkingDir'] == ('/' if role == 'holder' else '/output') and
         s['Status'] == 'created' and s['Running'] is False and s['Pid'] == 0,
         'Inspect created container before start')
    need(h['NetworkMode'] == 'none' and h['ReadonlyRootfs'] is True and
         h['Privileged'] is False and c['User'] == '65534:65534', 'Offline readonly nonroot')
    need(h.get('CapDrop') == ['ALL'] and not h.get('CapAdd') and
         'no-new-privileges:true' in h.get('SecurityOpt', []) and
         not h.get('Devices') and not h.get('DeviceRequests') and not h.get('PortBindings')
         and h.get('PidMode') == '' and h.get('IpcMode') == 'private',
         'Exact private PID/IPC namespaces and no host privileges')
    need(set(info.get('NetworkSettings', {}).get('Networks', {})) <= {'none'} and
         not h['AutoRemove'] and h['RestartPolicy']['Name'] in ('', 'no'), 'Fixed lifecycle')
    need('OomKillDisable' in h and (h['OomKillDisable'] is None or h['OomKillDisable'] is False),
         'Explicit enabled OOM policy')
    need(h['Memory'] == h['MemorySwap'] == lim['memory'] and h['NanoCpus'] == lim['nano_cpus']
         and h['PidsLimit'] == lim['pids'], 'Exact resource requests')
    need((h.get('Tmpfs') or {}) == (TMPFS if role == 'candidate' else {}), 'Exact tmpfs')
    need(h['LogConfig'] == {'Type': 'local', 'Config': {'max-size': '64k', 'max-file': '1',
         'compress': 'false'}}, 'Bounded log driver')
    need(len(h['Ulimits']) == 4 and {x['Name']: (x['Soft'], x['Hard']) for x in h['Ulimits']} ==
         {'cpu': (lim['cpu'], lim['cpu']+2), 'nofile': (1024, 1024), 'core': (0, 0),
          'fsize': (OUTPUT_BYTES, OUTPUT_BYTES)}, 'Full100MB output contract and CPU limits')
    env = [v.split('=', 1) for v in c['Env']]
    need(len(env) == len({p[0] for p in env}), 'Unique environment')
    env = dict(env)
    need(all(env.get(k) == '1' for k in THREADS) and
         env.get('PYTHONDONTWRITEBYTECODE') == '1', 'Thread/bytecode settings')
    for source, rows, key in [('daemon', h.get('Mounts', []), 'Target'),
                              ('effective', [r for r in info['Mounts'] if r['Type'] != 'tmpfs'], 'Destination')]:
        need(len(rows) == len(mounts) and {r[key] for r in rows} == set(mounts),
             'Exact requested and effective mounts')
        for row in rows:
            expected = mounts[row[key]]
            actual = row.get('Name') if source == 'effective' and expected['type'] == 'volume' else row['Source']
            alias = expected['type'] == 'bind' and expected['source'].startswith('/Users/') and actual == '/host_mnt' + expected['source']
            need(row['Type'] == expected['type'] and (actual == expected['source'] or alias),
                 'Exact source or documented Docker Desktop alias')
            need((row.get('ReadOnly', False) is (not expected['rw'])) if source == 'daemon'
                 else row['RW'] is expected['rw'], 'Exact effective mount mode')
            if source == 'daemon' and expected['type'] == 'volume':
                need(row.get('VolumeOptions', {}).get('NoCopy') is True, 'No copyup')
    need(len({r['Destination'] for r in info['Mounts']}) == len(info['Mounts']) and
         all(r['Destination'] in TMPFS and r['RW'] is True and role == 'candidate'
             for r in info['Mounts'] if r['Type'] == 'tmpfs'), 'No extra effective mounts')
    return {'status': 'requested_and_effective_boundary_checked', 'role': role,
            'native_qualification': False}
