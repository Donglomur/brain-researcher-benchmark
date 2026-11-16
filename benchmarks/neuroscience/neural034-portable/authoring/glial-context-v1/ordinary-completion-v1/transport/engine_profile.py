"""Inherited BaseEngine with recorded immutable IDs and shared exact recovery.

Required captured-source injections: BaseEngine, HostBudget, regular, digest,
snapshot, absence, contract, recovery. No canonical module imports or aliases.
"""
import os
import re


class ProfileEngine(BaseEngine):
    def __init__(self, end, out, budget, profile):
        super().__init__(end, out, budget)
        self.profile = profile
        self.expected = {}
        self.created_ids = {}
        self.verified_ids = {}

    def volume(self, name):
        self.expected[('volume', name)] = {
            'kind': 'volume', 'name': name, 'argv': contract.volume_argv(name)}
        return super().volume(name)

    def create(self, name, role, mounts):
        argv = contract.create_argv(name, role, mounts, self.profile)
        expected = {'kind': 'container', 'name': name, 'argv': argv,
                    'role': role, 'mounts': mounts, 'profile': self.profile}
        self.expected[('container', name)] = expected
        self.own('container', name, argv)  # Original durable intent precedes dispatch.
        proc = self.run(argv, cap=65536)
        contract.require(proc.returncode == 0, 'Container creation')
        text = proc.stdout.decode('ascii', errors='strict')
        contract.require(re.fullmatch('[a-f0-9]{64}\n?', text) is not None and len(proc.stderr) <= 4096,
                         'One complete immutable create-result ID')
        identity = text.rstrip('\n')
        # Persist the independent create result before any name-based inspection.
        path = self.write('created-' + name + '.json', {
            'kind': 'container', 'name': name, 'canonical_create_argv': argv,
            'returncode': proc.returncode, 'stdout': text,
            'stderr': proc.stderr.decode('utf-8', errors='replace'),
            'immutable_id': identity, 'recorded_before_inspect': True}, cap=20000)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        fd = os.open(self.out, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self.created_ids[name] = identity
        info = self.inspect('container', name)
        boundary = contract.verify(info, name, role, mounts, self.profile)
        self.verified_ids[name] = identity
        return info, boundary

    def run(self, argv, *args, **kwargs):
        if len(argv) == 4 and argv[:3] == ['kill', '--signal', 'KILL']:
            name = argv[3]
            identity = self.verified_ids.get(name)
            expected = self.expected.get(('container', name), {})
            contract.require(identity is not None and self.created_ids.get(name) == identity and
                             expected.get('role') == 'candidate', 'Stop requires a profile-verified create ID')
            created = recovery.read_json(self.out / ('created-' + name + '.json'), 20000)
            contract.require(created.get('kind') == 'container' and created.get('name') == name and
                             created.get('immutable_id') == identity and created.get('returncode') == 0 and
                             created.get('recorded_before_inspect') is True and
                             created.get('stdout') in (identity, identity + '\n') and
                             created.get('canonical_create_argv') == expected['argv'],
                             'Stop matches durable immutable create result and original request')
            argv = [*argv[:3], identity]
        return super().run(argv, *args, **kwargs)

    def inspect(self, kind, name):
        info = super().inspect(kind, name)  # Preserves complete bounded saved inspect.
        if kind == 'container':
            contract.require(name in self.created_ids and info.get('Id') == self.created_ids[name],
                             'Named inspection matches immutable Docker create result')
        return info

    def cleanup(self, kind, name):
        rows = [row for row in self.owned if (row['kind'], row['name']) == (kind, name)]
        if len(rows) != 1 or (kind, name) not in self.expected:
            return {'kind': kind, 'name': name, 'absence_verified': False,
                    'error': 'Exact attempted request unavailable; cleanup remains unresolved'}
        return recovery.recover_resource(self, self.out, rows[0], self.expected[(kind, name)])
