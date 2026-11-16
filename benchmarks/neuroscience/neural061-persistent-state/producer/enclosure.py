"""Concrete requested/effective Docker boundary; never a qualification certificate."""
from pathlib import Path
import re
from wire import need

THREADS = ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT',
           'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS', 'NUMEXPR_NUM_THREADS')


def validate_request(request):
    need(type(request) is dict and set(request) == {'image', 'memory_bytes', 'nano_cpus',
         'pids', 'cpu_seconds', 'tmp_bytes', 'frame_bytes', 'stderr_bytes', 'wall_seconds',
         'command_seconds', 'command_bytes'}, 'closed prospective native selection')
    need(re.fullmatch('sha256:[0-9a-f]{64}', request['image']), 'local immutable image ID; never pull')
    for key in set(request) - {'image'}:
        need(type(request[key]) is int and request[key] > 0, 'positive finite integer selection')
    need(request['frame_bytes'] <= 2**31 and request['command_bytes'] <= 1048576,
         'finite protocol/control ceilings')
    return request


def canonical_mounts(trusted, method):
    result = {'/trusted': str(trusted), '/participant/method.py': str(method)}
    for source in result.values():
        p = Path(source)
        need(p.is_absolute() and '..' not in p.parts and not any(c in source for c in ',\n\r\x00'),
             'literal absolute owned bind source')
    need(Path(result['/trusted']).parent == Path(result['/participant/method.py']).parent,
         'same fresh owned mount root')
    return result


def command(request):
    return ['-I', '-B', '/trusted/child.py', str(request['frame_bytes'])]


def tmpfs(request):
    return {'/tmp': f"rw,noexec,nosuid,nodev,size={request['tmp_bytes']},mode=1777"}


def create_argv(name, mounts, request):
    validate_request(request)
    need(re.fullmatch('n061-[0-9a-f]{32}', name), 'owned random native name')
    need(set(mounts) == {'/trusted', '/participant/method.py'}, 'exact mounts')
    argv = ['create', '--pull', 'never', '--name', name, '-i', '--network', 'none',
            '--read-only', '--user', '65534:65534', '--cap-drop', 'ALL',
            '--security-opt', 'no-new-privileges:true', '--ipc', 'private', '--cgroupns', 'private',
            '--memory', str(request['memory_bytes']), '--memory-swap', str(request['memory_bytes']),
            '--cpus', f"{request['nano_cpus']//1000000000}.{request['nano_cpus']%1000000000:09d}",
            '--pids-limit', str(request['pids']), '--restart', 'no', '--log-driver', 'local',
            '--log-opt', 'max-size=64k', '--log-opt', 'max-file=1', '--log-opt', 'compress=false',
            '--ulimit', f"cpu={request['cpu_seconds']}:{request['cpu_seconds']}",
            '--ulimit', 'nofile=128:128', '--ulimit', 'core=0:0', '--ulimit',
            f"fsize={request['tmp_bytes']}:{request['tmp_bytes']}", '--workdir', '/tmp']
    for target, source in mounts.items():
        argv += ['--mount', f'type=bind,src={source},dst={target},readonly']
    for target, options in tmpfs(request).items():
        argv += ['--tmpfs', target + ':' + options]
    for key in THREADS:
        argv += ['--env', key + '=1']
    return argv + ['--env', 'PYTHONDONTWRITEBYTECODE=1', '--entrypoint', 'python',
                   request['image'], *command(request)]


def verify(info, name, mounts, request):
    validate_request(request)
    h, c, s = info['HostConfig'], info['Config'], info['State']
    need(info['Name'] == '/' + name and info['Image'] == c['Image'] == request['image'] and
         c['Entrypoint'] == ['python'] and c['Cmd'] == command(request), 'exact source entry/image')
    need(c['WorkingDir'] == '/tmp' and c['User'] == '65534:65534' and
         c['OpenStdin'] is True and c['Tty'] is False and s['Status'] == 'created' and
         s['Running'] is False and s['Pid'] == 0, 'inspect before start; pipe protocol')
    need(h['NetworkMode'] == 'none' and h['ReadonlyRootfs'] is True and
         h['Privileged'] is False and h.get('CapDrop') == ['ALL'] and not h.get('CapAdd') and
         h.get('SecurityOpt') == ['no-new-privileges:true'], 'closed privilege boundary')
    need(h.get('PidMode') == '' and h.get('IpcMode') == 'private' and
         h.get('UTSMode') == '' and h.get('UsernsMode') == '' and
         h.get('CgroupnsMode') == 'private', 'private namespaces, no borrowed container namespace')
    need(not h.get('Devices') and not h.get('DeviceRequests') and not h.get('PortBindings') and
         not h.get('VolumesFrom') and not h.get('Links') and not h.get('Binds'), 'no extra host access')
    need(not h['AutoRemove'] and h['RestartPolicy']['Name'] in ('', 'no') and
         h.get('OomKillDisable') in (False, None), 'owned explicit lifecycle')
    need(h['Memory'] == h['MemorySwap'] == request['memory_bytes'] and
         h['NanoCpus'] == request['nano_cpus'] and h['PidsLimit'] == request['pids'], 'exact resource limits')
    need((h.get('Tmpfs') or {}) == tmpfs(request), 'bounded scratch only')
    need(h['LogConfig'] == {'Type': 'local', 'Config': {'max-size': '64k', 'max-file': '1',
         'compress': 'false'}}, 'bounded daemon logs')
    limits = {'cpu': (request['cpu_seconds'], request['cpu_seconds']), 'nofile': (128, 128),
              'core': (0, 0), 'fsize': (request['tmp_bytes'], request['tmp_bytes'])}
    need(len(h['Ulimits']) == 4 and {x['Name']: (x['Soft'], x['Hard']) for x in h['Ulimits']} == limits,
         'exact per-process limits; no aggregate CPU-time claim')
    env = [value.split('=', 1) for value in c['Env']]
    need(all(len(pair) == 2 for pair in env) and len({pair[0] for pair in env}) == len(env),
         'unique literal environment')
    env = dict(env)
    need(all(env.get(key) == '1' for key in THREADS) and env.get('PYTHONDONTWRITEBYTECODE') == '1',
         'thread and bytecode limits')
    need(set(info.get('NetworkSettings', {}).get('Networks', {})) <= {'none'}, 'effective offline network')
    for rows, target, effective in ((h.get('Mounts', []), 'Target', False),
                                    ([r for r in info['Mounts'] if r['Type'] != 'tmpfs'], 'Destination', True)):
        need(len(rows) == len(mounts) and {r[target] for r in rows} == set(mounts), 'exact mount roster')
        for row in rows:
            source = mounts[row[target]]
            alias = source.startswith('/Users/') and row['Source'] == '/host_mnt' + source
            need(row['Type'] == 'bind' and (row['Source'] == source or alias), 'exact captured mount source')
            need(row['RW'] is False if effective else row.get('ReadOnly') is True, 'read-only captured mount')
    need(len({r['Destination'] for r in info['Mounts']}) == len(info['Mounts']) and
         all(r['Destination'] == '/tmp' and r['RW'] is True for r in info['Mounts'] if r['Type'] == 'tmpfs'),
         'no anonymous or additional mounts')
    return {'effective_boundary_checked': True, 'native_qualification': False}
