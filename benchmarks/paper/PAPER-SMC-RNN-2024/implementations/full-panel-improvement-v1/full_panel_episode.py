"""Explicit full-panel episode composition; native qualification stays separate.

The retained owner receives this instance through a source-authenticated overlay,
not through mutation of a retained module or a caller-selected implementation.
"""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import re
import signal
import stat
import sys
import tempfile
import time

TASK_ID = 'PAPER-SMC-RNN-2024'
INFERENCE_CONDITION = 'full_panel_offline_transductive_v1'
ROUTE = 'smc_full_panel_aggregate_v1'
CONDITIONS = ('paper_data', 'paper_data_author_code_and_weights')
OWNER_REL = 'benchmarks/paper/PAPER-SMC-RNN-2024/implementations/aggregate-owner-v1'
EPISODE_REL = 'benchmarks/paper/PAPER-SMC-RNN-2024/implementations/aggregate-episode-v1'
EPISODE_PIN = {'bytes': 37158, 'sha256': '75aaa0e67bcfe72ab1c33dddd8122006781cbc6eea1ba71bd3eae1d3c55b413d'}
EPISODE_SOURCE_PIN = {'bytes': 1485, 'sha256': '3057a8d8f292e299df9dcc66b6efddea6f6233304363c19b90a86fb0aef9696a'}
BENCHMARK_PIN = {'bytes': 43093, 'sha256': '2da9e6ee5c8cc47fd5440a3edbc3eeb275020359f6f7fd5d456c6f86d2c96b4f'}
TASK_PIN = {'bytes': 5474, 'sha256': '5b3b1008cca8f9106a5031ee9f15dfd028bd11121912316bd1fe788a32580c88'}
POLICY_PIN = {'bytes': 15519, 'sha256': 'f383e252c52fab1681451cd9247acb324d8ac7588099476155ce03fd92d2e75e'}
WORKER_PIN = {'bytes': 4726, 'sha256': 'c9bcc169882d9270812ed3c33b52599c9c0b73d13665d514f2d93904a3e5d8ff'}
PROFILE = {'cpu_seconds': 7200, 'wall_seconds': 10800, 'memory_bytes': 8589934592, 'threads': 6}
RUNTIME_FILES = {'full_panel_episode.py', 'full_panel_worker.py', 'owner_overlay.py', 'owner_legacy.py',
                 'RUNTIME_BINDING.json', 'MATERIAL_BINDING.json', 'DEPLOYMENT_BINDING.json'}


def _pin(raw):
    return {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}


def _read_source(path, expected):
    if (type(expected) is not dict or set(expected) != {'bytes', 'sha256'}
            or type(expected['bytes']) is not int or not 0 < expected['bytes'] <= 1024**2
            or type(expected['sha256']) is not str or re.fullmatch('[0-9a-f]{64}', expected['sha256']) is None):
        raise ValueError('Fixed bounded source descriptor')
    path = Path(path).absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError('Unlinked source path')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != expected['bytes']:
            raise ValueError('Exact ordinary source extent before read')
        raw = stream.read(expected['bytes'] + 1)
        after, named = os.fstat(stream.fileno()), path.lstat()
    fields = ('st_dev', 'st_ino', 'st_size', 'st_mode', 'st_nlink', 'st_mtime_ns', 'st_ctime_ns')
    if any(getattr(before, k) != getattr(after, k) or getattr(after, k) != getattr(named, k) for k in fields):
        raise ValueError('Stable exact source body')
    if _pin(raw) != expected:
        raise ValueError('Exact reviewed source bytes')
    return raw


def _module(name, path, expected):
    raw = _read_source(path, expected)
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    # No insertion, replacement or mutation of another module's global namespace.
    exec(compile(raw, str(path), 'exec'), module.__dict__)
    return module


class FullPanelEpisode:
    TASK_ID, ROUTE, CONDITIONS = TASK_ID, ROUTE, CONDITIONS
    PROFILES = {'improvement': PROFILE}
    KEYS = {'improvement': ['offline']}
    PAIR_CAP, FILE_CAP, META_CAP = 64 * 1024**2, 512 * 1024**2, 1024**2
    REQUEST_SCHEMA = 'smc_aggregate_phase_request_v1'
    RECEIPT_SCHEMA = 'smc_aggregate_phase_receipt_v1'
    OWNERSHIP_SCHEMA = 'smc_aggregate_phase_ownership_v1'
    JOURNAL_SCHEMA = 'smc_aggregate_transport_journal_v1'
    CLOSED_SCHEMA = 'smc_full_panel_closed_pair_v1'
    RECOVERY_SCHEMA = 'smc_aggregate_independent_phase_recovery_v1'
    ENGINE_MODULE = '_smc_aggregate_transport.engine'
    COMMAND = ['/usr/local/bin/python', '-I', '-S', '-B', '/runner/worker.py']

    def __init__(self, repository_root, component_root):
        self.repository_root = Path(repository_root).absolute()
        self.HERE = Path(component_root).absolute()
        retained_root = self.repository_root / EPISODE_REL
        _read_source(retained_root / 'SOURCE.json', EPISODE_SOURCE_PIN)
        self.retained = _module('_smc_full_panel_retained_episode', retained_root / 'episode.py', EPISODE_PIN)
        self.retained.source_identity()
        for name in ('need', 'path', 'body', 'read', 'publish', 'relative', 'descriptor', 'checked',
                     'encoded', 'request_bytes', 'pin', 'decode', 'file_mount', 'mount_identity',
                     'validate_closed', 'observe_closed', 'provider_class'):
            setattr(self, name, getattr(self.retained, name))
        binding = self.read(self.HERE / 'RUNTIME_BINDING.json')
        self.need(binding['schema'] == 'smc_full_panel_runtime_dependencies_v1'
                  and binding['retained_episode'] == EPISODE_PIN
                  and binding['retained_episode_source'] == EPISODE_SOURCE_PIN
                  and binding['benchmark'] == BENCHMARK_PIN and binding['task'] == TASK_PIN
                  and binding['policy'] == POLICY_PIN,
                  'Reviewed full-panel dependencies, no caller implementation override')
        self.BENCHMARK_PIN = self.descriptor(binding['benchmark'])
        self.TASK_SHA = self.descriptor(binding['task'])['sha256']
        self.POLICY_SHA = self.descriptor(binding['policy'])['sha256']
        _read_source(self.HERE / 'task.json', binding['task'])
        _read_source(self.HERE / 'policy.json', binding['policy'])
        module = _module('_smc_full_panel_continuous', self.HERE / 'benchmark.py', self.BENCHMARK_PIN)
        self.api = module.FullPanelAPI(self.repository_root, self.HERE)
        self.need(self.api.task_sha256 == self.TASK_SHA and self.api.policy_sha256 == self.POLICY_SHA,
                  'Continuous interface and composition agree on new identities')
        self.TRANSPORT = retained_root / 'vendor_transport'
        self.TRANSPORT_SHA = self.retained.TRANSPORT_SHA
        self._protocol = None
        self._protocol_path = None
        self._captured_actual = {}
        self._compatibility = _BenchmarkCompatibility(self)
        self.source_identity()

    @property
    def PAIR_SHA(self):
        return self.material_binding()['new_pair']['sha256']

    def benchmark(self):
        return self._compatibility

    def source_identity(self):
        manifest = self.read(self.HERE / 'RUNTIME_SOURCE.json')
        self.need(set(manifest) == {'schema', 'route', 'files', 'continuous_benchmark', 'retained_episode_source'}
                  and manifest['schema'] == 'smc_full_panel_runtime_source_v1'
                  and manifest['route'] == self.ROUTE and set(manifest['files']) == RUNTIME_FILES,
                  'Closed full-panel runtime source')
        for name, expected in manifest['files'].items():
            self.need(self.pin(self.body(self.HERE / name)) == self.descriptor(expected), 'Frozen runtime file')
        self.need(manifest['continuous_benchmark'] == self.BENCHMARK_PIN
                  and manifest['retained_episode_source'] == EPISODE_SOURCE_PIN
                  and manifest['files']['full_panel_worker.py'] == WORKER_PIN,
                  'Complete reviewed dependency binding')
        return self.pin(self.body(self.HERE / 'RUNTIME_SOURCE.json'))

    def implementation_identity(self):
        self.source_identity()
        return self.pin(self.request_bytes({'schema': 'smc_full_panel_implementation_v1',
            'episode': self.pin(self.body(self.HERE / 'full_panel_episode.py')),
            'worker': self.pin(self.body(self.HERE / 'full_panel_worker.py')),
            'continuous': self.BENCHMARK_PIN,
            'transport': self.pin(self.body(self.TRANSPORT / 'SOURCE_MANIFEST.json'))}))

    def material_binding(self):
        self.source_identity()
        value = self.read(self.HERE / 'MATERIAL_BINDING.json')
        self.need(set(value) == {'schema', 'state', 'task_sha256', 'policy_sha256', 'new_pair', 'missing'}
                  and value['schema'] == 'smc_full_panel_material_binding_v1'
                  and value['task_sha256'] == self.TASK_SHA and value['policy_sha256'] == self.POLICY_SHA,
                  'New source-selected material identity')
        self.need(value['state'] == 'selected' and value['missing'] == [] and value['new_pair'] is not None,
                  'unresolved_material_binding: fresh full-panel export has not been selected')
        self.descriptor(value['new_pair'])
        return value

    def public_context(self, pair_path, task_path):
        self.material_binding()
        self.api.current_task(task_path, self.TASK_SHA)
        pair = self.read(pair_path, self.PAIR_SHA)
        self.need(pair['schema'] == 'smc_full_panel_pair_v1' and pair['task_id'] == TASK_ID
                  and pair['current_task_sha256'] == self.TASK_SHA
                  and pair['policy_sha256'] == self.POLICY_SHA
                  and pair['inference_condition_id'] == INFERENCE_CONDITION
                  and pair['conditions'] == list(CONDITIONS)
                  and pair['resource_budget'] == self.PROFILES,
                  'Fresh full-panel pair and unchanged aggregate resource profiles')
        # Runtime exposure comes only from separately inspected method-gated views.
        return pair, {}

    def _method(self, condition, *, full=True):
        self.need(self._protocol is not None and condition in CONDITIONS, 'Admitted protocol context required')
        row = self._protocol['programs'][condition]['method']
        if not full:
            method = self.read(row['path'], row['sha256'])
            self.need(method['schema'] == 'smc_full_panel_method_freeze_v1'
                      and method['condition'] == condition and method['outcome'] == 'improvement'
                      and method['task_id'] == TASK_ID and method['inference_condition_id'] == INFERENCE_CONDITION
                      and method['current_task_sha256'] == self.TASK_SHA and method['policy_sha256'] == self.POLICY_SHA
                      and method['pair_sha256'] == self.PAIR_SHA and method['test_inputs_released'] is False,
                      'Exact pinned method metadata before owned data access')
            return method
        return self.api.inspect_method(row['path'], row['sha256'],
            self._protocol['pair_path'], self.PAIR_SHA, self._protocol['task_path'], self.TASK_SHA,
            condition, max_bytes=self.PAIR_CAP)

    def _release(self, condition, *, full=True):
        row = self._protocol['programs'][condition]
        release, method = row['release'], row['method']
        if not full:
            record = self.read(release['path'], release['sha256'])
            self.need(record['schema'] == 'smc_full_panel_inference_view_v1'
                      and record['condition'] == condition and record['task_id'] == TASK_ID
                      and record['inference_condition_id'] == INFERENCE_CONDITION
                      and record['current_task_sha256'] == self.TASK_SHA and record['policy_sha256'] == self.POLICY_SHA
                      and record['pair_sha256'] == self.PAIR_SHA
                      and record['method_freeze_sha256'] == method['sha256']
                      and record['release_after_method_freeze'] is True,
                      'Exact pinned release metadata before owned data access')
            return {'manifest': record, 'root': str(self.path(release['path']).parent)}
        return self.api.inspect_release(release['path'], release['sha256'], method['path'], method['sha256'],
            self._protocol['pair_path'], self.PAIR_SHA, self._protocol['task_path'], self.TASK_SHA,
            condition, max_bytes=self.PAIR_CAP)

    def instantiate(self, pair_path, task_path, method_records, runtime_path, runtime_sha, output):
        self.need(set(method_records) == set(CONDITIONS), 'Both already-frozen methods required')
        self.public_context(pair_path, task_path)
        runtime_raw = self.body(runtime_path)
        self.need(self.pin(runtime_raw)['sha256'] == runtime_sha, 'Exact runtime configuration')
        runtime = self.runtime_config(self.decode(runtime_raw))
        methods = {}
        for condition, selected in method_records.items():
            self.need(set(selected) == {'path', 'sha256'}, 'Exact method receipt selector')
            methods[condition] = self.api.inspect_method(selected['path'], selected['sha256'], pair_path,
                self.PAIR_SHA, task_path, self.TASK_SHA, condition, max_bytes=self.PAIR_CAP)
        root = self.path(output)
        self.need(not root.exists() and root.parent.is_dir()
                  and not root.is_relative_to(self.path(pair_path).parent), 'Fresh private protocol root')
        root.mkdir(mode=0o700)
        records = {}
        for condition in CONDITIONS:
            folder = root / condition
            folder.mkdir(mode=0o700)
            method = methods[condition]
            code = self.body(method['program']['path'], self.META_CAP)
            self.need(self.pin(code) == {k: method['program'][k] for k in ('bytes', 'sha256')},
                      'Immutable method programme before any inference release')
            records[condition] = {
                'method': dict(method_records[condition]),
                'program': self.publish(folder / 'program.py', code, 0o444),
                'declaration': self.publish(folder / 'declaration.json', self.encoded(method['plan']), 0o444)}
        # Both selected method snapshots and programme copies precede either release.
        for condition in CONDITIONS:
            folder = root / condition
            selected = records[condition]['method']
            self.api.release_inference_view(selected['path'], selected['sha256'], pair_path, self.PAIR_SHA,
                task_path, self.TASK_SHA, condition, folder / 'inference', max_bytes=self.PAIR_CAP)
            manifest = folder / 'inference' / 'inference_manifest.json'
            records[condition]['release'] = {'path': str(manifest), **self.pin(self.body(manifest))}
        protocol = {'schema': 'smc_full_panel_pair_protocol_v1', 'route': self.ROUTE, 'task_id': TASK_ID,
            'inference_condition_id': INFERENCE_CONDITION, 'pair_path': str(self.path(pair_path)),
            'pair_sha256': self.PAIR_SHA, 'task_path': str(self.path(task_path)), 'current_task_sha256': self.TASK_SHA,
            'outcome': 'improvement', 'source': self.source_identity(), 'resource_profile': PROFILE,
            'programs': records, 'runtime': self.publish(root / 'runtime.json', runtime_raw),
            'all_programmes_and_declarations_frozen_before_first_phase': True,
            'material_binding_pin': self.pin(self.body(self.HERE / 'MATERIAL_BINDING.json')),
            'deployment_binding_pin': runtime['deployment']['binding_pin'],
            'pre_test_authoring_isolation_verified': False,
            'pre_freeze_development_resources_measured_by_inference_owner': False,
            'experimental_qualification': 'unestablished', 'scientific_success': None,
            'execution_authorized_by_construction': False,
            'restrictions': {'max_kernel_tasks': runtime['deployment']['pid_limit'], 'cpu_rate_nanos': 6000000000,
                'generic_primary_profile_equivalence': False,
                'aggregate_cpu_rule': 'parent_meter_stop_and_final_admission_not_zero_overshoot',
                'host_candidate_execution': False}}
        self.publish(root / 'PROTOCOL.json', self.encoded(protocol))
        return protocol

    def admit_protocol(self, protocol_path, expected):
        if self._protocol_path != self.path(protocol_path):
            self._captured_actual.clear()
        try:
            return self._admit_protocol_impl(protocol_path, expected)
        except BaseException:
            self._protocol = self._protocol_path = None
            self._captured_actual.clear()
            raise

    def _admit_protocol_impl(self, protocol_path, expected):
        self.material_binding()
        self.deployment_binding()
        protocol_path = self.path(protocol_path)
        protocol = self.read(protocol_path, expected)
        self.need(protocol['schema'] == 'smc_full_panel_pair_protocol_v1' and protocol['route'] == self.ROUTE
                  and protocol['task_id'] == TASK_ID and protocol['inference_condition_id'] == INFERENCE_CONDITION
                  and protocol['source'] == self.source_identity() and protocol['pair_sha256'] == self.PAIR_SHA
                  and protocol['current_task_sha256'] == self.TASK_SHA and protocol['outcome'] == 'improvement'
                  and protocol['resource_profile'] == PROFILE and set(protocol['programs']) == set(CONDITIONS)
                  and protocol['all_programmes_and_declarations_frozen_before_first_phase'] is True,
                  'Exact full-panel method/programme scope')
        self.need(protocol['pre_test_authoring_isolation_verified'] is False
                  and protocol['pre_freeze_development_resources_measured_by_inference_owner'] is False
                  and protocol['experimental_qualification'] == 'unestablished',
                  'Do not manufacture authoring-custody or resource evidence')
        self._protocol, self._protocol_path = protocol, protocol_path
        self.public_context(protocol['pair_path'], protocol['task_path'])
        for condition, row in protocol['programs'].items():
            self.need(set(row) == {'method', 'program', 'declaration', 'release'}, 'Closed method and release binding')
            method = self._method(condition, full=False)
            self.need(self.pin(self.body(protocol_path.parent / condition / 'program.py')) == row['program']
                      == {k: method['program'][k] for k in ('bytes', 'sha256')}, 'Both programmes remain frozen')
            self.need(self.pin(self.body(protocol_path.parent / condition / 'declaration.json')) == row['declaration']
                      and self.read(protocol_path.parent / condition / 'declaration.json') == method['plan'],
                      'Pre-run declaration is the frozen PLAN, not actual-use evidence')
            self.need(self.path(row['release']['path']) == protocol_path.parent / condition / 'inference' / 'inference_manifest.json',
                      'Only this protocol-owned full-panel release')
            self._release(condition, full=False)
        self.need(self.pin(self.body(protocol_path.parent / 'runtime.json')) == protocol['runtime'], 'Frozen runtime')
        runtime = self.runtime_config(self.read(protocol_path.parent / 'runtime.json'))
        self.need(protocol['material_binding_pin'] == self.pin(self.body(self.HERE / 'MATERIAL_BINDING.json'))
                  and protocol['deployment_binding_pin'] == runtime['deployment']['binding_pin'], 'Exact selected bindings')
        self.need(protocol['restrictions'] == {'max_kernel_tasks': runtime['deployment']['pid_limit'],
                  'cpu_rate_nanos': 6000000000, 'generic_primary_profile_equivalence': False,
                  'aggregate_cpu_rule': 'parent_meter_stop_and_final_admission_not_zero_overshoot',
                  'host_candidate_execution': False}, 'Unchanged whole-tree inference restrictions')
        return protocol, runtime

    def mounts_for(self, protocol_path, protocol, condition, job_path, job_pin, manifests):
        self.need(protocol is self._protocol or protocol == self._protocol, 'Admitted protocol before exposure')
        release = self._release(condition)
        root = self.path(release['root'])
        result = {}
        rows = {row['path']: {k: row[k] for k in ('bytes', 'sha256')} for row in release['manifest']['files']}
        rows['inference_manifest.json'] = {k: protocol['programs'][condition]['release'][k] for k in ('bytes', 'sha256')}
        for name, expected in rows.items():
            self.relative(name)
            purpose = 'historical_author_source' if name.startswith('official_source/') or name in ('official_source_manifest.json', 'official_asset_manifest.json') else 'input'
            result['/materials/' + name] = self.file_mount(root / name, expected, purpose)
        folder = self.path(protocol_path).parent / condition
        row = protocol['programs'][condition]
        result['/program/program.py'] = self.file_mount(folder / 'program.py', row['program'], 'program')
        result['/declaration.json'] = self.file_mount(folder / 'declaration.json', row['declaration'], 'contract')
        result['/execution.json'] = self.file_mount(job_path, job_pin, 'contract')
        result['/runner/worker.py'] = self.file_mount(self.HERE / 'full_panel_worker.py', self.pin(self.body(self.HERE / 'full_panel_worker.py')), 'program')
        retained_worker = self.repository_root / EPISODE_REL / 'worker.py'
        result['/runner/retained_worker.py'] = self.file_mount(retained_worker,
            {'bytes': 11424, 'sha256': '2fc10bb2b608e7f1e4a803588cff1123add5aa7c6fbb92eb6b22cea028a9b473'}, 'program')
        method = self._method(condition)
        for name, asset in method['selected_artifacts'].items():
            self.relative(name)
            result['/selected_artifacts/' + name] = self.file_mount(asset['path'], {k: asset[k] for k in ('bytes', 'sha256')}, 'input')
        return result

    def job_for(self, protocol, condition):
        row = protocol['programs'][condition]
        return {'schema': 'smc_aggregate_execution_job_v1', 'inference_condition_id': INFERENCE_CONDITION,
            'outcome': 'improvement', 'condition': condition, 'source': protocol['source'],
            'resource_profile': PROFILE, 'submission_keys': ['offline'], 'program_sha256': row['program']['sha256'],
            'declaration_sha256': row['declaration']['sha256'], 'method_freeze_sha256': row['method']['sha256'],
            'max_file_bytes': self.FILE_CAP}

    def captured_predictions(self, receipt, condition, outcome, programme):
        self.need(outcome == 'improvement' and self._protocol is not None, 'Full-panel improvement only')
        files = receipt['output_inventory']['files']
        self.need(receipt['output_inventory']['complete'] is True
                  and set(files) == {'offline.h5', 'actual_declaration.json', 'RESULT.json', 'OUTPUTS.json'},
                  'Complete prediction and post-run declaration inventory')
        root = self.path(receipt['quarantine_root'])
        result = self.read(root / 'RESULT.json', files['RESULT.json']['sha256'])
        self.need(result == {'schema': 'smc_full_panel_program_result_v1', 'inference_condition_id': INFERENCE_CONDITION,
            'outcome': 'improvement', 'condition': condition, 'program_sha256': programme['program']['sha256'],
            'declaration_sha256': programme['declaration']['sha256'], 'method_freeze_sha256': programme['method']['sha256'],
            'submission_keys': ['offline']}, 'Captured output joins the actual frozen method')
        for name in ('offline.h5', 'actual_declaration.json'):
            expected = files[name]
            self.need((root / name).lstat().st_size == expected['bytes']
                      and self.api.hash_file(root / name, self.FILE_CAP) == expected['sha256'], 'Closed output changed')
        self._captured_actual[condition] = {'path': str(root / 'actual_declaration.json'),
            'pin': files['actual_declaration.json'], 'program': programme,
            'prediction_path': str(root / 'offline.h5'), 'prediction_pin': files['offline.h5']}
        return {'offline': root / 'offline.h5'}


    # Identity-sensitive retained proof paths, explicitly rebound to this instance.
    def deployment_binding(self):
        self.source_identity()
        binding = self.read(self.HERE / 'DEPLOYMENT_BINDING.json')
        self.need(set(binding) == {'schema', 'state', 'selected', 'missing'} and binding['schema'] == 'smc_aggregate_deployment_binding_v1', 'Exact source-selected deployment binding')
        self.need(binding['state'] == 'selected' and binding['missing'] == [], 'unresolved_deployment_binding: scientific image, same-host delegated cgroup and PID qualification are not selected')
        selected = binding['selected']
        self.need(type(selected) is dict and set(selected) == {'image', 'docker_binary', 'docker_socket', 'boot_id', 'delegation', 'pid_limit', 'qualification', 'resource_policy', 'cgroup_driver'}, 'Closed selected deployment shape')
        self.need(selected['resource_policy'] == 'measured_caps_and_oom_kill_v1', 'Exact measured-cap and OOM-kill policy')
        self.need(selected['cgroup_driver'] == 'cgroupfs', 'Exact same-host cgroupfs driver; systemd paths are not interchangeable')
        self.need(type(selected['image']) is str and re.fullmatch('sha256:[a-f0-9]{64}', selected['image']), 'Pinned immutable scientific image')
        self.need(type(selected['pid_limit']) is int and selected['pid_limit'] > 0, 'Explicit selected PID ceiling; never a default')
        self.need(type(selected['boot_id']) is str and re.fullmatch('[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', selected['boot_id']), 'Selected same-boot Linux deployment')
        for key in ('docker_binary', 'docker_socket'):
            self.path(selected[key])
        delegation = selected['delegation']
        self.need(type(delegation) is dict and set(delegation) == {'path', 'st_dev', 'st_ino', 'uid', 'mount_id', 'mount_point', 'mount_root', 'fs_type'}, 'Exact selected delegated-root identity')
        for key in ('st_dev', 'st_ino', 'uid', 'mount_id'):
            self.need(type(delegation[key]) is int and delegation[key] >= 0, 'Typed delegated-root identity')
        self.need(delegation['fs_type'] == 'cgroup2' and delegation['mount_root'] == '/', 'Selected cgroup2 mount coordinates; slash alone is not same-host proof')
        self.need(self.path(delegation['path']).is_relative_to(self.path(delegation['mount_point'])) and self.path(delegation['path']) != self.path(delegation['mount_point']), 'Dedicated delegated root below selected mount')
        self.need(type(selected['qualification']) is dict and set(selected['qualification']) == {'path', 'bytes', 'sha256'}, 'Qualification is source-selected, not caller booleans')
        self.descriptor({k: selected['qualification'][k] for k in ('bytes', 'sha256')})
        self.path(selected['qualification']['path'])
        return {**selected, 'binding_pin': self.pin(self.body(self.HERE / 'DEPLOYMENT_BINDING.json'))}

    def runtime_config(self, value):
        deployment = self.deployment_binding()
        keys = {'schema', 'image', 'docker_binary', 'docker_socket', 'qualification', 'source_read_bytes', 'host_write_bytes'}
        self.need(type(value) is dict and set(value) == keys and (value['schema'] == 'smc_aggregate_runtime_v1'), 'Explicit operator runtime configuration')
        self.need(type(value['image']) is str and re.fullmatch('sha256:[a-f0-9]{64}', value['image']), 'Existing immutable image only')
        for key in ('source_read_bytes', 'host_write_bytes'):
            self.need(type(value[key]) is int and value[key] > 0, 'Finite externally allocated whole-pair I/O')
        self.need(all((value[k] == deployment[k] for k in ('image', 'docker_binary', 'docker_socket', 'qualification'))), 'Runtime must equal source-selected deployment; no caller qualification override')
        self.checked(value['qualification'])
        return {**value, 'deployment': deployment}

    def qualify(self, runtime, source):
        deployment = self.deployment_binding()
        self.need(runtime['deployment'] == deployment and source == self.source_identity(), 'Exact selected deployment and complete source before qualification')
        self.need(sys.platform == 'linux' and hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'), 'Existing provider requires a qualified Linux/pidfd operator; native macOS is unsupported')
        record = self.decode(self.checked(runtime['qualification']))
        expected = {'schema', 'route', 'implementation', 'image', 'image_inventory_sha256', 'profiles', 'boot_id', 'delegation', 'pid_limit', 'resource_policy', 'cgroup_driver', 'evidence'}
        self.need(set(record) == expected and record['schema'] == 'smc_aggregate_runtime_qualification_v1' and (record['route'] == self.ROUTE) and (record['implementation'] == self.implementation_identity()) and (record['image'] == runtime['image']) and (record['profiles'] == self.PROFILES) and all((record[key] == deployment[key] for key in ('boot_id', 'delegation', 'pid_limit', 'resource_policy', 'cgroup_driver'))), 'Source-selected qualification binds operational bytes and exact deployment; no caller flags')
        self.need(type(record['image_inventory_sha256']) is str and re.fullmatch('[a-f0-9]{64}', record['image_inventory_sha256']), 'Reviewed generic scientific image inventory')
        evidence = record['evidence']
        self.need(type(evidence) is dict and set(evidence) == {'image_inventory', 'scientific_packages', 'six_thread_probe', 'aggregate_cpu_probe', 'containment_probe', 'closure_probe', 'same_host_pid_cgroup_probe'}, 'Complete source-selected external qualification evidence set')
        for row in evidence.values():
            self.decode(self.checked(row))
        self.need(evidence['image_inventory']['sha256'] == record['image_inventory_sha256'], 'Exact inventory receipt join')
        return record

    def resources(self, outcome, runtime):
        p = self.PROFILES[outcome]
        deployment = self.deployment_binding()
        self.need(runtime['deployment'] == deployment, 'Only source-selected PID and deployment limits')
        return {'setup_seconds': 60, 'producer_seconds': p['wall_seconds'], 'capture_seconds': 300, 'cleanup_seconds': 60, 'memory_bytes': p['memory_bytes'], 'cpu_nanos': 6000000000, 'cpu_seconds': p['cpu_seconds'], 'pids': deployment['pid_limit'], 'scratch_bytes': 512 * 1024 ** 2, 'max_files': 4, 'max_directories': 1, 'max_file_bytes': self.FILE_CAP, 'max_output_bytes': 2 * self.FILE_CAP + 4096, 'manifest_bytes': 65536, 'max_cli_calls': 256, 'max_cli_bytes': 8 * 1024 ** 2, 'inventory_bytes': 65536, 'source_read_bytes': runtime['source_read_bytes'] // 2, 'host_write_bytes': runtime['host_write_bytes'] // 2}

    def aggregate_plan(self, invocation, invocation_pin, condition, runtime):
        self.need(condition in self.CONDITIONS, 'Exact paired access condition')
        self.descriptor(invocation_pin)
        deployment = self.deployment_binding()
        self.need(runtime['deployment'] == deployment and invocation['deployment_pin'] == deployment['binding_pin'], 'Invocation retains exact source-selected delegation')
        nonce = invocation['aggregate_nonce']
        self.need(type(nonce) is str and re.fullmatch('[a-f0-9]{32}', nonce), 'Fresh bound aggregate nonce')
        name = 'smc-' + nonce + ('-a' if condition == self.CONDITIONS[0] else '-b')
        parent = str(self.path(deployment['delegation']['path']))
        scope_path = Path(parent) / name
        daemon_parent = '/' + str(scope_path.relative_to(self.path(deployment['delegation']['mount_point'])))
        return {'schema': 'smc_cgroup_plan_v1', 'phase_id': condition, 'name': name, 'parent': parent, 'path': str(scope_path), 'cgroup_parent': daemon_parent, 'deployment_pin': deployment['binding_pin'], 'invocation_pin': invocation_pin}

    def _grade_from_owned_pair(self, closed_path, closed_sha, target, evaluator, output, scratch_bytes):
        """Private helper called by the source-bound owner only after all its proofs."""
        closed = self.read(closed_path, closed_sha)
        self.need(closed['schema'] == self.CLOSED_SCHEMA and closed['route'] == self.ROUTE and (closed['both_conditions_closed_before_private_grade'] is True) and (closed['private_target_accessed'] is False) and (set(closed['conditions']) == set(self.CONDITIONS)), 'Both protected conditions required before first target read')
        protocol, runtime = self.admit_protocol(closed['protocol_path'], closed['protocol_sha256'])
        self.need(closed['source'] == protocol['source'] and closed['outcome'] == protocol['outcome'], 'Closed pair scope')
        self.need(closed['runtime_qualification'] == runtime['qualification'], 'Same externally admitted runtime qualification')
        _, manifests = self.public_context(protocol['pair_path'], protocol['task_path'])
        root = self.path(closed_path).parent
        final = self.path(output)
        self.need(not final.exists() and final.parent.is_dir() and (not final.is_relative_to(Path(protocol['pair_path']).parent)) and (not final.is_relative_to(Path(closed['protocol_path']).parent)), 'Private final report outside public materials')
        for condition in self.CONDITIONS:
            row = closed['conditions'][condition]
            self.need(self.path(row['receipt_path']) == root / 'control' / condition / 'RECEIPT.json' and self.path(row['freeze_path']) == root / 'freezes' / (condition + '.json'), 'Only owned protected outputs may enter scoring')
            receipt = self.read(row['receipt_path'], row['receipt']['sha256'])
            self.need(self.pin(self.body(row['receipt_path'])) == row['receipt'], 'Closed exact observed receipt')
            request_path = root / 'jobs' / condition / 'REQUEST.json'
            request = self.read(request_path, row['request']['sha256'])
            self.need(request['schema'] == self.REQUEST_SCHEMA and self.pin(self.body(request_path)) == row['request'] == self.pin(self.request_bytes(request)) and (request['phase_id'] == condition) and (request['role'] == ('A' if condition == self.CONDITIONS[0] else 'B')) and (request['image'] == runtime['image']) and (request['source'] == protocol['source']) and (request['command'] == self.COMMAND) and (request['workdir'] == '/work') and (request['action'] == 'held_attempt') and (request['resources'] == self.resources(protocol['outcome'], runtime)) and (request['output'] == {'kind': 'generic', 'manifest': 'OUTPUTS.json'}), 'Current exact executed request/profile')
            self.need(request['aggregate']['phase_id'] == condition and request['aggregate']['deployment_pin'] == runtime['deployment']['binding_pin'] and (request['aggregate']['invocation_pin'] == closed['owner_invocation_pin']), 'Aggregate request joins exact owner invocation and selected deployment')
            self.validate_closed(request, receipt)
            self.need(self.path(receipt['quarantine_root']) == root / 'quarantine' / condition, 'Owned immutable quarantine only')
            job_path = root / 'jobs' / condition / 'EXECUTION.json'
            self.need(self.read(job_path) == self.job_for(protocol, condition), 'Exact executed job binds outcome, programme and CPU profile')
            mounts = self.mounts_for(closed['protocol_path'], protocol, condition, job_path, self.pin(self.body(job_path)), manifests)
            identity = self.mount_identity(mounts)
            exposure = self.read(root / 'jobs' / condition / 'EXPOSURE.json', request['exposure']['sha256'])
            self.need(self.pin(self.body(root / 'jobs' / condition / 'EXPOSURE.json')) == request['exposure'] and exposure['mounts'] == identity and (exposure['source'] == protocol['source']) and (exposure['image'] == runtime['image']) and (exposure['role'] == request['role']) and (exposure['command'] == self.COMMAND) and (exposure['boundary_audit'] == {k: runtime['qualification'][k] for k in ('bytes', 'sha256')}), 'Current exact exposure and qualification join')
            self.need(receipt['exposure'] == request['exposure'] and receipt['input_before'] == identity and (receipt['input_after'] == identity), 'Exact condition files remained unchanged through capture')
            predictions = self.captured_predictions(receipt, condition, protocol['outcome'], protocol['programs'][condition])
            frozen = self.read(row['freeze_path'], row['freeze']['sha256'])
            self.need(self.pin(self.body(row['freeze_path'])) == row['freeze'] and frozen['condition'] == condition and (frozen['outcome'] == protocol['outcome']) and (set(frozen['submissions']) == set(self.KEYS[protocol['outcome']])), 'Complete frozen outcome')
            for key, filename in predictions.items():
                expected = receipt['output_inventory']['files'][key + '.h5']
                self.need(self.path(frozen['submissions'][key]['path']) == self.path(filename) and frozen['submissions'][key]['sha256'] == expected['sha256'] and (self.benchmark().hash_file(filename, self.FILE_CAP) == expected['sha256']), 'Immutable protected prediction lineage')
        lock = root / 'GRADE_STARTED.json'
        self.publish(lock, self.encoded({'closed_pair_sha256': closed_sha, 'one_final_grade': True, 'all_complete_predictions_authenticated_before_target_access': True}))
        with tempfile.TemporaryDirectory(prefix='.smc-private-grade-', dir=final.parent) as temporary:
            reports = {}
            for condition in self.CONDITIONS:
                row = closed['conditions'][condition]
                report_path = Path(temporary) / (condition + '.json')
                reports[condition] = self.benchmark().score(row['freeze_path'], row['freeze']['sha256'], protocol['pair_path'], self.PAIR_SHA, protocol['task_path'], self.TASK_SHA, Path(protocol['pair_path']).parent / condition, target, evaluator, report_path, scratch_bytes=scratch_bytes, max_bytes=self.PAIR_CAP)
            self.need(self.pin(self.body(closed_path))['sha256'] == closed_sha, 'Closed pair unchanged after grading')
            result = {'schema': 'smc_full_panel_paired_measurements_v1', 'route': self.ROUTE, 'closed_pair_sha256': closed_sha, 'outcome': protocol['outcome'], 'conditions': reports, 'complete_offline_four_vector_per_condition': True, 'inference_condition_id': INFERENCE_CONDITION, 'transductive_fixed_panel': True, 'fresh_trial_generalization': False, 'pre_test_authoring_isolation_verified': False, 'pre_freeze_development_resources_measured_by_inference_owner': False, 'cross_condition_averaging': False, 'binary_reproduction_or_improvement_win': None, 'generic_primary_profile_equivalence': False, 'AI_attribution_verified': False, 'broader_SOTA_claim': False}
            self.publish(final, self.encoded(result), 384)
        return result

class _BenchmarkCompatibility:
    """Supply explicit protocol joins to the unchanged two-phase owner API."""
    def __init__(self, episode):
        self.episode = episode
        self.hash_file = episode.api.hash_file

    def inspect_pair(self, *args, **kwargs):
        result = self.episode.api.inspect_pair(*args, **kwargs)
        # The unchanged owner calls this only after its active custody ACK.
        for condition in CONDITIONS:
            self.episode._method(condition)
            self.episode._release(condition)
        return result

    def freeze(self, pair_path, pair_sha, task_path, task_sha, condition, outcome,
               submissions, planned_path, output, *, max_bytes):
        L = self.episode
        L.need(outcome == 'improvement' and condition in L._captured_actual,
               'Closed provider capture before actual-use freeze')
        row = L._protocol['programs'][condition]
        actual = L._captured_actual[condition]
        L.need(L.path(planned_path) == L._protocol_path.parent / condition / 'declaration.json'
               and L.pin(L.body(planned_path)) == row['declaration']
               and actual['program'] == row
               and L.path(submissions['offline']) == L.path(actual['prediction_path']),
               'Join owner planned path, frozen programme and exact captured outputs')
        L.need(L.pin(L.body(actual['path'])) == actual['pin'], 'Post-run declaration remains immutable')
        return L.api.freeze(pair_path, pair_sha, task_path, task_sha, condition, outcome, submissions,
            actual['path'], output, max_bytes=max_bytes,
            method_path=row['method']['path'], method_sha256=row['method']['sha256'])

    def score(self, frozen_path, frozen_sha, pair_path, pair_sha, task_path, task_sha,
              condition_root, target, evaluator, output, *, scratch_bytes, max_bytes):
        L = self.episode
        frozen = L.read(frozen_path, frozen_sha)
        condition = frozen['condition']
        L.need(condition in CONDITIONS and L._protocol is not None, 'Protected admitted condition for score')
        row = L._protocol['programs'][condition]
        return L.api.score(frozen_path, frozen_sha, pair_path, pair_sha, task_path, task_sha,
            condition_root, target, evaluator, output, scratch_bytes=scratch_bytes, max_bytes=max_bytes,
            method_path=row['method']['path'], method_sha256=row['method']['sha256'])
