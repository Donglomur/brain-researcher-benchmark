"""Focused generated Docker-inspect controls; no Docker, model, or neural data."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
TASK = 'NEURAL-022'
EXPECTED_SOURCE = {'bytes': 4998, 'sha256': '20a7cbb9d39c9398c725d86d2d0a088aa372773846d68cd44e1a16b792055de2'}
EXPECTED_MANIFEST = {'bytes': 987, 'sha256': '77c1f57d98d2db86134612e9edf0cad1b07a45f3396a25b00e17de18323ba835'}
HOLDER_MEMORY = 134217728


def identity(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def load_provider():
    # Authenticate this test's exact implementation, including unchanged imports.
    source_raw = (HERE / 'SOURCE.json').read_bytes()
    if identity(source_raw) != EXPECTED_SOURCE:
        raise AssertionError('Current component source descriptor changed')
    source = json.loads(source_raw)
    raw = (HERE / 'transport/SOURCE_MANIFEST.json').read_bytes()
    if identity(raw) != EXPECTED_MANIFEST:
        raise AssertionError('Current transport descriptor changed')
    manifest = json.loads(raw)
    prefix = 'benchmarks/neural/' + TASK + '/implementations/submitted-program-v1/'
    if source['files'][prefix + 'transport/SOURCE_MANIFEST.json'] != identity(raw):
        raise AssertionError('Outer descriptor does not bind current transport')
    for name, expected in manifest['files'].items():
        actual = identity((HERE / 'transport' / name).read_bytes())
        if actual != expected or source['files'][prefix + 'transport/' + name] != expected:
            raise AssertionError('Direct and transitive transport source mismatch: ' + name)
    name = TASK.lower().replace('-', '_') + '_inspect_portability_transport'
    spec = importlib.util.spec_from_file_location(name, HERE / 'transport/__init__.py',
                                                submodule_search_locations=[str(HERE / 'transport')])
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return sys.modules[name + '.provider']


provider = load_provider()


def fixture(holder):
    # Invented owner, image and operands. Only the observed enabled option spelling
    # is transferred from the motivating real run; no private fixture is embedded.
    item = {'kind': 'container', 'name': 'generated-inspect', 'owner': 'generated-owner', 'id': 'a' * 64}
    request = {'image': 'sha256:' + 'b' * 64, 'command': ['/generated/python', 'candidate.py'],
               'resources': {'memory_bytes': 1073741824, 'cpu_nanos': 1000000000, 'pids': 8,
                             'max_file_bytes': 65536, 'scratch_bytes': 67108864}}
    command = ['/generated/python', 'holder.py'] if holder else request['command']
    env = {key: '2' for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'OMP_THREAD_LIMIT',
                              'MKL_NUM_THREADS', 'NUMBA_NUM_THREADS', 'NUMEXPR_NUM_THREADS')}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if not holder:
        env.update(HOME='/work', TMPDIR='/work')
    memory = HOLDER_MEMORY if holder else 1073741824
    host = {'Memory': memory, 'MemorySwap': memory, 'NanoCpus': 250000000 if holder else 1000000000,
            'PidsLimit': 64 if holder else 8, 'ShmSize': 16777216, 'NetworkMode': 'none',
            'ReadonlyRootfs': True, 'CgroupnsMode': 'private', 'LogConfig': {'Type': 'none'},
            'IpcMode': 'private', 'PidMode': '', 'Privileged': False, 'CapAdd': [], 'CapDrop': ['ALL'],
            'SecurityOpt': ['no-new-privileges:true', 'label=disable'], 'Devices': [], 'DeviceRequests': [],
            'RestartPolicy': {'Name': 'no'}, 'AutoRemove': False, 'Init': False,
            'Tmpfs': {'/ready': 'rw,nosuid,nodev,noexec,size=4096,mode=0700,uid=65534,gid=65534'} if holder
                     else {'/work': 'rw,nosuid,nodev,noexec,size=67108864,mode=0770,uid=65534,gid=65534'},
            'Ulimits': [{'Name': key, 'Soft': value, 'Hard': value} for key, value in
                        {'core': 0, 'nofile': 128, 'fsize': 256 if holder else 65536}.items()]}
    mounts = {'/input/generated.json': ('bind', '/generated/input.json', False)}
    info = {'Name': '/generated-inspect', 'Id': 'a' * 64, 'Image': request['image'], 'HostConfig': host,
            'Mounts': [{'Type': 'bind', 'Source': '/generated/input.json',
                        'Destination': '/input/generated.json', 'RW': False}],
            'Config': {'Labels': {provider.LABEL: 'generated-owner'}, 'Image': request['image'],
                       'User': '65534:65534', 'Entrypoint': [command[0]], 'Cmd': command[1:],
                       'WorkingDir': '/' if holder else '/work', 'Env': [k + '=' + v for k, v in env.items()]}}
    return info, item, holder, mounts, request, command, []


class InspectPortability(unittest.TestCase):
    def test_both_enabled_spellings_in_both_roles(self):
        for holder in (True, False):
            for enabled in ('no-new-privileges', 'no-new-privileges:true'):
                for remaining in ([], ['label=disable']):
                    args = fixture(holder)
                    args[0]['HostConfig']['SecurityOpt'] = [enabled, *remaining]
                    with self.subTest(holder=holder, enabled=enabled, remaining=remaining):
                        provider.admit_container(*args)

    def test_missing_disabled_duplicate_conflicting_and_malformed_options_fail(self):
        invalid = [None, 'no-new-privileges', {'no-new-privileges': True}, [], ['label=disable'],
                   ['no-new-privileges:false'], ['no-new-privileges:yes'], ['no-new-privileges:true:true'],
                   ['no-new-privileges=true'], ['no-new-privileges', 'no-new-privileges:true'],
                   ['no-new-privileges:true', 'no-new-privileges:true'],
                   ['no-new-privileges', 'no-new-privileges'],
                   ['no-new-privileges:true', 'no-new-privileges:false'],
                   ['no-new-privileges', 'no-new-privileges:false'], [1], ['no-new-privileges', None]]
        for holder in (True, False):
            for options in invalid:
                args = fixture(holder)
                args[0]['HostConfig']['SecurityOpt'] = options
                with self.subTest(holder=holder, options=options), self.assertRaises(ValueError):
                    provider.admit_container(*args)

    def test_enabled_canonical_option_does_not_weaken_other_admission(self):
        host_changes = {'CapAdd': ['SYS_PTRACE'], 'CapDrop': [], 'Privileged': True,
                        'NetworkMode': 'bridge', 'CgroupnsMode': 'host', 'IpcMode': 'host',
                        'PidMode': 'host', 'ReadonlyRootfs': False, 'Memory': True,
                        'NanoCpus': 250000001, 'Devices': ['/generated/device'],
                        'DeviceRequests': [{'Count': 1}], 'AutoRemove': True, 'Init': True}
        for holder in (True, False):
            for field, value in host_changes.items():
                args = fixture(holder)
                args[0]['HostConfig'][field] = value
                with self.subTest(holder=holder, field=field), self.assertRaises(ValueError):
                    provider.admit_container(*args)
            for caps in (['CAP_SYS_PTRACE'], ['SYS_PTRACE', 'CAP_SYS_PTRACE']):
                args = fixture(holder)
                args[0]['HostConfig']['CapAdd'] = caps
                with self.subTest(holder=holder, caps=caps), self.assertRaises(ValueError):
                    provider.admit_container(*args)
            for mutation in ('owner', 'image', 'user', 'missing', 'extra', 'source', 'target', 'writable', 'duplicate'):
                args = fixture(holder)
                info = args[0]
                if mutation == 'owner': info['Config']['Labels'][provider.LABEL] = 'other-owner'
                if mutation == 'image': info['Image'] = 'sha256:' + 'c' * 64
                if mutation == 'user': info['Config']['User'] = '0:0'
                if mutation == 'missing': info['Mounts'].clear()
                if mutation == 'extra': info['Mounts'].append({'Type': 'bind', 'Source': '/generated/extra', 'Destination': '/extra', 'RW': False})
                if mutation == 'source': info['Mounts'][0]['Source'] = '/generated/other.json'
                if mutation == 'target': info['Mounts'][0]['Destination'] = '/wrong'
                if mutation == 'writable': info['Mounts'][0]['RW'] = True
                if mutation == 'duplicate': info['Mounts'].append(copy.deepcopy(info['Mounts'][0]))
                with self.subTest(holder=holder, mutation=mutation), self.assertRaises(ValueError):
                    provider.admit_container(*args)


if __name__ == '__main__':
    unittest.main(verbosity=2)
