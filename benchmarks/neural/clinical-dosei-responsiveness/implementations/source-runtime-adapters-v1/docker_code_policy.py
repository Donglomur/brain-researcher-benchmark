"""Exact source policy for the selected existing code image; no Docker calls."""
import hashlib
import json
import math
import os
import re

PROFILE_SHA256 = 'c1830439a06254a982279604d645de5969c3444260e74262f7ad0efc7bc3129b'
IMAGE = 'sha256:385454f413cc6f607bc7e6bfc0246c365fe3a5d6ee8f8a9fdef47196b6141156'
CONTAINER_LABEL = 'org.dosei.generated-source-owner'
ENTRY = '/usr/local/bin/python3'
COMMAND = ['-I', '-B', '/input/program.py']
MAX_OBSERVATION = 2097152
MAX_PROGRAM = 65536


def require(ok, message):
    if not ok:
        raise ValueError(message)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, 'duplicate JSON key')
            value[key] = item
        return value
    def nonfinite(_):
        raise ValueError('nonfinite JSON')
    def finite(value):
        result = float(value)
        require(math.isfinite(result), 'nonfinite JSON')
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite, parse_float=finite)


def profile(raw):
    require(type(raw) is bytes and hashlib.sha256(raw).hexdigest() == PROFILE_SHA256,
            'exact retained runtime source profile required')
    return decode(raw)


def exact_path(value):
    require(type(value) is str and os.path.isabs(value) and
            not any(c in value for c in ('\x00', '\n', '\r', ',')), 'safe exact absolute path required')
    return value


def context(value):
    require(type(value) is str and re.fullmatch('[0-9a-f]{64}', value), 'exact opaque owner identity required')
    return value


def expected_environment(p):
    environment = {}
    for entry in p['selected_image']['Config']['Env']:
        key, value = entry.split('=', 1)
        require(key not in environment, 'unique retained image environment')
        environment[key] = value
    environment.update(p['code_container_policy']['environment_overrides'])
    return sorted(key+'='+value for key, value in environment.items())


def admit_image(p, value):
    require(type(value) is list and len(value) == 1 and type(value[0]) is dict, 'one exact image inspect object')
    observed = value[0]
    for key in ('Id', 'Architecture', 'Os', 'Size'):
        require(type(observed.get(key)) is type(p['selected_image'][key]) and
                observed[key] == p['selected_image'][key], 'selected existing image identity differs')
    require(type(observed.get('Config')) is dict, 'image configuration required')
    for key, wanted in p['selected_image']['Config'].items():
        require(observed['Config'].get(key) == wanted, 'retained image configuration differs')


def specification(p, context_id, ordinal, observation_path, program_path):
    context(context_id)
    require(type(ordinal) is int and 1 <= ordinal <= 128, 'bounded tool-call ordinal required')
    return {'name': f'dosei-code-{context_id[:32]}-{ordinal:03d}',
            'context_id': context_id, 'ordinal': ordinal, 'image': IMAGE,
            'observation_path': exact_path(observation_path), 'program_path': exact_path(program_path),
            'profile_sha256': PROFILE_SHA256}


def create_arguments(p, spec):
    policy = p['code_container_policy']
    arguments = ['create', '--name', spec['name'], '--pull', 'never', '--network', 'none',
                 '--ipc', 'none', '--cgroupns', 'private', '--read-only', '--user', '65534:65534',
                 '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges:true', '--no-healthcheck',
                 '--log-driver', 'none',
                 '--memory', str(policy['memory_bytes']), '--memory-swap', str(policy['memory_swap_total_bytes']),
                 '--cpus', '1', '--pids-limit', str(policy['pids_limit']), '--workdir', '/work',
                 '--entrypoint', ENTRY, '--label', CONTAINER_LABEL+'='+spec['context_id'],
                 '--label', 'org.dosei.call='+str(spec['ordinal'])]
    for key, value in sorted(policy['environment_overrides'].items()):
        arguments += ['--env', key+'='+value]
    for destination, options in sorted(policy['tmpfs'].items()):
        arguments += ['--tmpfs', destination+':'+options]
    for path, destination in ((spec['observation_path'], '/input/observation.json'),
                              (spec['program_path'], '/input/program.py')):
        arguments += ['--mount', f'type=bind,src={path},dst={destination},readonly,bind-propagation=rprivate']
    return arguments + [IMAGE] + COMMAND


def admit_ownership(spec, value, *, required_id):
    require(type(value) is list and len(value) == 1 and type(value[0]) is dict, 'one owned container inspection required')
    observed = value[0]
    require(type(required_id) is str and re.fullmatch('[0-9a-f]{64}', required_id), 'exact daemon container ID required')
    require(observed.get('Id') == required_id and observed.get('Name') == '/'+spec['name'] and
            observed.get('Image') == IMAGE, 'owned immutable container identity differs')
    require(type(observed.get('Config')) is dict and
            observed['Config'].get('Labels') == {CONTAINER_LABEL: spec['context_id'],
                'org.dosei.call': str(spec['ordinal'])}, 'exact owner/call labels required')
    return observed


def admit_container(p, spec, value, *, required_id, running=None):
    observed = admit_ownership(spec, value, required_id=required_id)
    config, host, state = observed.get('Config'), observed.get('HostConfig'), observed.get('State')
    require(type(config) is dict and type(host) is dict and type(state) is dict, 'full effective container inspection required')
    require(config.get('User') == '65534:65534' and config.get('Entrypoint') == [ENTRY] and
            config.get('Cmd') == COMMAND and config.get('WorkingDir') == '/work' and
            sorted(config.get('Env') or []) == expected_environment(p) and not config.get('Volumes') and
            type(config.get('Healthcheck')) is dict and
            config['Healthcheck'].get('Test') == ['NONE'], 'effective candidate command/environment differs')
    require(config.get('Labels') == {CONTAINER_LABEL: spec['context_id'], 'org.dosei.call': str(spec['ordinal'])},
            'exact owner/call labels required')
    policy = p['code_container_policy']
    require(host.get('ReadonlyRootfs') is True and host.get('Privileged') is False and
            host.get('NetworkMode') == 'none' and host.get('IpcMode') == 'none' and
            host.get('CgroupnsMode') == 'private' and host.get('PidMode', '') == '' and
            host.get('Memory') == policy['memory_bytes'] and host.get('MemorySwap') == policy['memory_swap_total_bytes'] and
            host.get('NanoCpus') == policy['nano_cpus'] and host.get('PidsLimit') == policy['pids_limit'] and
            set(host.get('CapDrop') or []) == {'ALL'} and not host.get('CapAdd') and
            set(host.get('SecurityOpt') or []) == {'no-new-privileges:true'}, 'effective isolation/resource profile differs')
    require(not host.get('Devices') and not host.get('DeviceRequests') and not host.get('DeviceCgroupRules') and
            not host.get('VolumesFrom') and not host.get('Links') and not host.get('PortBindings') and
            not host.get('ExtraHosts') and host.get('Tmpfs') == policy['tmpfs'] and
            host.get('LogConfig') == {'Type': 'none', 'Config': {}}, 'unexpected host access or tmpfs policy')
    mounts = observed.get('Mounts')
    require(type(mounts) is list, 'effective mount inventory required')
    expected = {'/input/observation.json': spec['observation_path'], '/input/program.py': spec['program_path']}
    seen = set()
    for mount in mounts:
        require(type(mount) is dict and type(mount.get('Destination')) is str and mount['Destination'] not in seen,
                'unique effective mount destination required')
        destination = mount['Destination']; seen.add(destination)
        if destination in expected:
            require(mount.get('Type') == 'bind' and mount.get('Source') == expected[destination] and
                    mount.get('RW') is False and mount.get('Propagation') == 'rprivate', 'only exact read-only case files may be bound')
        else:
            require(mount.get('Type') == 'tmpfs' and destination in policy['tmpfs'], 'extra mount prohibited')
    require(set(expected).issubset(seen) and seen <= set(expected)|set(policy['tmpfs']), 'complete exact case mount scope')
    require(type(state.get('Running')) is bool and type(state.get('Paused')) is bool and state['Paused'] is False,
            'unambiguous effective container state required')
    if running is not None:
        require(state['Running'] is running, 'effective running state differs')
    return state
