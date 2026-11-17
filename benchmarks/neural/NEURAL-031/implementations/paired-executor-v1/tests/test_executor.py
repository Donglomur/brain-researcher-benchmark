"""Independent generated executor controls: no Docker, candidate or authentic data."""
from __future__ import annotations

import copy
import io
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import tarfile
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
import common
import docker_backend as db
import executor as ex

IMAGE = 'sha256:' + '1' * 64
COUNTS = [37, 23, 52, 94, 50, 21, 33, 64, 53, 24, 67, 18, 23, 31, 57, 22, 28, 24, 31, 22]
WRITTEN = 0
RECLAIMED = 0
CAP = int(os.environ.get('NEURAL031_GENERATED_WRITE_CAP', '1400000'))


def charge(body):
    global WRITTEN
    if WRITTEN + len(body) > CAP:
        raise AssertionError('Generated cumulative artifact allocation exceeded before write')
    WRITTEN += len(body)


def fixture_write(path, body):
    charge(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)


def compressed(values):
    stream = io.BytesIO()
    np.savez_compressed(stream, **values)
    return stream.getvalue()


def tar_bytes(body=b'{}', name='predictions.json', kind=tarfile.REGTYPE, *, extra=False, pax=None):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w', format=tarfile.PAX_FORMAT if pax else tarfile.USTAR_FORMAT) as archive:
        info = tarfile.TarInfo(name)
        info.type = kind
        info.size = len(body) if kind == tarfile.REGTYPE else 0
        if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE): info.linkname = '/private/targets'
        if pax: info.pax_headers = pax
        archive.addfile(info, io.BytesIO(body) if info.size else None)
        if extra:
            info = tarfile.TarInfo('extra.json'); info.size = 1
            archive.addfile(info, io.BytesIO(b'x'))
    return stream.getvalue()


class FakeClock:
    def __init__(self): self.now = 0.0
    def __call__(self): return self.now


class SimulatedBackend:
    def __init__(self, fault=None):
        self.events, self.specs, self.fault = [], [], fault
        self.closed = []
        self.absence_checked = False

    def verify_image(self, image, deadline):
        assert image == IMAGE
        self.events.append({'event': 'generated-image-check'})
        if self.fault == 'setup_timeout': deadline.clock.now = 481

    def run_context(self, spec, deadline):
        assert len(self.closed) == len(self.specs), 'prior context must close'
        self.specs.append(copy.deepcopy(spec))
        mounts = {destination: Path(source) for source, destination in spec['mounts']}
        assert set(mounts) == {'/input/data.npz', '/input/manifest.json', '/program/submission.py'}
        assert all(stat.S_IMODE(path.stat().st_mode) & 0o222 == 0 for path in mounts.values())
        assert common.pin(mounts['/program/submission.py'].read_bytes()) == spec['program_pin']
        manifest_body = mounts['/input/manifest.json'].read_bytes()
        manifest = common.decode(manifest_body)
        assert common.pin(manifest_body) == spec['input_pins']['manifest']
        data = mounts['/input/data.npz'].read_bytes()
        assert common.pin(data) == spec['input_pins']['data']
        with np.load(io.BytesIO(data), allow_pickle=False) as packet:
            assert set(packet.files) == {'train_x', 'train_y', 'train_mouse', 'train_rowid', 'query_x', 'query_rowid'}
            expected_columns = 4 if spec['view'] == 'baseline' else 6
            assert packet['query_x'].shape[1] == packet['train_x'].shape[1] == expected_columns
            assert spec['fold'] not in packet['train_mouse']
            ids = packet['query_rowid'].tolist()
            if spec['view'] == 'baseline':
                assert not np.any(packet['query_x'] == 73.0)
            else:
                assert np.all(packet['query_x'][:, 4] == 73.0)
        output = {'schema': 'neural031_ordinary_prediction_v1', 'candidate_id': 'NEURAL-031',
                  'fold': spec['fold'], 'view': spec['view'],
                  'input_manifest': common.pin(manifest_body),
                  'rows': [{'row_id': row, 'prediction': 1.0} for row in ids]}
        if self.fault == 'malformed_last' and len(self.specs) == 40: output['rows'].pop()
        if self.fault == 'mutate_frozen':
            path = mounts['/program/submission.py']; path.chmod(0o600)
            fixture_write(path, b'# changed source bytes\n')
        self.closed.append(spec['name'])
        self.events.append({'event': 'generated-closure', 'name': spec['name']})
        return common.encoded(output)

    def absent_all(self, deadline):
        assert len(self.closed) == len(self.specs) == 40
        self.absence_checked = True
        self.events.append({'event': 'generated-all-absent'})
        if self.fault == 'unclosed_batch': raise ValueError('generated remaining producer')


class FullExecutorControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='generated-n031-executor-')
        cls.root = Path(cls.temp.name)
        cls.store = cls.root / 'store'; cls.store.mkdir()
        cls.delivery, cls.endpoint, cls.scorer = common.dependencies()
        cls.dependencies = (cls.delivery, cls.endpoint, cls.scorer)
        ids = np.arange(774, dtype=np.int64)
        groups = np.repeat(np.arange(20, dtype=np.int64), COUNTS)
        y = np.ones(774, dtype=np.float64); y[np.arange(0, 731, 17)] = np.nan; y[1] = 0
        source = copy.deepcopy(cls.delivery.inputs())
        support = {'schema': 'neural031_ordinary_public_support_v1', 'candidate_id': 'NEURAL-031',
                   'folds': [], 'request_rows': 774, 'query_targets_included': False}
        for fold in range(20):
            train, query = groups != fold, groups == fold
            row = {'fold': fold, 'rowids': ids[query].tolist(), 'views': {}}
            for view in ('baseline', 'neural'):
                x = np.column_stack((np.ones(774), ids % 2, np.zeros(774), np.zeros(774))).astype(np.float64)
                if view == 'neural': x = np.column_stack((x, np.full(774, 73.0), np.full(774, -11.0)))
                packet = {'train_x': x[train], 'train_y': y[train], 'train_mouse': groups[train],
                          'train_rowid': ids[train], 'query_x': x[query], 'query_rowid': ids[query]}
                data = compressed(packet)
                manifest = cls.delivery.public_manifest(fold, view, packet, common.pin(data), cls.endpoint.MICE)
                body = common.encoded(manifest)
                for name, content in (('data.npz', data), ('manifest.json', body)):
                    fixture_write(cls.store / f'public/fold{fold:02d}' / view / name, content)
                pair = {'data': common.pin(data), 'manifest': common.pin(body)}
                row['views'][view] = pair
                source['paired_views'][2 * fold + (view == 'neural')].update(pair)
            support['folds'].append(row)
        body = common.encoded(support); fixture_write(cls.store / 'support.json', body)
        source['support'] = common.pin(body)
        cls.source, cls.support = source, support
        cls.program = cls.root / 'caller.py'; cls.program_body = b'# frozen generated source; never executed\n'
        fixture_write(cls.program, cls.program_body)
        cls.method = {'schema': 'neural031_frozen_program_method_v1', 'program': common.pin(cls.program_body),
                      'method': 'Generated transport-only constant-ratio fixture; no candidate execution',
                      'same_method_across_views': True, 'training_only_selection': True,
                      'image_inventory_review_sha256': '2' * 64, 'method_review_sha256': '3' * 64}
        target = {'schema': 'neural031_ratio_targets_v1', 'candidate_id': 'NEURAL-031',
                  'mice': list(cls.endpoint.MICE), 'rows': []}
        for rowid in range(1143):
            request = rowid < 774; observed = request and np.isfinite(y[rowid])
            target['rows'].append({'rowid': rowid, 'mouse': int(groups[rowid]) if request else rowid % 20,
                'y': float(y[rowid]) if observed else None, 'request': int(request), 'observed': int(observed),
                'baseline_new': rowid % 2, 'compartment': rowid % 2})
        cls.target = cls.root / 'generated-targets.json'
        body = common.encoded(target); fixture_write(cls.target, body); cls.target_sha = common.pin(body)['sha256']
        cls.original_writer = cls.delivery.Writer.write
        cls.original_write = ex.write

    @classmethod
    def tearDownClass(cls):
        global RECLAIMED
        for directory, _, files in os.walk(cls.root):
            Path(directory).chmod(0o700)
            for name in files: (Path(directory) / name).chmod(0o600)
        cls.temp.cleanup()
        assert not cls.root.exists()
        RECLAIMED = WRITTEN

    def setUp(self):
        self.output = self.root / self._testMethodName
        self.clock = FakeClock()
        def writer(instance, relative, body, cap):
            charge(body)
            return type(self).original_writer(instance, relative, body, cap)
        def write(path, body, cap, mode=0o600):
            charge(body)
            return type(self).original_write(path, body, cap, mode)
        self.patchers = [mock.patch.object(ex, 'dependencies', return_value=self.dependencies),
                         mock.patch.object(self.delivery.Writer, 'write', writer),
                         mock.patch.object(ex, 'write', write)]
        for patcher in self.patchers: patcher.start()
        self.addCleanup(lambda: [patcher.stop() for patcher in reversed(self.patchers)])

    def execute(self, backend, score=False):
        args = (self.store, self.program, self.output, IMAGE, self.method)
        kwargs = dict(backend=backend, clock=self.clock, _source=self.source, _generated=True)
        if score: return ex.run_and_score(*args, self.target, self.target_sha, **kwargs)
        return ex.execute(*args, **kwargs)

    def test_complete_forty_contexts_same_program_public_admission_before_real_scorer(self):
        backend = SimulatedBackend(); accesses = []
        original_read = self.scorer.read_json
        def guarded_read(path, *args, **kwargs):
            if Path(path) == self.target:
                self.assertTrue(backend.absence_checked)
                self.assertEqual(len(backend.closed), 40)
                self.assertTrue((self.output / 'BATCH.json').exists())
                accesses.append('private_generated_target')
            return original_read(path, *args, **kwargs)
        with mock.patch.object(self.scorer, 'read_json', guarded_read):
            result = self.execute(backend, score=True)
        self.assertEqual(accesses, ['private_generated_target'])
        batch, score = result['batch'], result['score']
        self.assertEqual(len(batch['contexts']), 40)
        self.assertEqual({row['program']['sha256'] for row in batch['contexts']}, {common.pin(self.program_body)['sha256']})
        self.assertEqual(len({row['container_name'] for row in batch['contexts']}), 40)
        self.assertEqual(batch['scope'], 'generated_command_simulation')
        self.assertFalse(batch['independent_runtime_qualification'])
        self.assertEqual((score['request_rows'], score['scored_rows'], score['unavailable_rows']), (774, 731, 43))
        self.assertEqual(score['primary'], 0.0)
        self.assertGreater(score['macro']['baseline_mae'], 0)
        self.assertEqual(batch['collection']['predictions'], 1548)

    def test_malformed_last_context_never_opens_private_targets_or_accepts_batch(self):
        backend = SimulatedBackend('malformed_last')
        with mock.patch.object(self.scorer, 'run', side_effect=AssertionError('must not score')) as scorer:
            with self.assertRaises(ValueError): self.execute(backend, score=True)
        scorer.assert_not_called()
        self.assertEqual(len(backend.closed), 40)
        self.assertFalse((self.output / 'BATCH.json').exists())
        self.assertEqual(common.decode((self.output / 'FAILURE.json').read_bytes())['private_targets_opened'], 0)

    def test_mutated_frozen_program_refuses_before_capture_commit(self):
        backend = SimulatedBackend('mutate_frozen')
        with self.assertRaises(ValueError): self.execute(backend)
        self.assertEqual(len(backend.specs), 1)
        self.assertFalse((self.output / 'BATCH.json').exists())
        self.assertEqual(common.decode((self.output / 'FAILURE.json').read_bytes())['completed_captures'], 0)

    def test_whole_deadline_includes_initial_image_setup(self):
        backend = SimulatedBackend('setup_timeout')
        with self.assertRaises(TimeoutError): self.execute(backend)
        self.assertEqual(backend.specs, [])
        self.assertEqual(common.decode((self.output / 'FAILURE.json').read_bytes())['batch_wall_seconds'], 481)

    def test_simulated_backend_cannot_enter_production_route(self):
        with self.assertRaises(ValueError):
            ex.execute(self.store, self.program, self.output, IMAGE, self.method, backend=SimulatedBackend())
        self.assertFalse(self.output.exists())

    def test_final_absence_failure_blocks_private_scoring(self):
        backend = SimulatedBackend('unclosed_batch')
        with mock.patch.object(self.scorer, 'run', side_effect=AssertionError('must not score')) as scorer:
            with self.assertRaises(ValueError): self.execute(backend, score=True)
        scorer.assert_not_called()
        self.assertEqual(len(backend.specs), 40)
        self.assertFalse((self.output / 'BATCH.json').exists())

    def test_deadline_after_batch_write_reclassifies_receipt_and_blocks_scoring(self):
        backend = SimulatedBackend()
        original_write = ex.write
        def late_write(path, body, cap, mode=0o600):
            result = original_write(path, body, cap, mode)
            if Path(path).name == 'BATCH.json': self.clock.now = 481
            return result
        with mock.patch.object(ex, 'write', late_write):
            with mock.patch.object(self.scorer, 'run', side_effect=AssertionError('must not score')) as scorer:
                with self.assertRaises(TimeoutError): self.execute(backend, score=True)
        scorer.assert_not_called()
        self.assertFalse((self.output / 'BATCH.json').exists())
        self.assertTrue((self.output / 'UNACCEPTED_BATCH.json').exists())
        self.assertEqual(common.decode((self.output / 'FAILURE.json').read_bytes())['batch_wall_seconds'], 481)


def context_spec():
    batch = 'a' * 24
    return {'fold': 0, 'view': 'baseline', 'batch': batch, 'name': f'n031-{batch}-00-b',
            'image': IMAGE, 'mounts': [('/generated/data.npz', '/input/data.npz'),
                ('/generated/manifest.json', '/input/manifest.json'),
                ('/generated/submission.py', '/program/submission.py')],
            'program_pin': {'bytes': 2, 'sha256': '4' * 64}, 'input_pins': {}}


class DockerScript:
    """Explicit byte-level command simulation; never invokes Docker or subprocess."""
    def __init__(self, spec, fault=None, mutate=None):
        self.spec, self.fault, self.mutate = spec, fault, mutate
        self.exists = fault == 'initial_collision'
        self.running = self.paused = False
        self.calls = []
        self.image_env = ['PATH=/usr/local/bin:/usr/bin:/bin', 'LANG=C.UTF-8']
        self.capture = tar_bytes(b'{"generated":true}')

    def inspection(self):
        spec = self.spec
        host = {'NetworkMode': 'none', 'ReadonlyRootfs': True, 'Memory': 3221225472,
                'MemorySwap': 3221225472, 'NanoCpus': 1750000000, 'PidsLimit': 256,
                'IpcMode': 'none', 'PidMode': '', 'Privileged': False, 'Devices': [],
                'DeviceRequests': None, 'CapAdd': None, 'CapDrop': ['ALL'],
                'Tmpfs': {'/output': 'rw,nosuid,nodev,noexec,size=1048576,mode=0700,uid=65534,gid=65534',
                          '/tmp': 'rw,nosuid,nodev,size=3221225472,mode=0700,uid=65534,gid=65534'},
                'LogConfig': {'Type': 'none'}, 'RestartPolicy': {'Name': 'no'},
                'SecurityOpt': ['no-new-privileges:true']}
        config = {'User': '65534:65534', 'WorkingDir': '/tmp', 'Entrypoint': ['/usr/local/bin/python'],
                  'Cmd': ['-I', '-B', '-c', 'import signal; signal.pause()'],
                  'Volumes': None, 'Labels': {'neural031.batch': spec['batch']},
                  'Env': self.image_env + list(db.ENV)}
        value = {'Name': '/' + spec['name'], 'Image': IMAGE, 'HostConfig': host,
                 'Config': config, 'State': {'Running': self.running, 'Paused': self.paused},
                 'Mounts': [{'Type': 'bind', 'Source': src, 'Destination': dst, 'RW': False}
                            for src, dst in spec['mounts']]}
        if self.fault == 'wrong_owner': config['Labels']['neural031.batch'] = 'foreign'
        if self.mutate: self.mutate(value)
        return value

    def __call__(self, argv, deadline, cap):
        assert argv[:3] == ['/docker-not-executed', '--host', 'unix:///var/run/docker.sock']
        args = argv[3:]; self.calls.append(list(args))
        if args[:2] == ['image', 'inspect']:
            value = {'Id': IMAGE, 'Os': 'linux', 'Config': {'Env': self.image_env, 'Volumes': None}}
            if self.fault == 'image_volume': value['Config']['Volumes'] = {'/leak': {}}
            if self.fault == 'image_secret': value['Config']['Env'] = self.image_env + ['API_TOKEN=forbidden']
            if self.fault == 'image_duplicate': value['Config']['Env'] = self.image_env + ['PATH=/other']
            return common.encoded([value])
        if args[0] == 'ps':
            if self.fault == 'daemon_error': raise OSError('generated daemon unavailable')
            return b'c' * 64 + b'\n' if self.exists else b''
        if args[0] == 'create': self.exists = True; return b'c' * 64 + b'\n'
        if args[0] == 'start': self.running = True; return self.spec['name'].encode() + b'\n'
        if args[:2] == ['container', 'inspect']: return common.encoded([self.inspection()])
        if args[0] == 'exec':
            assert args == ['exec', '--user', '65534:65534', self.spec['name'],
                '/usr/local/bin/python', '-I', '-B', '/program/submission.py',
                '--input', '/input/data.npz', '--manifest', '/input/manifest.json',
                '--output', '/output/predictions.json']
            if self.fault in ('candidate_failure', 'wrong_owner'): raise ValueError('generated candidate failure')
            if self.fault == 'timeout': deadline.clock.now = 481
            return b''
        if args[0] == 'pause': self.paused = self.fault != 'unpaused'; return b'paused\n'
        if args[0] == 'cp':
            assert self.paused, 'capture must occur while every producer process is frozen'
            return self.capture
        if args[0] == 'rm':
            if self.fault == 'remove_failure': raise OSError('generated removal failure')
            self.exists = self.running = self.paused = False
            return b'removed\n'
        raise AssertionError('Unexpected production Docker operation: ' + repr(args))


class DockerLifecycleControls(unittest.TestCase):
    def setup_backend(self, fault=None, mutate=None):
        spec = context_spec(); script = DockerScript(spec, fault, mutate)
        backend = db.DockerBackend(command=script)
        deadline = db.Deadline(clock=FakeClock())
        backend.verify_image(IMAGE, deadline)
        return spec, script, backend, deadline

    def test_exact_production_commands_pause_capture_remove_and_absence(self):
        spec, script, backend, deadline = self.setup_backend()
        body = backend.run_context(spec, deadline)
        self.assertEqual(body, b'{"generated":true}')
        self.assertFalse(script.exists)
        steps = [row[0] for row in script.calls]
        self.assertEqual(steps, ['image', 'ps', 'create', 'start', 'container', 'exec', 'pause', 'container', 'cp', 'rm', 'ps'])
        create = next(row for row in script.calls if row[0] == 'create')
        for option, expected in (('--network', 'none'), ('--ipc', 'none'), ('--user', '65534:65534'),
                ('--memory', '3221225472'), ('--memory-swap', '3221225472'), ('--cpus', '1.75'),
                ('--pids-limit', '256'), ('--pull', 'never'), ('--log-driver', 'none')):
            self.assertEqual(create[create.index(option) + 1], expected)
        self.assertIn('--read-only', create)
        mounts = [create[i + 1] for i, value in enumerate(create) if value == '--mount']
        self.assertEqual(mounts, [f'type=bind,src={src},dst={dst},readonly' for src, dst in spec['mounts']])
        self.assertEqual([event['paused'] for event in backend.events if event['event'] == 'context_inspected'], [False, True])
        self.assertFalse(backend.real_transport)
        with self.assertRaises(ValueError): backend.run_context(spec, deadline)

    def test_image_requires_immutable_identity_no_volumes_secrets_or_duplicate_env(self):
        for fault in ('image_volume', 'image_secret', 'image_duplicate'):
            with self.subTest(fault=fault), self.assertRaises(ValueError): self.setup_backend(fault)
        spec = context_spec(); script = DockerScript(spec)
        backend = db.DockerBackend(command=script)
        with self.assertRaises(ValueError): backend.verify_image('python:latest', db.Deadline(clock=FakeClock()))
        self.assertEqual(script.calls, [])

    def test_actual_unsafe_mount_env_resource_or_network_settings_refuse_before_exec(self):
        mutations = [lambda row: row['HostConfig'].__setitem__('NetworkMode', 'host'),
                     lambda row: row['HostConfig'].__setitem__('MemorySwap', 0),
                     lambda row: row['HostConfig'].__setitem__('ReadonlyRootfs', False),
                     lambda row: row['Config']['Env'].append('EXTRA_SECRET=forbidden'),
                     lambda row: row['Config'].__setitem__('User', '0'),
                     lambda row: row['Mounts'][0].__setitem__('RW', True),
                     lambda row: row['Mounts'].append({'Type': 'volume', 'Destination': '/escape', 'RW': True})]
        for mutate in mutations:
            spec, script, backend, deadline = self.setup_backend(mutate=mutate)
            with self.assertRaises(ValueError): backend.run_context(spec, deadline)
            self.assertNotIn('exec', [row[0] for row in script.calls])
            self.assertFalse(script.exists)
            self.assertTrue(backend.events[-1]['absence_verified'])

    def test_initial_name_collision_never_removes_foreign_resource(self):
        spec, script, backend, deadline = self.setup_backend('initial_collision')
        with self.assertRaises(ValueError): backend.run_context(spec, deadline)
        self.assertTrue(script.exists)
        self.assertNotIn('rm', [row[0] for row in script.calls])
        self.assertNotIn('create', [row[0] for row in script.calls])

    def test_wrong_owned_label_blocks_cleanup_and_reports_unknown_closure(self):
        spec, script, backend, deadline = self.setup_backend('wrong_owner')
        with self.assertRaises(ValueError): backend.run_context(spec, deadline)
        self.assertTrue(script.exists)
        self.assertNotIn('rm', [row[0] for row in script.calls])
        self.assertFalse(backend.events[-1]['absence_verified'])

    def test_unpaused_capture_candidate_failure_or_removal_error_cannot_succeed(self):
        for fault in ('unpaused', 'candidate_failure', 'remove_failure'):
            spec, script, backend, deadline = self.setup_backend(fault)
            with self.assertRaises((ValueError, OSError)): backend.run_context(spec, deadline)
            if fault != 'remove_failure': self.assertNotIn('cp', [row[0] for row in script.calls])
            self.assertEqual(backend.events[-1]['absence_verified'], fault != 'remove_failure')

    def test_expired_whole_deadline_records_separate_cleanup_never_success(self):
        spec, script, backend, deadline = self.setup_backend('timeout')
        with self.assertRaises(TimeoutError): backend.run_context(spec, deadline)
        self.assertFalse(script.exists)
        self.assertTrue(backend.events[-1]['absence_verified'])
        self.assertEqual(backend.events[-1]['batch_deadline_elapsed_seconds'], 481)
        self.assertNotIn('cp', [row[0] for row in script.calls])

    def test_daemon_failure_is_not_absence_and_transport_caps_are_enforced(self):
        spec, script, backend, deadline = self.setup_backend('daemon_error')
        with self.assertRaises(OSError): backend.absent_all(deadline) if backend.names else backend.absent(spec['name'], deadline)
        backend = db.DockerBackend(command=lambda argv, clock, cap: b'x' * (cap + 1))
        with self.assertRaises(ValueError): backend._command(['generated'], db.Deadline(clock=FakeClock()), cap=16)


class CaptureControls(unittest.TestCase):
    def test_regular_prediction_and_inert_pax_timestamp_are_allowed(self):
        self.assertEqual(db.prediction_from_tar(tar_bytes(b'{"ok":1}')), b'{"ok":1}')
        self.assertEqual(db.prediction_from_tar(tar_bytes(b'{}', pax={'mtime': '1.25'})), b'{}')

    def test_links_special_files_traversal_extra_output_and_path_pax_refused(self):
        bodies = [tar_bytes(kind=kind) for kind in (tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE, tarfile.CHRTYPE)]
        bodies += [tar_bytes(name='../predictions.json'), tar_bytes(extra=True),
                   tar_bytes(pax={'path': 'predictions.json'}), tar_bytes(pax={'size': '2'})]
        for body in bodies:
            with self.assertRaises((ValueError, tarfile.TarError)): db.prediction_from_tar(body)

    def test_trailing_bytes_truncation_oversize_and_bad_checksum_refused(self):
        body = tar_bytes(); bad_checksum = bytearray(body); bad_checksum[0] ^= 1
        for bad in (body[:-1], body + b'x' * 512, bytes(bad_checksum),
                    tar_bytes(body=b'x' * 131073), b'\0' * 262656):
            with self.assertRaises((ValueError, tarfile.TarError)): db.prediction_from_tar(bad)


if __name__ == '__main__':
    try:
        unittest.main()
    finally:
        record = {'scope': 'generated simulated transport only', 'generated_logical_bytes_written': WRITTEN,
                  'generated_logical_bytes_reclaimed': RECLAIMED, 'retained_generated_bytes': WRITTEN - RECLAIMED,
                  'authentic_payload_reads': 0, 'docker_calls': 0, 'candidate_program_runs': 0}
        if os.environ.get('NEURAL031_EXECUTOR_ACCOUNTING'):
            Path(os.environ['NEURAL031_EXECUTOR_ACCOUNTING']).write_text(json.dumps(record, indent=2) + '\n')
        print(json.dumps(record))
