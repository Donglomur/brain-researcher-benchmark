"""ERP exact resource identity recovery with the closed choice unknown-create fix."""
import copy
import json
import re
from types import SimpleNamespace
import uuid
from common import need, regular, strict, save, absence, identity
import choice_profile as profile


def inventory(run):
    result = []
    for label in profile.LABELS:
        folder = run / label; journal = folder / 'resource_ownership.json'
        if not journal.exists(): continue
        rows = strict(regular(journal, 65536))['owned']
        need(type(rows) is list and len(rows) == 1, 'One owned container per started phase')
        for row in rows:
            need(row['kind'] == 'container' and re.fullmatch('neural059-open-' + label + '-[a-f0-9]{32}', row['name']),
                 'Exact task-owned namespace')
            result.append((folder, row))
    need(len({r['name'] for _, r in result}) == len(result), 'Distinct owned resources')
    return result


def normalized(info):
    value = copy.deepcopy(info)
    h = value['HostConfig']
    need('OomKillDisable' in h and (h['OomKillDisable'] is None or h['OomKillDisable'] is False), 'Strict OOM recovery equivalence')
    h['OomKillDisable'] = False
    return value


def recover(run, folder, item, engine, budget):
    label = folder.name; name = item['name']; mounts = profile.mapping(run, label)
    need(item['attempted_before_dispatch'] is True and item['canonical_create_argv'] == profile.create_args(name, label, mounts),
         'Exact durable ownership request before dispatch')
    before = strict(regular(folder / ('precreate-' + name + '.json'), 65536))
    need(absence(before['returncode'], before['stdout'], before['stderr'], 'container', name), 'Exact precreation absence')
    captured = []
    paths = list(folder.glob('inspect-*-' + name + '.json')); need(len(paths) <= 6, 'Bounded observed inspections')
    for path in paths:
        row = strict(regular(path, 220000))
        if row['returncode'] == 0:
            values = strict(row['stdout'])
            need(type(values) is list and len(values) == 1 and type(values[0]) is dict,
                 'One observed resource')
            observed = values[0]
            need(observed.get('Name') == '/' + name and type(observed.get('Id')) is str
                 and re.fullmatch('[a-f0-9]{64}', observed['Id']),
                 'Saved immutable identity belongs to this exact owned name')
            captured.append(observed)
    ids = {row['Id'] for row in captured}
    need(len(ids) <= 1 and all(re.fullmatch('[a-f0-9]{64}', key) for key in ids), 'One immutable observed ID')
    serial = uuid.uuid4().hex; calls = 0; log_write_errors = []
    def call(argv):
        nonlocal calls
        calls += 1; need(calls <= 4, 'At most four exact cleanup calls')
        reply = engine.run(argv, timeout=2, cap=100000)
        value = {'argv': argv, 'returncode': reply.returncode, 'stdout': reply.stdout.decode(errors='replace'),
                 'stderr': reply.stderr.decode(errors='replace')}
        try: save(folder / ('recovery-' + serial + '-' + str(calls) + '.json'), value, budget, 220000)
        except BaseException as error:
            log_write_errors.append({'call': calls, 'error': repr(error)[:500]})
        return value
    def completed(value):
        value.update(evidence_retention_failed=bool(log_write_errors), log_write_errors=log_write_errors)
        return value
    def missing(row, key): return absence(row['returncode'], row['stdout'], row['stderr'], 'container', key)
    first = call(['inspect', '--type', 'container', name])
    if missing(first, name):
        if not ids:
            return completed({'name': name, 'absence_verified': False, 'unresolved_create': True,
                    'basis': 'Journaled create may still resolve; no immutable ID was observed.'})
        checks = [missing(call(['inspect', '--type', 'container', key]), key) for key in sorted(ids)]
        return completed({'name': name, 'absence_verified': all(checks), 'captured_ids_checked': sorted(ids), 'already_absent': True})
    need(first['returncode'] == 0, 'Strict inspect success or absence')
    live = strict(first['stdout']); need(len(live) == 1, 'One live owned resource')
    environment = strict(regular(run / 'image.json', 65536))['environment']
    verifier = SimpleNamespace(verify=lambda info, n, m: profile.verify_exact(info, n, label, m, environment))
    key = identity.verify_live(normalized(live[0]), {'kind': 'container', 'name': name, 'mounts': mounts, 'module': verifier},
                               [normalized(v) for v in captured])
    need(not ids or ids == {key}, 'Live and observed immutable identity agree')
    call(['rm', '--force', key]); by_id = call(['inspect', '--type', 'container', key]); by_name = call(['inspect', '--type', 'container', name])
    return completed({'name': name, 'immutable_id': key, 'absence_verified': missing(by_id, key) and missing(by_name, name),
            'exact_configuration_verified': True})


def recover_all(run, engine, budget):
    results = []
    for folder, item in reversed(inventory(run)):
        try: result = recover(run, folder, item, engine, budget)
        except BaseException as error: result = {'name': item['name'], 'absence_verified': False, 'error': repr(error)[:1000]}
        results.append(result)
    return results
