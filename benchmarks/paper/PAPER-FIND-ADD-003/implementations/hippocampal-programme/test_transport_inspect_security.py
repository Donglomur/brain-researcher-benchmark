"""Generated inspect regressions; no Docker, scientific data, or native run.

The explicit-true acceptance cases fail against the original bare-only guard.
All resource names, paths, pins and records below are invented test values.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest

SOURCE = Path(__file__).resolve().parent / 'transport'
spec = importlib.util.spec_from_file_location(
    'hippocampal_inspect_transport', SOURCE / '__init__.py',
    submodule_search_locations=[str(SOURCE)])
package = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package
spec.loader.exec_module(package)
provider = sys.modules[spec.name + '.provider']
engine = sys.modules[spec.name + '.engine']


def fixture(holder=False, security=None):
    """A complete generated inspect object accepted by the original policy."""
    resources = {'memory_bytes': 268435456, 'cpu_nanos': 2000000000,
                 'pids': 32, 'max_file_bytes': 65536, 'scratch_bytes': 8192}
    request = {'resources': resources, 'image': 'sha256:' + 'a' * 64,
               'command': ['/generated/run', '--fixture']}
    item = {'name': 'generated-container', 'id': 'b' * 64,
            'kind': 'container', 'owner': 'generated-owner'}
    holder_command = ['/generated/holder', '--fixture']
    command = holder_command if holder else request['command']
    mounts = {'/input': ('bind', '/generated/input', False),
              '/output': ('volume', 'generated-output', True)}
    image_env = ['LANG=C']
    env = {'LANG': 'C', 'OPENBLAS_NUM_THREADS': '1', 'OMP_NUM_THREADS': '1',
           'MKL_NUM_THREADS': '1', 'NUMEXPR_NUM_THREADS': '1',
           'PYTHONDONTWRITEBYTECODE': '1'}
    if not holder:
        env.update(HOME='/work', TMPDIR='/work')
    memory = 134217728 if holder else resources['memory_bytes']
    file_size = 256 if holder else resources['max_file_bytes']
    record = {
        'Name': '/' + item['name'], 'Id': item['id'], 'Image': request['image'],
        'Config': {'Image': request['image'], 'User': '65534:65534',
                   'Entrypoint': [command[0]], 'Cmd': command[1:],
                   'WorkingDir': '/' if holder else '/work',
                   'Env': [key + '=' + value for key, value in env.items()],
                   'Labels': {engine.LABEL: item['owner']}},
        'HostConfig': {
            'Memory': memory, 'MemorySwap': memory,
            'NanoCpus': 1000000000 if holder else resources['cpu_nanos'],
            'PidsLimit': 64 if holder else resources['pids'], 'ShmSize': 16777216,
            'NetworkMode': 'none', 'ReadonlyRootfs': True,
            'CgroupnsMode': 'private', 'LogConfig': {'Type': 'none'},
            'IpcMode': 'private', 'PidMode': '', 'Privileged': False,
            'CapAdd': None, 'CapDrop': ['ALL'], 'Devices': [], 'DeviceRequests': [],
            'SecurityOpt': ['no-new-privileges'] if security is None else security,
            'RestartPolicy': {'Name': 'no'}, 'AutoRemove': False, 'Init': False,
            'Tmpfs': ({'/ready': 'rw,nosuid,nodev,noexec,size=4096,mode=0700,uid=65534,gid=65534'}
                      if holder else
                      {'/work': 'rw,nosuid,nodev,noexec,size=8192,mode=0770,uid=65534,gid=65534'}),
            'Ulimits': [{'Name': 'core', 'Soft': 0, 'Hard': 0},
                       {'Name': 'nofile', 'Soft': 128, 'Hard': 128},
                       {'Name': 'fsize', 'Soft': file_size, 'Hard': file_size}]},
        'Mounts': [{'Destination': '/input', 'Type': 'bind',
                    'Source': '/generated/input', 'RW': False},
                   {'Destination': '/output', 'Type': 'volume',
                    'Name': 'generated-output', 'RW': True}]}
    return record, item, holder, mounts, request, holder_command, image_env


class InspectSecurityTests(unittest.TestCase):
    def test_bare_and_explicit_true_for_both_roles(self):
        for holder in (False, True):
            for option in ('no-new-privileges', 'no-new-privileges:true'):
                for unrelated in ([], ['label=disable']):
                    with self.subTest(holder=holder, option=option, unrelated=unrelated):
                        provider.admit_container(*fixture(holder, [option] + unrelated))

    def test_ambiguous_disabled_missing_and_malformed_options_refused(self):
        invalid = [None, [], 'no-new-privileges', ('no-new-privileges',),
                   {'no-new-privileges': True}, ['label=disable'],
                   ['no-new-privileges:false'], ['no-new-privileges:FALSE'],
                   ['no-new-privileges:TRUE'], ['no-new-privileges:1'],
                   ['no-new-privileges= true'], ['no-new-privileges=true'],
                   ['no-new-privileges', 'no-new-privileges'],
                   ['no-new-privileges:true', 'no-new-privileges:true'],
                   ['no-new-privileges', 'no-new-privileges:true'],
                   ['no-new-privileges', 'no-new-privileges:false'],
                   ['no-new-privileges:true', 'no-new-privileges=false'],
                   ['no-new-privileges', None], [True]]
        for holder in (False, True):
            for value in invalid:
                with self.subTest(holder=holder, security=value):
                    args = fixture(holder)
                    args[0]['HostConfig']['SecurityOpt'] = value
                    with self.assertRaises(ValueError):
                        provider.admit_container(*args)

    def test_added_capabilities_remain_forbidden(self):
        for holder in (False, True):
            for caps in (['DAC_OVERRIDE'], ['CAP_DAC_OVERRIDE'], ['SYS_PTRACE'],
                         ['CAP_SYS_PTRACE'], ['ALL'], ['CAP_DAC_OVERRIDE'] * 2):
                with self.subTest(holder=holder, caps=caps):
                    args = fixture(holder, ['no-new-privileges:true'])
                    args[0]['HostConfig']['CapAdd'] = caps
                    with self.assertRaises(ValueError):
                        provider.admit_container(*args)

    def test_host_isolation_and_limits_remain_enforced(self):
        mutations = {'CapDrop': [], 'Privileged': True, 'Devices': ['device'],
                     'DeviceRequests': ['request'], 'Memory': 1, 'MemorySwap': 1,
                     'NanoCpus': 1, 'PidsLimit': 1, 'ShmSize': 1,
                     'NetworkMode': 'host', 'ReadonlyRootfs': False,
                     'CgroupnsMode': 'host', 'IpcMode': 'host', 'PidMode': 'host',
                     'LogConfig': {'Type': 'json-file'},
                     'RestartPolicy': {'Name': 'always'}, 'AutoRemove': True,
                     'Init': True, 'Tmpfs': {}, 'Ulimits': []}
        for holder in (False, True):
            for key, value in mutations.items():
                with self.subTest(holder=holder, field=key):
                    args = fixture(holder, ['no-new-privileges:true'])
                    args[0]['HostConfig'][key] = value
                    with self.assertRaises(ValueError):
                        provider.admit_container(*args)
            args = fixture(holder, ['no-new-privileges:true'])
            args[0]['HostConfig']['Memory'] = float(args[0]['HostConfig']['Memory'])
            with self.assertRaises(ValueError):
                provider.admit_container(*args)

    def test_mount_set_source_target_mode_and_owner_remain_enforced(self):
        for holder in (False, True):
            original = fixture(holder, ['no-new-privileges:true'])
            for field, value in (('Source', '/generated/other'), ('Destination', '/other'),
                                 ('RW', True), ('RW', 0), ('Type', 'volume')):
                with self.subTest(holder=holder, field=field, value=value):
                    args = copy.deepcopy(original)
                    args[0]['Mounts'][0][field] = value
                    if field == 'Type':
                        args[0]['Mounts'][0]['Name'] = 'wrong-volume'
                    with self.assertRaises(ValueError):
                        provider.admit_container(*args)
            for change in ('missing', 'extra', 'duplicate'):
                with self.subTest(holder=holder, change=change):
                    args = copy.deepcopy(original)
                    if change == 'missing':
                        args[0]['Mounts'].pop()
                    else:
                        row = copy.deepcopy(args[0]['Mounts'][0])
                        if change == 'extra':
                            row['Destination'] = '/extra'
                        args[0]['Mounts'].append(row)
                    with self.assertRaises(ValueError):
                        provider.admit_container(*args)
            for field, value in (('User', '0:0'), ('Entrypoint', ['/other']),
                                 ('Cmd', []), ('WorkingDir', '/other'),
                                 ('Env', ['LANG=C']), ('Labels', {})):
                with self.subTest(holder=holder, config=field):
                    args = copy.deepcopy(original)
                    args[0]['Config'][field] = value
                    with self.assertRaises(ValueError):
                        provider.admit_container(*args)
            args = copy.deepcopy(original)
            args[0]['Id'] = 'c' * 64
            with self.assertRaises(ValueError):
                provider.admit_container(*args)

    def test_current_source_manifest_chain(self):
        def pin(raw):
            return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        nested_raw = (SOURCE / 'SOURCE_MANIFEST.json').read_bytes()
        nested = json.loads(nested_raw)
        self.assertEqual(nested['files']['provider.py'],
                         pin((SOURCE / 'provider.py').read_bytes()))
        outer = json.loads((SOURCE.parent / 'EXECUTABLE_SOURCE_MANIFEST.json').read_bytes())
        rows = {row['path']: {'bytes': row['bytes'], 'sha256': row['sha256']}
                for row in outer['files']}
        self.assertEqual(len(rows), len(outer['files']))
        self.assertEqual(rows['transport/provider.py'], nested['files']['provider.py'])
        self.assertEqual(rows['transport/SOURCE_MANIFEST.json'], pin(nested_raw))


if __name__ == '__main__':
    unittest.main()
