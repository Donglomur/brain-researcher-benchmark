#!/usr/bin/env python3
"""Prospective SMC aggregate-resource paired episode.

The task-local transport requires synchronous parent-owned cgroup custody.
Unresolved source-pinned material and deployment bindings prevent execution;
caller runtime metadata cannot choose an image, PID ceiling or qualification.
The owned controller route is separate from this construction/grading module.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import signal
import stat
import sys
import tempfile
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
TASK = HERE.parents[1]
TASK_ID = 'PAPER-SMC-RNN-2024'
ROUTE = 'smc_aggregate_pair_v1'
TASK_SHA = 'e99cf60035a156fdb7a0a3b61b539db387ae53b31f1d4be59da31f18d9346fbd'
PAIR_SHA = 'a88725a6d3b8c7509826d7c9a4034c796a04635e4bce80cb887468e688f976bc'  # Accepted matched 8GiB/six-thread material pair.
POLICY_SHA = 'd15ef4c5410d96e7e6e61e7554d3d99e21cedceb4073b1c8ee641c35b011f328'
BENCHMARK_SHA = 'a9ca90b9a62e706d5522fc8e52be0b6d2ab6fc01fb6b700c9cd00f8fff777fd5'
TRANSPORT = HERE / 'vendor_transport'
TRANSPORT_SHA = '3ead419589d245857fce0f64657bbe7385c29e92c30ce900a9f3439b32f4940f'
CONDITIONS = ('paper_data', 'paper_data_author_code_and_weights')
PROFILES = {'reproduction': {'cpu_seconds': 75000, 'wall_seconds': 86400, 'memory_bytes': 8589934592, 'threads': 6},
            'improvement': {'cpu_seconds': 7200, 'wall_seconds': 10800, 'memory_bytes': 8589934592, 'threads': 6}}
REQUEST_SCHEMA = 'smc_aggregate_phase_request_v1'
RECEIPT_SCHEMA = 'smc_aggregate_phase_receipt_v1'
OWNERSHIP_SCHEMA = 'smc_aggregate_phase_ownership_v1'
JOURNAL_SCHEMA = 'smc_aggregate_transport_journal_v1'
CLOSED_SCHEMA = 'smc_aggregate_closed_pair_v1'
RECOVERY_SCHEMA = 'smc_aggregate_independent_phase_recovery_v1'
ENGINE_MODULE = '_smc_aggregate_transport.engine'
KEYS = {'reproduction': ['causal', 'noncausal'], 'improvement': ['offline']}
COMMAND = ['/usr/local/bin/python', '-I', '-S', '-B', '/runner/worker.py']
PAIR_CAP = 33554432
FILE_CAP = 512 * 1024**2
META_CAP = 1024**2


def need(ok, message):
    if not ok:
        raise ValueError(message)


def encoded(value):
    return (json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + '\n').encode()


def request_bytes(value):
    """Exact retained Provider engine.encoded ABI; other metadata stays pretty."""
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def path(value):
    p = Path(value).absolute()
    need('..' not in p.parts and not any(q.is_symlink() for q in (p, *p.parents)), 'Unlinked absolute paths only')
    return p


def body(value, cap=META_CAP):
    p = path(value)
    fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        need(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and 0 < before.st_size <= cap,
             'Bounded ordinary single-link metadata/source')
        raw = stream.read(cap + 1)
        after = os.fstat(stream.fileno())
        named = p.lstat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    need(len(raw) == before.st_size and all(getattr(before, k) == getattr(after, k) == getattr(named, k) for k in fields), 'Stable complete file')
    return raw


def decode(raw):
    def unique(rows):
        value = {}
        for key, item in rows:
            need(key not in value, 'Duplicate metadata key')
            value[key] = item
        return value
    return json.loads(raw, object_pairs_hook=unique, parse_constant=lambda _: need(False, 'Nonfinite metadata'))


def read(value, expected=None, cap=META_CAP):
    raw = body(value, cap)
    if expected is not None:
        need(pin(raw)['sha256'] == expected, 'Pinned identity changed: ' + str(value))
    return decode(raw)


def publish(value, raw, mode=0o400):
    p = path(value)
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(raw)
        stream.flush()
        if mode == 0o444:
            # These exact public mount files must remain readable under umask077.
            os.fchmod(stream.fileno(), 0o444)
        os.fsync(stream.fileno())
    return pin(raw)


def relative(value):
    need(type(value) is str and str(PurePosixPath(value)) == value and not value.startswith('/')
         and all(x not in ('', '.', '..') for x in value.split('/')), 'Canonical relative member')
    return value


def descriptor(row, allow_empty=False):
    need(type(row) is dict and set(row) == {'bytes', 'sha256'} and type(row['bytes']) is int
         and (0 if allow_empty else 1) <= row['bytes'] and type(row['sha256']) is str
         and re.fullmatch('[a-f0-9]{64}', row['sha256']), 'Exact positive file descriptor')
    return row


def checked(row, cap=META_CAP):
    need(type(row) is dict and set(row) == {'path', 'bytes', 'sha256'}, 'Exact external file descriptor')
    raw = body(row['path'], cap)
    need(pin(raw) == descriptor({k: row[k] for k in ('bytes', 'sha256')}), 'External descriptor changed')
    return raw


def load_file(name, source, expected, package=False):
    raw = body(source)
    need(pin(raw)['sha256'] == expected, 'Operator source pin changed')
    spec = importlib.util.spec_from_file_location(name, source,
            submodule_search_locations=[str(Path(source).parent)] if package else None)
    module = importlib.util.module_from_spec(spec)
    need(name not in sys.modules, 'Fresh fixed operator module namespace')
    sys.modules[name] = module
    try:
        exec(compile(raw, str(source), 'exec'), module.__dict__)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


_BENCHMARK = None
_PROVIDER = None


def benchmark():
    global _BENCHMARK
    if _BENCHMARK is None:
        _BENCHMARK = load_file('_smc_episode_continuous', HERE.parent / 'continuous-outcomes-v2/benchmark.py', BENCHMARK_SHA)
    return _BENCHMARK


def source_identity():
    manifest = read(HERE / 'SOURCE.json')
    need(manifest['schema'] == 'smc_aggregate_episode_source_v1' and manifest['route'] == ROUTE, 'Exact task-local source descriptor')
    for name, expected in manifest['files'].items():
        relative(name)
        need('/' not in name and pin(body(HERE / name)) == descriptor(expected), 'Current complete local source closure')
    need(set(manifest['files']) == {'episode.py', 'worker.py', 'MATERIAL_BINDING.json', 'DEPLOYMENT_BINDING.json'},
         'Closed executable and selection-file closure')
    need(manifest['continuous_benchmark_sha256'] == BENCHMARK_SHA and manifest['transport_manifest_sha256'] == TRANSPORT_SHA,
         'Exact operator dependency closure')
    return pin(body(HERE / 'SOURCE.json'))


def implementation_identity():
    """Acyclic operational identity: qualification never self-pins selections."""
    source_identity()
    manifest = read(TRANSPORT / 'SOURCE_MANIFEST.json', TRANSPORT_SHA)
    for name, expected in manifest['files'].items():
        need('/' not in relative(name) and pin(body(TRANSPORT / name)) == descriptor(expected),
             'Complete transport implementation before qualification')
    return pin(request_bytes({'schema': 'smc_aggregate_implementation_identity_v1',
        'episode.py': pin(body(HERE / 'episode.py')), 'worker.py': pin(body(HERE / 'worker.py')),
        'transport_manifest': pin(body(TRANSPORT / 'SOURCE_MANIFEST.json'))}))


def material_binding():
    source_identity()
    binding = read(HERE / 'MATERIAL_BINDING.json')
    need(set(binding) == {'schema', 'state', 'accepted_task_sha256', 'predecessor_pair_sha256', 'new_pair', 'missing'}
         and binding['schema'] == 'smc_aggregate_material_binding_v1'
         and binding['accepted_task_sha256'] == TASK_SHA, 'Exact source-selected material binding')
    need(binding['state'] == 'selected' and binding['missing'] == [] and PAIR_SHA is not None,
         'unresolved_material_binding: new 8GiB/six-thread matched packet export is not selected')
    need(descriptor(binding['new_pair'])['sha256'] == PAIR_SHA, 'Selected new pair has exact source identity')
    return binding


def deployment_binding():
    source_identity()
    binding = read(HERE / 'DEPLOYMENT_BINDING.json')
    need(set(binding) == {'schema', 'state', 'selected', 'missing'}
         and binding['schema'] == 'smc_aggregate_deployment_binding_v1', 'Exact source-selected deployment binding')
    need(binding['state'] == 'selected' and binding['missing'] == [],
         'unresolved_deployment_binding: scientific image, same-host delegated cgroup and PID qualification are not selected')
    selected = binding['selected']
    need(type(selected) is dict and set(selected) == {'image', 'docker_binary', 'docker_socket',
         'boot_id', 'delegation', 'pid_limit', 'qualification', 'resource_policy', 'cgroup_driver'}, 'Closed selected deployment shape')
    need(selected['resource_policy'] == 'measured_caps_and_oom_kill_v1', 'Exact measured-cap and OOM-kill policy')
    need(selected['cgroup_driver'] == 'cgroupfs', 'Exact same-host cgroupfs driver; systemd paths are not interchangeable')
    need(type(selected['image']) is str and re.fullmatch('sha256:[a-f0-9]{64}', selected['image']), 'Pinned immutable scientific image')
    need(type(selected['pid_limit']) is int and selected['pid_limit'] > 0, 'Explicit selected PID ceiling; never a default')
    need(type(selected['boot_id']) is str and re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', selected['boot_id']),
         'Selected same-boot Linux deployment')
    for key in ('docker_binary', 'docker_socket'):
        path(selected[key])
    delegation = selected['delegation']
    need(type(delegation) is dict and set(delegation) == {'path', 'st_dev', 'st_ino', 'uid',
         'mount_id', 'mount_point', 'mount_root', 'fs_type'}, 'Exact selected delegated-root identity')
    for key in ('st_dev', 'st_ino', 'uid', 'mount_id'):
        need(type(delegation[key]) is int and delegation[key] >= 0, 'Typed delegated-root identity')
    need(delegation['fs_type'] == 'cgroup2' and delegation['mount_root'] == '/',
         'Same-host complete cgroup2 hierarchy, not a hidden cgroup namespace')
    need(path(delegation['path']).is_relative_to(path(delegation['mount_point']))
         and path(delegation['path']) != path(delegation['mount_point']), 'Dedicated delegated root below selected mount')
    need(type(selected['qualification']) is dict and set(selected['qualification']) == {'path', 'bytes', 'sha256'},
         'Qualification is source-selected, not caller booleans')
    descriptor({k: selected['qualification'][k] for k in ('bytes', 'sha256')})
    path(selected['qualification']['path'])
    return {**selected, 'binding_pin': pin(body(HERE / 'DEPLOYMENT_BINDING.json'))}


def provider_class():
    global _PROVIDER
    if _PROVIDER is None:
        manifest = read(TRANSPORT / 'SOURCE_MANIFEST.json', TRANSPORT_SHA)
        need(manifest['schema'] == 'smc_aggregate_transport_source_manifest_v1' and set(manifest['files']) ==
             {'__init__.py', 'engine.py', 'bounds.py', 'contract.py', 'archive.py', 'holder.py', 'provider.py'}, 'Closed retained transport')
        for name, expected in manifest['files'].items():
            need(pin(body(TRANSPORT / name)) == expected, 'Retained transport changed')
        load_file('_smc_aggregate_transport', TRANSPORT / '__init__.py', manifest['files']['__init__.py']['sha256'], True)
        from _smc_aggregate_transport.provider import Provider
        _PROVIDER = Provider
    return _PROVIDER


def public_context(pair_path, task_path):
    """Read already authenticated current manifests only; no array/model reads."""
    material_binding()  # Refuse unresolved selection before opening caller paths.
    pair_path, task_path = path(pair_path), path(task_path)
    need(pair_path.name == 'pair_manifest.json', 'Canonical pair manifest')
    task = read(task_path, TASK_SHA)
    need(task.get('id', task.get('task_id')) == TASK_ID, 'Current task identity')
    pair = read(pair_path, PAIR_SHA)
    need(pair['schema'] == 'smc_continuous_pair_v2' and pair['current_task_sha256'] == TASK_SHA
         and pair['policy_sha256'] == POLICY_SHA and pair['conditions'] == list(CONDITIONS)
         and pair['resource_budget'] == PROFILES, 'Exact new material version and matched aggregate budgets')
    manifests = {}
    for condition in CONDITIONS:
        manifest = read(pair_path.parent / condition / 'delivery_manifest.json', pair['condition_manifest_sha256'][condition])
        need(manifest['condition'] == condition and manifest['current_task_sha256'] == TASK_SHA
             and manifest['policy_sha256'] == POLICY_SHA, 'Exact condition manifest')
        rows = {}
        for row in manifest['files']:
            name = relative(row['path'])
            need(name not in rows, 'No duplicate material member')
            rows[name] = descriptor({k: row[k] for k in ('bytes', 'sha256')}, allow_empty=True)
        need('delivery_manifest.json' not in rows, 'Manifest is separately bound')
        rows['delivery_manifest.json'] = pin(body(pair_path.parent / condition / 'delivery_manifest.json'))
        manifests[condition] = rows
    need(1 + sum(len(x) for x in manifests.values()) == 71, 'Exact complete 71-file packet')
    return pair, manifests


def runtime_config(value):
    deployment = deployment_binding()  # Never admit caller-selected runtime claims.
    keys = {'schema', 'image', 'docker_binary', 'docker_socket', 'qualification', 'source_read_bytes', 'host_write_bytes'}
    need(type(value) is dict and set(value) == keys and value['schema'] == 'smc_aggregate_runtime_v1', 'Explicit operator runtime configuration')
    need(type(value['image']) is str and re.fullmatch('sha256:[a-f0-9]{64}', value['image']), 'Existing immutable image only')
    for key in ('source_read_bytes', 'host_write_bytes'):
        need(type(value[key]) is int and value[key] > 0, 'Finite externally allocated whole-pair I/O')
    need(all(value[k] == deployment[k] for k in ('image', 'docker_binary', 'docker_socket', 'qualification')),
         'Runtime must equal source-selected deployment; no caller qualification override')
    checked(value['qualification'])
    return {**value, 'deployment': deployment}


def instantiate(pair_path, task_path, outcome, programs, declarations, runtime_path, runtime_sha, output):
    need(outcome in KEYS and set(programs) == set(declarations) == set(CONDITIONS), 'Both full conditions and one outcome')
    pair, _ = public_context(pair_path, task_path)
    runtime_raw = body(runtime_path)
    need(pin(runtime_raw)['sha256'] == runtime_sha, 'Operator-selected runtime configuration')
    runtime = runtime_config(decode(runtime_raw))
    captured = {}
    for condition in CONDITIONS:
        code = body(programs[condition], 1024**2)
        declaration_raw = body(declarations[condition])
        declaration = benchmark().validate_declaration(decode(declaration_raw), outcome, condition)
        need(all(row['source_sha256'] == pin(code)['sha256'] for row in declaration['methods'].values()), 'Declared methods bind the submitted programme')
        captured[condition] = (code, declaration_raw)
    root = path(output)
    need(not root.exists() and root.parent.is_dir() and not root.is_relative_to(path(pair_path).parent), 'Fresh operator protocol outside materials')
    root.mkdir(mode=0o700)
    records = {}
    for condition in CONDITIONS:
        folder = root / condition
        folder.mkdir(mode=0o700)
        code, declaration_raw = captured[condition]
        records[condition] = {'program': publish(folder / 'program.py', code, 0o444),
                              'declaration': publish(folder / 'declaration.json', declaration_raw, 0o444)}
    runtime_pin = publish(root / 'runtime.json', runtime_raw)
    protocol = {'schema': 'smc_aggregate_pair_protocol_v1', 'route': ROUTE, 'task_id': TASK_ID,
        'pair_path': str(path(pair_path)), 'pair_sha256': PAIR_SHA, 'task_path': str(path(task_path)),
        'current_task_sha256': TASK_SHA, 'outcome': outcome, 'source': source_identity(),
        'resource_profile': PROFILES[outcome], 'programs': records, 'runtime': runtime_pin,
        'all_programmes_and_declarations_frozen_before_first_phase': True,
        'material_binding_pin': pin(body(HERE / 'MATERIAL_BINDING.json')),
        'deployment_binding_pin': runtime['deployment']['binding_pin'],
        'restrictions': {'max_kernel_tasks': runtime['deployment']['pid_limit'],
                         'cpu_rate_nanos': 6000000000, 'generic_primary_profile_equivalence': False,
                         'aggregate_cpu_rule': 'parent_meter_stop_and_final_admission_not_zero_overshoot',
                         'host_candidate_execution': False},
        'scientific_success': None, 'execution_authorized_by_construction': False}
    publish(root / 'PROTOCOL.json', encoded(protocol))
    return protocol


def admit_protocol(protocol_path, expected):
    material_binding()
    deployment_binding()
    protocol_path = path(protocol_path)
    protocol = read(protocol_path, expected)
    need(protocol['schema'] == 'smc_aggregate_pair_protocol_v1' and protocol['route'] == ROUTE
         and protocol['task_id'] == TASK_ID and protocol['source'] == source_identity(), 'Current frozen route')
    need(protocol['pair_sha256'] == PAIR_SHA and protocol['current_task_sha256'] == TASK_SHA
         and protocol['outcome'] in KEYS and protocol['resource_profile'] == PROFILES[protocol['outcome']], 'Immutable scope and budgets')
    need(protocol['all_programmes_and_declarations_frozen_before_first_phase'] is True
         and set(protocol['programs']) == set(CONDITIONS), 'Both frozen programmes required')
    public_context(protocol['pair_path'], protocol['task_path'])
    for condition, row in protocol['programs'].items():
        need(set(row) == {'program', 'declaration'}, 'Only source and method declaration')
        for key, filename in (('program', 'program.py'), ('declaration', 'declaration.json')):
            need(pin(body(protocol_path.parent / condition / filename)) == row[key], 'Frozen programme/declaration changed')
        declaration = benchmark().validate_declaration(read(protocol_path.parent / condition / 'declaration.json'), protocol['outcome'], condition)
        need(all(x['source_sha256'] == row['program']['sha256'] for x in declaration['methods'].values()), 'Declared programme source changed')
    need(pin(body(protocol_path.parent / 'runtime.json')) == protocol['runtime'], 'Frozen runtime configuration')
    runtime = runtime_config(read(protocol_path.parent / 'runtime.json'))
    need(protocol['material_binding_pin'] == pin(body(HERE / 'MATERIAL_BINDING.json'))
         and protocol['deployment_binding_pin'] == runtime['deployment']['binding_pin'],
         'Frozen source-selected material and deployment bindings')
    need(protocol['restrictions'] == {'max_kernel_tasks': runtime['deployment']['pid_limit'],
         'cpu_rate_nanos': 6000000000, 'generic_primary_profile_equivalence': False,
         'aggregate_cpu_rule': 'parent_meter_stop_and_final_admission_not_zero_overshoot',
         'host_candidate_execution': False}, 'Exact whole-tree resource restriction')
    return protocol, runtime


def qualify(runtime, source):
    deployment = deployment_binding()
    need(runtime['deployment'] == deployment and source == source_identity(),
         'Exact selected deployment and complete source before qualification')
    need(sys.platform == 'linux' and hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'),
         'Existing provider requires a qualified Linux/pidfd operator; native macOS is unsupported')
    record = decode(checked(runtime['qualification']))
    expected = {'schema', 'route', 'implementation', 'image', 'image_inventory_sha256', 'profiles',
                'boot_id', 'delegation', 'pid_limit', 'resource_policy', 'cgroup_driver', 'evidence'}
    need(set(record) == expected and record['schema'] == 'smc_aggregate_runtime_qualification_v1'
         and record['route'] == ROUTE and record['implementation'] == implementation_identity()
         and record['image'] == runtime['image'] and record['profiles'] == PROFILES
         and all(record[key] == deployment[key] for key in ('boot_id', 'delegation', 'pid_limit', 'resource_policy', 'cgroup_driver')),
         'Source-selected qualification binds operational bytes and exact deployment; no caller flags')
    need(type(record['image_inventory_sha256']) is str and re.fullmatch('[a-f0-9]{64}', record['image_inventory_sha256']),
         'Reviewed generic scientific image inventory')
    evidence = record['evidence']
    need(type(evidence) is dict and set(evidence) == {'image_inventory', 'scientific_packages',
         'six_thread_probe', 'aggregate_cpu_probe', 'containment_probe', 'closure_probe'},
         'Complete source-selected external qualification evidence set')
    # These immutable metadata receipts are selected by the reviewed source binding.
    # Their independent acceptance is not recreated by booleans in caller runtime.json.
    for row in evidence.values():
        decode(checked(row))
    need(evidence['image_inventory']['sha256'] == record['image_inventory_sha256'], 'Exact inventory receipt join')
    return record


def file_mount(source, expected, purpose='input'):
    return {'path': str(path(source)), 'kind': 'file', 'purpose': purpose,
            'files': {Path(source).name: descriptor(expected, allow_empty=True)}}


def mount_identity(mounts):
    return {target: {'kind': value['kind'], 'purpose': value['purpose'], 'files': value['files']}
            for target, value in sorted(mounts.items())}


def resources(outcome, runtime):
    p = PROFILES[outcome]
    deployment = deployment_binding()
    need(runtime['deployment'] == deployment, 'Only source-selected PID and deployment limits')
    return {'setup_seconds': 60, 'producer_seconds': p['wall_seconds'], 'capture_seconds': 300,
        'cleanup_seconds': 60, 'memory_bytes': p['memory_bytes'], 'cpu_nanos': 6000000000,
        'cpu_seconds': p['cpu_seconds'], 'pids': deployment['pid_limit'],
        'scratch_bytes': 512 * 1024**2, 'max_files': 4, 'max_directories': 1,
        'max_file_bytes': FILE_CAP, 'max_output_bytes': 2 * FILE_CAP + 4096,
        'manifest_bytes': 65536, 'max_cli_calls': 256, 'max_cli_bytes': 8 * 1024**2,
        'inventory_bytes': 65536, 'source_read_bytes': runtime['source_read_bytes'] // 2,
        'host_write_bytes': runtime['host_write_bytes'] // 2}


def aggregate_plan(invocation, invocation_pin, condition, runtime):
    need(condition in CONDITIONS, 'Exact paired access condition')
    descriptor(invocation_pin)
    deployment = deployment_binding()
    need(runtime['deployment'] == deployment and invocation['deployment_pin'] == deployment['binding_pin'],
         'Invocation retains exact source-selected delegation')
    nonce = invocation['aggregate_nonce']
    need(type(nonce) is str and re.fullmatch('[a-f0-9]{32}', nonce), 'Fresh bound aggregate nonce')
    name = 'smc-' + nonce + ('-a' if condition == CONDITIONS[0] else '-b')
    parent = str(path(deployment['delegation']['path']))
    scope_path = Path(parent) / name
    daemon_parent = '/' + str(scope_path.relative_to(path(deployment['delegation']['mount_point'])))
    return {'schema': 'smc_cgroup_plan_v1', 'phase_id': condition, 'name': name,
            'parent': parent, 'path': str(scope_path), 'cgroup_parent': daemon_parent,
            'deployment_pin': deployment['binding_pin'], 'invocation_pin': invocation_pin}


def mounts_for(protocol_path, protocol, condition, job_path, job_pin, manifests):
    root = Path(protocol['pair_path']).parent / condition
    result = {}
    for name, expected in manifests[condition].items():
        purpose = 'historical_author_source' if name.startswith('official_source/') or name in ('official_source_manifest.json', 'official_asset_manifest.json') else 'input'
        if name == 'paper.pdf':
            purpose = 'paper'
        result['/materials/' + name] = file_mount(root / name, expected, purpose)
    folder = Path(protocol_path).parent / condition
    result['/program/program.py'] = file_mount(folder / 'program.py', protocol['programs'][condition]['program'], 'program')
    result['/declaration.json'] = file_mount(folder / 'declaration.json', protocol['programs'][condition]['declaration'], 'contract')
    result['/execution.json'] = file_mount(job_path, job_pin, 'contract')
    result['/runner/worker.py'] = file_mount(HERE / 'worker.py', pin(body(HERE / 'worker.py')), 'program')
    return result


def job_for(protocol, condition):
    programme = protocol['programs'][condition]
    return {'schema': 'smc_aggregate_execution_job_v1', 'outcome': protocol['outcome'], 'condition': condition,
            'source': protocol['source'],
            'resource_profile': protocol['resource_profile'], 'submission_keys': KEYS[protocol['outcome']],
            'program_sha256': programme['program']['sha256'], 'declaration_sha256': programme['declaration']['sha256'],
            'max_file_bytes': FILE_CAP}


def validate_closed(request, receipt):
    need(request['schema'] == REQUEST_SCHEMA and receipt['schema'] == RECEIPT_SCHEMA
         and receipt['status'] == 'captured' and receipt['producer_closed_before_capture'] is True
         and receipt['all_native_resources_closed'] is True and receipt['cli_reaped'] is True,
         'Producer and every owned native resource must close before grading')
    need(receipt['request_sha256'] == pin(request_bytes(request))['sha256'] and receipt['phase_id'] == request['phase_id']
         and receipt['source'] == request['source'] and receipt['image'] == request['image']
         and receipt['role'] == request['role'] and receipt['enforced_resource_limits'] == request['resources']
         and receipt['aggregate'] == request['aggregate']
         and receipt['aggregate_final_acknowledged'] is True
         and receipt['aggregate_custody_owner'] == 'parent'
         and receipt['resource_custody_scope'] == 'docker_volume_holder_producer_only',
         'Closed receipt binds exact phase/profile; parent aggregate proof remains separately required')
    return receipt


def observe_closed(provider, request, result, deadline):
    observed = provider.observe(request['phase_id'], pin(request_bytes(request))['sha256'], result['receipt_pin'], deadline)
    receipt = observed['receipt']
    need(observed['receipt_pin'] == result['receipt_pin'] and receipt == result['receipt'], 'Independent saved receipt observation')
    return validate_closed(request, receipt)


def captured_predictions(receipt, condition, outcome, programme):
    inventory = receipt['output_inventory']
    expected = {k + '.h5' for k in KEYS[outcome]} | {'RESULT.json', 'OUTPUTS.json'}
    need(inventory['complete'] is True and set(inventory['files']) == expected, 'Complete original predictions and envelope only')
    root = path(receipt['quarantine_root'])
    result = read(root / 'RESULT.json', inventory['files']['RESULT.json']['sha256'])
    need(result == {'schema': 'smc_aggregate_program_result_v1', 'outcome': outcome, 'condition': condition,
                   'program_sha256': programme['program']['sha256'], 'declaration_sha256': programme['declaration']['sha256'],
                   'submission_keys': KEYS[outcome]}, 'Captured result binds frozen programme/method declaration')
    predictions = {key: root / (key + '.h5') for key in KEYS[outcome]}
    for key, filename in predictions.items():
        expected_pin = inventory['files'][key + '.h5']
        need(filename.lstat().st_size == expected_pin['bytes']
             and benchmark().hash_file(filename, FILE_CAP) == expected_pin['sha256'],
             'Captured prediction changed before immutable freeze')
    return predictions


def execute(protocol_path, expected, output):
    raise RuntimeError('unsupported_direct_execute: use the separately bound aggregate owner with its original clock')


def grade(closed_path, closed_sha, target, evaluator, output, scratch_bytes):
    raise RuntimeError('aggregate_owner_grade_required: parent closure, counters and removal proof precede target access')


def _grade_from_owned_pair(closed_path, closed_sha, target, evaluator, output, scratch_bytes):
    """Private helper called by the source-bound owner only after all its proofs."""
    closed = read(closed_path, closed_sha)
    need(closed['schema'] == CLOSED_SCHEMA and closed['route'] == ROUTE
         and closed['both_conditions_closed_before_private_grade'] is True
         and closed['private_target_accessed'] is False and set(closed['conditions']) == set(CONDITIONS), 'Both protected conditions required before first target read')
    protocol, runtime = admit_protocol(closed['protocol_path'], closed['protocol_sha256'])
    need(closed['source'] == protocol['source'] and closed['outcome'] == protocol['outcome'], 'Closed pair scope')
    need(closed['runtime_qualification'] == runtime['qualification'], 'Same externally admitted runtime qualification')
    _, manifests = public_context(protocol['pair_path'], protocol['task_path'])
    root = path(closed_path).parent
    final = path(output)
    need(not final.exists() and final.parent.is_dir() and not final.is_relative_to(Path(protocol['pair_path']).parent)
         and not final.is_relative_to(Path(closed['protocol_path']).parent), 'Private final report outside public materials')
    # Authenticate both receipts and all frozen predictions before any scoring.
    for condition in CONDITIONS:
        row = closed['conditions'][condition]
        need(path(row['receipt_path']) == root / 'control' / condition / 'RECEIPT.json'
             and path(row['freeze_path']) == root / 'freezes' / (condition + '.json'), 'Only owned protected outputs may enter scoring')
        receipt = read(row['receipt_path'], row['receipt']['sha256'])
        need(pin(body(row['receipt_path'])) == row['receipt'], 'Closed exact observed receipt')
        request_path = root / 'jobs' / condition / 'REQUEST.json'
        request = read(request_path, row['request']['sha256'])
        need(request['schema'] == REQUEST_SCHEMA
             and pin(body(request_path)) == row['request'] == pin(request_bytes(request)) and request['phase_id'] == condition
             and request['role'] == ('A' if condition == CONDITIONS[0] else 'B')
             and request['image'] == runtime['image'] and request['source'] == protocol['source']
             and request['command'] == COMMAND and request['workdir'] == '/work'
             and request['action'] == 'held_attempt' and request['resources'] == resources(protocol['outcome'], runtime)
             and request['output'] == {'kind': 'generic', 'manifest': 'OUTPUTS.json'}, 'Current exact executed request/profile')
        need(request['aggregate']['phase_id'] == condition
             and request['aggregate']['deployment_pin'] == runtime['deployment']['binding_pin']
             and request['aggregate']['invocation_pin'] == closed['owner_invocation_pin'],
             'Aggregate request joins exact owner invocation and selected deployment')
        validate_closed(request, receipt)
        need(path(receipt['quarantine_root']) == root / 'quarantine' / condition, 'Owned immutable quarantine only')
        job_path = root / 'jobs' / condition / 'EXECUTION.json'
        need(read(job_path) == job_for(protocol, condition), 'Exact executed job binds outcome, programme and CPU profile')
        mounts = mounts_for(closed['protocol_path'], protocol, condition, job_path, pin(body(job_path)), manifests)
        identity = mount_identity(mounts)
        exposure = read(root / 'jobs' / condition / 'EXPOSURE.json', request['exposure']['sha256'])
        need(pin(body(root / 'jobs' / condition / 'EXPOSURE.json')) == request['exposure']
             and exposure['mounts'] == identity and exposure['source'] == protocol['source']
             and exposure['image'] == runtime['image'] and exposure['role'] == request['role']
             and exposure['command'] == COMMAND
             and exposure['boundary_audit'] == {k: runtime['qualification'][k] for k in ('bytes', 'sha256')},
             'Current exact exposure and qualification join')
        need(receipt['exposure'] == request['exposure'] and receipt['input_before'] == identity
             and receipt['input_after'] == identity, 'Exact condition files remained unchanged through capture')
        predictions = captured_predictions(receipt, condition, protocol['outcome'], protocol['programs'][condition])
        frozen = read(row['freeze_path'], row['freeze']['sha256'])
        need(pin(body(row['freeze_path'])) == row['freeze'] and frozen['condition'] == condition
             and frozen['outcome'] == protocol['outcome'] and set(frozen['submissions']) == set(KEYS[protocol['outcome']]), 'Complete frozen outcome')
        for key, filename in predictions.items():
            expected = receipt['output_inventory']['files'][key + '.h5']
            need(path(frozen['submissions'][key]['path']) == path(filename)
                 and frozen['submissions'][key]['sha256'] == expected['sha256']
                 and benchmark().hash_file(filename, FILE_CAP) == expected['sha256'], 'Immutable protected prediction lineage')
    lock = root / 'GRADE_STARTED.json'
    publish(lock, encoded({'closed_pair_sha256': closed_sha, 'one_final_grade': True,
                          'all_complete_predictions_authenticated_before_target_access': True}))
    # All intermediate reports live in one mode0700 temporary operator directory.
    # A second-arm failure publishes no paired numerical report or partial score.
    with tempfile.TemporaryDirectory(prefix='.smc-private-grade-', dir=final.parent) as temporary:
        reports = {}
        for condition in CONDITIONS:
            row = closed['conditions'][condition]
            report_path = Path(temporary) / (condition + '.json')
            reports[condition] = benchmark().score(row['freeze_path'], row['freeze']['sha256'],
                protocol['pair_path'], PAIR_SHA, protocol['task_path'], TASK_SHA,
                Path(protocol['pair_path']).parent / condition, target, evaluator, report_path,
                scratch_bytes=scratch_bytes, max_bytes=PAIR_CAP)
        need(pin(body(closed_path))['sha256'] == closed_sha, 'Closed pair unchanged after grading')
        result = {'schema': 'smc_aggregate_paired_measurements_v1', 'route': ROUTE,
            'closed_pair_sha256': closed_sha, 'outcome': protocol['outcome'], 'conditions': reports,
            'all_eight_reproduction_findings_or_complete_offline_four_vector_per_condition': True,
            'cross_condition_averaging': False, 'binary_reproduction_or_improvement_win': None,
            'generic_primary_profile_equivalence': False, 'AI_attribution_verified': False,
            'broader_SOTA_claim': False}
        publish(final, encoded(result), 0o600)
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    make = sub.add_parser('instantiate')
    for key in ('pair', 'task', 'runtime', 'output'):
        make.add_argument('--' + key, type=Path, required=True)
    make.add_argument('--runtime-sha256', required=True)
    make.add_argument('--outcome', choices=KEYS, required=True)
    for suffix in ('paper-data', 'assisted'):
        make.add_argument('--program-' + suffix, type=Path, required=True)
        make.add_argument('--declaration-' + suffix, type=Path, required=True)
    run = sub.add_parser('execute')
    for key in ('protocol', 'output'):
        run.add_argument('--' + key, type=Path, required=True)
    run.add_argument('--protocol-sha256', required=True)
    score = sub.add_parser('grade')
    for key in ('closed', 'target', 'evaluator', 'output'):
        score.add_argument('--' + key, type=Path, required=True)
    score.add_argument('--closed-sha256', required=True)
    score.add_argument('--scratch-bytes', type=int, required=True)
    args = p.parse_args(argv)
    if args.command == 'instantiate':
        result = instantiate(args.pair, args.task, args.outcome,
            dict(zip(CONDITIONS, (args.program_paper_data, args.program_assisted))),
            dict(zip(CONDITIONS, (args.declaration_paper_data, args.declaration_assisted))),
            args.runtime, args.runtime_sha256, args.output)
    elif args.command == 'execute':
        result = execute(args.protocol, args.protocol_sha256, args.output)
    else:
        result = grade(args.closed, args.closed_sha256, args.target, args.evaluator, args.output, args.scratch_bytes)
    print(encoded(result).decode(), end='')


if __name__ == '__main__':
    main()
