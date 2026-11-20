"""Invented Docker metadata only; no engine, candidate or data execution."""
import copy
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'runtime'))


def no_transport(event, args):
    if event in {'subprocess.Popen', 'os.system', 'os.posix_spawn',
                 'socket.connect', 'socket.bind'}:
        raise RuntimeError('inspect source control forbids transport: ' + event)


sys.addaudithook(no_transport)
import docker_owner as owner


def inspection(option, final):
    cid = 'f' * 64
    name = 'abr-invented-inspect'
    mounts = {('/invented/input', '/input', False),
              ('/invented/task', '/task', False),
              ('/invented/program.py', '/candidate/solution.py', False)}
    item = {
        'Id': cid, 'Image': owner.IMAGE, 'Name': '/' + name, 'RestartCount': 0,
        'Config': {'Labels': {owner.LABEL: name}, 'Entrypoint': ['python3'],
                   'Cmd': ['-I', '-B', '/candidate/solution.py'], 'User': '501:20',
                   'WorkingDir': '/work', 'Env': list(owner.THREAD_ENV)},
        'HostConfig': {
            'Memory': owner.MEMORY, 'MemorySwap': owner.MEMORY,
            'NanoCpus': 1000000000, 'PidsLimit': 64, 'NetworkMode': 'none',
            'ReadonlyRootfs': True, 'CapDrop': ['ALL'], 'CapAdd': [],
            'SecurityOpt': [option], 'LogConfig': {'Type': 'none'},
            'Privileged': False, 'IpcMode': 'private',
            'Tmpfs': {'/work': 'rw,nosuid,nodev,size=134217728,mode=1777',
                      '/tmp': 'rw,nosuid,nodev,size=134217728,mode=1777'},
            'Ulimits': [{'Name': 'nofile', 'Soft': 1024, 'Hard': 1024},
                        {'Name': 'fsize', 'Soft': 1048576, 'Hard': 1048576}]},
        'Mounts': [{'Type': 'bind', 'Source': s, 'Destination': d, 'RW': rw}
                   for s, d, rw in sorted(mounts)],
        'State': {'Running': False, 'Paused': False, 'Restarting': False,
                  'OOMKilled': False, 'Error': '',
                  'Status': 'exited' if final else 'created', 'ExitCode': 0}}
    return [item], cid, name, mounts


class InspectPortability(unittest.TestCase):
    def test_enabled_spellings_at_created_and_natural_exit(self):
        for final in (False, True):
            for option in ('no-new-privileges', 'no-new-privileges:true'):
                with self.subTest(final=final, option=option):
                    args = inspection(option, final)
                    self.assertIs(owner.validate_inspection(*args, final=final), args[0][0])

    def test_false_missing_duplicate_and_extra_options_refused(self):
        rejected = (None, [], ['no-new-privileges:false'],
                    ['no-new-privileges:1'], ['no-new-privileges:true:true'],
                    ['no-new-privileges', 'no-new-privileges'],
                    ['no-new-privileges:true', 'no-new-privileges:true'],
                    ['no-new-privileges', 'no-new-privileges:true'],
                    ['no-new-privileges:true', 'no-new-privileges:false'],
                    ['no-new-privileges:true', 'label=disable'],
                    ['no-new-privileges:true', False], 'no-new-privileges:true')
        for final in (False, True):
            for options in rejected:
                args = inspection('no-new-privileges:true', final)
                args[0][0]['HostConfig']['SecurityOpt'] = options
                with self.subTest(final=final, options=options), self.assertRaises(ValueError):
                    owner.validate_inspection(*args, final=final)

    def test_enabled_spelling_does_not_bypass_isolation_or_closure(self):
        mutations = (
            ('capability', lambda x: x['HostConfig'].update(CapAdd=['CAP_SYS_PTRACE'])),
            ('privileged', lambda x: x['HostConfig'].update(Privileged=True)),
            ('network', lambda x: x['HostConfig'].update(NetworkMode='host')),
            ('namespace', lambda x: x['HostConfig'].update(PidMode='host')),
            ('writable_root', lambda x: x['HostConfig'].update(ReadonlyRootfs=False)),
            ('memory', lambda x: x['HostConfig'].update(Memory=owner.MEMORY + 1)),
            ('source', lambda x: x['Mounts'][0].update(Source='/invented/other')),
            ('target', lambda x: x['Mounts'][0].update(Destination='/other')),
            ('writable_bind', lambda x: x['Mounts'][0].update(RW=True)),
            ('extra_bind', lambda x: x['Mounts'].append(copy.deepcopy(x['Mounts'][0]))),
            ('running', lambda x: x['State'].update(Running=True)),
            ('restarting', lambda x: x['State'].update(Restarting=True)),
            ('exit_failure', lambda x: x['State'].update(ExitCode=1)))
        for label, mutate in mutations:
            args = inspection('no-new-privileges:true', True)
            mutate(args[0][0])
            with self.subTest(label=label), self.assertRaises(ValueError):
                owner.validate_inspection(*args, final=True)


if __name__ == '__main__':
    unittest.main(verbosity=2)
