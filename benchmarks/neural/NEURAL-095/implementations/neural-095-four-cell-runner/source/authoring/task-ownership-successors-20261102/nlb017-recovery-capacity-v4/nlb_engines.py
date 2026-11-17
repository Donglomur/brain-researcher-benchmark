"""Existing large-NPZ profile engine with explicit immutable-identity cleanup only."""
from pathlib import Path
import json, re
ROOT=binding.ROOT
load=binding.load
local=binding.local

old = load('authoring/nlb-cosmoothing/program-runner-v1/common.py', 'old_common')
base = load('authoring/shared-large-npz-runner-v1/engine_profile.py', 'old_r_engine')
contract = load('authoring/shared-large-npz-runner-v1/contract_profile.py', 'large_contract')
identity = load('authoring/task-ownership-successors-20261102/shared/recovery-identity-v1/recovery_identity.py', 'identity')
need = old.need


def volume_expected(name):
    kind, captured_name, argv = identity.capture_request(base.ProfileEngine, 'volume', (name,))
    need(kind == 'volume' and captured_name == name, 'Exact captured volume constructor')
    return {'kind': 'volume', 'name': name, 'argv': argv, 'module': contract}


def container_expected(name, role, mounts, profile):
    kind, captured_name, argv = identity.capture_request(base.ProfileEngine, 'create', (name, role, mounts), profile=profile)
    need(kind == 'container' and captured_name == name, 'Exact captured container constructor')
    return {'kind': 'container', 'name': name, 'argv': argv, 'module': contract,
            'role': role, 'mounts': mounts, 'profile': profile}


class ProfileEngine(base.ProfileEngine):
    def __init__(self, end, out, budget, profile):
        super().__init__(end, out, budget, profile)
        self.recovery_expected = {}

    def volume(self, name):
        self.recovery_expected[('volume', name)] = volume_expected(name)
        return super().volume(name)

    def create(self, name, role, mounts):
        self.recovery_expected[('container', name)] = container_expected(name, role, mounts, self.profile)
        return super().create(name, role, mounts)

    def cleanup(self, kind, name):
        rows = [row for row in self.owned if (row['kind'], row['name']) == (kind, name)]
        if len(rows) != 1 or (kind, name) not in self.recovery_expected:
            return {'kind': kind, 'name': name, 'absence_verified': False,
                    'error': 'Exact owned request unavailable; creation remains unresolved'}
        return identity.recover_one(self, self.out, rows[0], self.recovery_expected[(kind, name)])


def recover_unit(attempt, end):
    attempt = Path(attempt).absolute()
    need(attempt.name == 'batch-00' and attempt.is_relative_to(ROOT / 'artifacts-build') and
         all(not p.is_symlink() for p in (attempt, *attempt.parents)), 'Exact NLB unit namespace')
    journal = attempt / 'resource_ownership.json'
    if not journal.exists():
        return []
    rows = identity.read_json(journal, 65536)['owned']
    need(type(rows) is list and 1 <= len(rows) <= 3, 'At most three journaled unit resources')
    prefixes = ('dmfc-prog-volume-', 'dmfc-prog-holder-', 'dmfc-prog-worker-')
    suffix = None
    for index, item in enumerate(rows):
        name = item.get('name')
        need(type(name) is str and re.fullmatch(prefixes[index] + '[a-f0-9]{32}', name) is not None and
             item.get('kind') == ('volume' if index == 0 else 'container') and
             item.get('attempted_before_dispatch') is True, 'Exact ordered owned unit roles')
        value = name[len(prefixes[index]):]
        if suffix is None:
            suffix = value
        need(value == suffix, 'Single fixed unit resource suffix')
    unit = old.load_profile()['unit']
    profile = {'public_destinations': tuple(x['mount_destination'] for x in unit['public_inputs']),
               'output_name': unit['output_filename'], 'max_output_bytes': unit['max_output_bytes']}
    volume = prefixes[0] + suffix
    expected = {volume: volume_expected(volume)}
    if len(rows) > 1:
        mounts = {'/trusted/holder.py': {'type': 'bind', 'source': str(ROOT / 'authoring/shared-large-npz-runner-v1/holder_profile.py'), 'rw': False},
                  '/capture': {'type': 'volume', 'source': volume, 'rw': False}}
        name = prefixes[1] + suffix
        expected[name] = container_expected(name, 'holder', mounts, profile)
    if len(rows) > 2:
        mounts = {'/program/program.py': {'type': 'bind', 'source': str(attempt.parent / 'program.py'), 'rw': False},
                  '/output': {'type': 'volume', 'source': volume, 'rw': True}}
        mounts.update({x['mount_destination']: {'type': 'bind', 'source': str(ROOT / x['path']), 'rw': False}
                       for x in unit['public_inputs']})
        name = prefixes[2] + suffix
        expected[name] = container_expected(name, 'candidate', mounts, profile)
    engine = base.ProfileEngine(end, attempt, old.HostBudget(attempt.parent.parent, 40000000, 4000000), profile)
    return [identity.recover_one(engine, attempt, item, expected[item['name']]) for item in reversed(rows)]
