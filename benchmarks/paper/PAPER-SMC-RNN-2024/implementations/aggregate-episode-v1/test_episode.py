"""Generated metadata/filesystem controls only; no participant or native launch."""
import copy
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent


def load(name):
    spec = importlib.util.spec_from_file_location('_smc_aggregate_test_' + name, HERE / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


E = load('episode')
W = load('worker')
PIN = {'bytes': 1, 'sha256': 'a' * 64}


def request():
    return {'schema': E.REQUEST_SCHEMA, 'phase_id': E.CONDITIONS[0], 'source': PIN,
            'clock': {'origin': 1.0, 'phase_deadline': 100.0},
            'resources': {'cpu_seconds': 7200, 'producer_seconds': 10800,
                          'memory_bytes': 8589934592, 'cpu_nanos': 6000000000, 'pids': 32}}


def job():
    return {'schema': 'smc_aggregate_execution_job_v1', 'source': PIN,
            'condition': E.CONDITIONS[0], 'outcome': 'improvement',
            'resource_profile': E.PROFILES['improvement'], 'submission_keys': ['offline'],
            'program_sha256': 'b' * 64, 'declaration_sha256': 'c' * 64, 'max_file_bytes': E.FILE_CAP}


def deployment():
    return {'image': 'sha256:' + 'd' * 64, 'docker_binary': '/usr/bin/docker',
            'docker_socket': '/run/docker.sock', 'boot_id': '00000000-0000-0000-0000-000000000001',
            'pid_limit': 32, 'resource_policy': 'measured_caps_and_oom_kill_v1', 'cgroup_driver': 'cgroupfs',
            'qualification': {'path': '/operator/qualification.json', **PIN}, 'binding_pin': PIN,
            'delegation': {'path': '/sys/fs/cgroup/smc-tests', 'st_dev': 1, 'st_ino': 2, 'uid': 0,
                           'mount_id': 3, 'mount_point': '/sys/fs/cgroup', 'mount_root': '/', 'fs_type': 'cgroup2'}}


class EpisodeControls(unittest.TestCase):
    def setUp(self):
        self.no_process = mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('No native process control'))
        self.no_process.start()
        self.addCleanup(self.no_process.stop)

    def test_exact_source_and_compact_transport_encoding(self):
        self.assertEqual(E.source_identity(), E.pin((HERE / 'SOURCE.json').read_bytes()))
        E.provider_class()
        engine = sys.modules['_smc_aggregate_transport.engine']
        sample = {'schema': E.REQUEST_SCHEMA, 'unicode': 'α', 'nested': {'n': 2}}
        self.assertEqual(E.request_bytes(sample), engine.encoded(sample))
        self.assertNotEqual(E.encoded(sample), E.request_bytes(sample))
        self.assertEqual(set(E.read(HERE / 'SOURCE.json')['files']),
                         {'episode.py', 'worker.py', 'MATERIAL_BINDING.json', 'DEPLOYMENT_BINDING.json'})

    def test_selected_material_binds_accepted_actual_pair(self):
        binding = E.material_binding()
        expected = {'bytes': 5658, 'sha256': 'a88725a6d3b8c7509826d7c9a4034c796a04635e4bce80cb887468e688f976bc'}
        self.assertEqual(binding['new_pair'], expected)
        self.assertEqual(E.PAIR_SHA, expected['sha256'])
        self.assertEqual((binding['state'], binding['missing']), ('selected', []))

    def test_selected_material_rejects_wrong_pair_pin(self):
        old_read = E.read
        binding = copy.deepcopy(E.material_binding())
        binding['new_pair']['sha256'] = '0' * 64
        def read(p, *args, **kwargs):
            return binding if Path(p) == HERE / 'MATERIAL_BINDING.json' else old_read(p, *args, **kwargs)
        with mock.patch.object(E, 'read', side_effect=read):
            with self.assertRaisesRegex(ValueError, 'Selected new pair has exact source identity'):
                E.material_binding()

    def test_unresolved_material_refuses_before_caller_path_read(self):
        old = E.body
        old_read = E.read
        unresolved = copy.deepcopy(E.material_binding())
        unresolved.update(state='unresolved', new_pair=None, missing=['Generated unselected material'])
        def read(p, *args, **kwargs):
            return unresolved if Path(p) == HERE / 'MATERIAL_BINDING.json' else old_read(p, *args, **kwargs)
        seen = []
        def bounded(p, *args):
            seen.append(str(p))
            if str(p).startswith('/unread-candidate'):
                self.fail('Unresolved binding reached caller payload')
            return old(p, *args)
        with mock.patch.object(E, 'body', side_effect=bounded), mock.patch.object(E, 'read', side_effect=read):
            with self.assertRaisesRegex(ValueError, 'unresolved_material_binding'):
                E.public_context('/unread-candidate/pair_manifest.json', '/unread-candidate/task.json')
            with self.assertRaisesRegex(ValueError, 'unresolved_material_binding'):
                E.admit_protocol('/unread-candidate/PROTOCOL.json', 'a' * 64)
        self.assertFalse(any(p.startswith('/unread-candidate') for p in seen))

    def test_caller_qualification_flags_cannot_select_deployment(self):
        with self.assertRaisesRegex(ValueError, 'unresolved_deployment_binding'):
            E.runtime_config({'schema': 'smc_aggregate_runtime_v1', 'qualified': True})

    def test_public_execute_and_grade_refuse_without_any_file_read(self):
        with mock.patch.object(E, 'body', side_effect=AssertionError('No private input read')):
            with self.assertRaisesRegex(RuntimeError, 'unsupported_direct_execute'):
                E.execute('unused', 'unused', 'unused')
            with self.assertRaisesRegex(RuntimeError, 'aggregate_owner_grade_required'):
                E.grade('unused', 'unused', 'unused', 'unused', 'unused', 1)
        self.assertTrue(callable(E._grade_from_owned_pair))

    def test_episode_public0444_and_private0600_under077(self):
        with tempfile.TemporaryDirectory(prefix='smc-generated-public-mode-') as temporary:
            root = Path(temporary).resolve()
            before = os.umask(0o077)
            try:
                E.publish(root / 'public', b'public', 0o444)
                E.publish(root / 'private', b'private', 0o600)
            finally:
                os.umask(before)
            self.assertEqual(stat.S_IMODE((root / 'public').stat().st_mode), 0o444)
            self.assertEqual(stat.S_IMODE((root / 'private').stat().st_mode), 0o600)

    def test_matched_profiles_require_explicit_selected_pid_limit(self):
        selected = deployment()
        runtime = {'deployment': selected, 'source_read_bytes': 8192, 'host_write_bytes': 8192}
        with mock.patch.object(E, 'deployment_binding', return_value=selected):
            for outcome, cpu, wall in [('reproduction', 75000, 86400), ('improvement', 7200, 10800)]:
                r = E.resources(outcome, runtime)
                self.assertEqual((r['cpu_seconds'], r['producer_seconds'], r['memory_bytes'], r['cpu_nanos'], r['pids']),
                                 (cpu, wall, 8589934592, 6000000000, 32))
            with self.assertRaises(KeyError):
                E.resources('reproduction', {'source_read_bytes': 8192, 'host_write_bytes': 8192})

    def test_aggregate_plan_distinguishes_filesystem_and_daemon_paths(self):
        selected = deployment()
        invocation = {'aggregate_nonce': 'f' * 32, 'deployment_pin': PIN}
        with mock.patch.object(E, 'deployment_binding', return_value=selected):
            plans = [E.aggregate_plan(invocation, PIN, condition, {'deployment': selected}) for condition in E.CONDITIONS]
            self.assertNotEqual(plans[0]['path'], plans[1]['path'])
            for plan in plans:
                self.assertEqual(plan['path'], '/sys/fs/cgroup' + plan['cgroup_parent'])
                self.assertEqual(plan['invocation_pin'], PIN)
            with self.assertRaises(ValueError):
                E.aggregate_plan({**invocation, 'aggregate_nonce': '../bad'}, PIN, E.CONDITIONS[0], {'deployment': selected})

    def test_old_pair_resource_profile_refused_before_condition_files(self):
        pair = {'schema': 'smc_continuous_pair_v2', 'current_task_sha256': E.TASK_SHA,
                'policy_sha256': E.POLICY_SHA, 'conditions': list(E.CONDITIONS),
                'resource_budget': copy.deepcopy(E.PROFILES)}
        pair['resource_budget']['improvement']['memory_bytes'] = 4294967296
        def read(p, expected=None, **unused):
            if str(p) == '/operator/task.json':
                return {'id': E.TASK_ID}
            if str(p) == '/operator/pair_manifest.json':
                return pair
            self.fail('Wrong profile reached condition material')
        with mock.patch.object(E, 'material_binding', return_value={}), mock.patch.object(E, 'read', side_effect=read):
            with self.assertRaisesRegex(ValueError, 'matched aggregate budgets'):
                E.public_context('/operator/pair_manifest.json', '/operator/task.json')

    def test_closed_receipt_requires_parent_aggregate_ack(self):
        req = {**request(), 'image': 'sha256:' + 'd' * 64, 'role': 'A', 'aggregate': {'example': 1}}
        receipt = {'schema': E.RECEIPT_SCHEMA, 'status': 'captured', 'producer_closed_before_capture': True,
                   'all_native_resources_closed': True, 'cli_reaped': True,
                   'request_sha256': E.pin(E.request_bytes(req))['sha256'], 'phase_id': req['phase_id'],
                   'source': req['source'], 'image': req['image'], 'role': 'A',
                   'enforced_resource_limits': req['resources'], 'aggregate': req['aggregate'],
                   'aggregate_final_acknowledged': True, 'aggregate_custody_owner': 'parent',
                   'resource_custody_scope': 'docker_volume_holder_producer_only'}
        self.assertEqual(E.validate_closed(req, receipt), receipt)
        for key, value in [('aggregate_final_acknowledged', False), ('aggregate', {}),
                           ('resource_custody_scope', 'all_resources'), ('schema', 'osl_owned_phase_receipt_v1')]:
            with self.assertRaises(ValueError):
                E.validate_closed(req, {**receipt, key: value})


class WorkerControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='smc-generated-worker-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.patches = [mock.patch.object(W, name, self.root / filename) for name, filename in
                        [('JOB', 'job.json'), ('REQUEST', 'request.json'), ('READY', 'ready.json'), ('RELEASE', 'release.json')]]
        self.patches += [mock.patch.object(W.time, 'monotonic', return_value=2.0),
                         mock.patch.object(subprocess, 'Popen', side_effect=AssertionError('No native launch'))]
        for patch in self.patches:
            patch.start()
            self.addCleanup(patch.stop)
        W.JOB.write_bytes(W.encode(job()))
        W.REQUEST.write_bytes(W.compact(request()))

    def test_worker_authenticates_job_source_profile_and_compact_request(self):
        self.assertEqual(W.authenticated_inputs()[2], request())
        W.REQUEST.write_bytes(W.encode(request()))
        with self.assertRaisesRegex(ValueError, 'compact request'):
            W.authenticated_inputs()
        W.REQUEST.write_bytes(W.compact(request()))
        wrong = job()
        wrong['source'] = {'bytes': 2, 'sha256': 'b' * 64}
        W.JOB.write_bytes(W.encode(wrong))
        with self.assertRaisesRegex(ValueError, 'source, phase'):
            W.authenticated_inputs()

    def test_public_markers_under077_and_stale_release_refusal(self):
        req = request()
        value = W.marker(W.compact(req), req, 'release')
        before = os.umask(0o077)
        try:
            W.publish_marker(W.RELEASE, value, req)
        finally:
            os.umask(before)
        self.assertEqual(stat.S_IMODE(W.RELEASE.stat().st_mode), 0o444)
        self.assertEqual(stat.S_IMODE(W.RELEASE.with_name('release.json.publish-lock').stat().st_mode), 0o400)
        self.assertTrue(W.marker_available(W.RELEASE, value, req))
        old = W.RELEASE.read_bytes()
        with self.assertRaises(FileExistsError):
            W.publish_marker(W.RELEASE, value, req)
        self.assertEqual(W.RELEASE.read_bytes(), old)

    def test_waiter_cannot_observe_publication_before_fsync_and_unlock(self):
        req = request()
        value = W.marker(W.compact(req), req, 'ready')
        fsync = os.fsync
        observations = []
        def hook(fd):
            observations.append(W.marker_available(W.READY, value, req))
            return fsync(fd)
        with mock.patch.object(W.os, 'fsync', side_effect=hook):
            W.publish_marker(W.READY, value, req)
        self.assertEqual(observations, [False, False])
        self.assertTrue(W.marker_available(W.READY, value, req))

    def test_publication_failure_preserves_unowned_temp(self):
        stale = W.READY.with_name('ready.json.next')
        stale.write_bytes(b'unowned')
        req = request()
        with self.assertRaises(FileExistsError):
            W.publish_marker(W.READY, W.marker(W.compact(req), req, 'ready'), req)
        self.assertEqual(stale.read_bytes(), b'unowned')
        self.assertFalse(W.READY.exists())

    def test_directory_fsync_failure_removes_only_owned_final_marker(self):
        req = request()
        value = W.marker(W.compact(req), req, 'ready')
        fsync = os.fsync
        def hook(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError('generated directory-fsync failure')
            return fsync(fd)
        with mock.patch.object(W.os, 'fsync', side_effect=hook):
            with self.assertRaisesRegex(OSError, 'directory-fsync'):
                W.publish_marker(W.READY, value, req)
        self.assertFalse(W.READY.exists())
        self.assertFalse(W.marker_available(W.READY, value, req))

    def test_wrong_request_marker_and_original_deadline_refused(self):
        req = request()
        value = W.marker(W.compact(req), req, 'ready')
        W.publish_marker(W.READY, value, req)
        with self.assertRaises(ValueError):
            W.marker_available(W.READY, {**value, 'request_sha256': 'f' * 64}, req)
        with mock.patch.object(W.time, 'monotonic', return_value=100.0):
            with self.assertRaises(TimeoutError):
                W.release(job(), W.compact(req), req)
        self.assertFalse(W.RELEASE.exists())

    def test_release_helper_emits_exact_source_bound_reply(self):
        req = request()
        raw = W.compact(req)
        W.publish_marker(W.READY, W.marker(raw, req, 'ready'), req)
        output = io.StringIO()
        with mock.patch.object(sys, 'stdout', output):
            W.release(job(), raw, req)
        self.assertEqual(json.loads(output.getvalue()), {
            'schema': 'smc_producer_release_v1', 'phase_id': req['phase_id'],
            'request_sha256': E.pin(raw)['sha256'], 'source': PIN, 'phase_deadline': 100.0})
        self.assertTrue(W.marker_available(W.RELEASE, W.marker(raw, req, 'release'), req))

    def test_no_candidate_or_site_before_release(self):
        fake_site = types.SimpleNamespace(main=mock.Mock())
        with mock.patch.object(sys, 'argv', ['worker.py']), mock.patch.dict(sys.modules, site=fake_site), \
                mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.object(W.resource, 'setrlimit'), \
                mock.patch.object(W.resource, 'getrlimit', return_value=(7200, 7200)), \
                mock.patch.object(W, 'wait_marker', side_effect=TimeoutError('not released')), \
                mock.patch.object(W.runpy, 'run_path') as run:
            with self.assertRaises(TimeoutError):
                W.main()
            fake_site.main.assert_not_called()
            run.assert_not_called()

    def test_expiry_after_release_still_prevents_site_and_candidate(self):
        fake_site = types.SimpleNamespace(main=mock.Mock())
        with mock.patch.object(sys, 'argv', ['worker.py']), mock.patch.dict(sys.modules, site=fake_site), \
                mock.patch.dict(os.environ, {}, clear=False), \
                mock.patch.object(W.resource, 'setrlimit'), \
                mock.patch.object(W.resource, 'getrlimit', return_value=(7200, 7200)), \
                mock.patch.object(W, 'publish_marker'), mock.patch.object(W, 'wait_marker'), \
                mock.patch.object(W.time, 'monotonic', side_effect=[2.0, 100.0]), \
                mock.patch.object(W.runpy, 'run_path') as run:
            with self.assertRaises(TimeoutError):
                W.main()
            fake_site.main.assert_not_called()
            run.assert_not_called()


if __name__ == '__main__':
    counters = {'accepted_fixture_write_bytes': 0, 'ceiling_bytes': 24576}
    descriptor_paths = {}
    original_open, original_fdopen, original_write_bytes = os.open, os.fdopen, Path.write_bytes
    def fixture(p):
        return isinstance(p, (str, os.PathLike)) and any(str(part).startswith('smc-generated-') for part in Path(p).parts)
    def charge(n):
        counters['accepted_fixture_write_bytes'] += n
        if counters['accepted_fixture_write_bytes'] > counters['ceiling_bytes']:
            raise AssertionError('Generated fixture write ceiling exceeded')
    def tracked_open(p, *args, **kwargs):
        fd = original_open(p, *args, **kwargs)
        descriptor_paths[fd] = fixture(p)
        return fd
    class TrackedStream:
        def __init__(self, stream):
            self.stream = stream
        def __getattr__(self, name):
            return getattr(self.stream, name)
        def __enter__(self):
            self.stream.__enter__()
            return self
        def __exit__(self, *args):
            return self.stream.__exit__(*args)
        def write(self, value):
            if counters['accepted_fixture_write_bytes'] + len(value) > counters['ceiling_bytes']:
                raise AssertionError('Prospective generated fixture write ceiling')
            n = self.stream.write(value)
            charge(n)
            return n
    def tracked_fdopen(fd, *args, **kwargs):
        stream = original_fdopen(fd, *args, **kwargs)
        return TrackedStream(stream) if descriptor_paths.get(fd) else stream
    def tracked_write_bytes(p, value):
        if fixture(p) and counters['accepted_fixture_write_bytes'] + len(value) > counters['ceiling_bytes']:
            raise AssertionError('Prospective generated fixture write ceiling')
        n = original_write_bytes(p, value)
        if fixture(p):
            charge(n)
        return n
    with mock.patch.object(os, 'open', side_effect=tracked_open), \
            mock.patch.object(os, 'fdopen', side_effect=tracked_fdopen), \
            mock.patch.object(Path, 'write_bytes', tracked_write_bytes):
        result = unittest.main(verbosity=2, exit=False).result
    print(json.dumps({'schema': 'smc_episode_generated_fixture_accounting_v1', **counters,
                      'scope': 'successful byte counts from generated Path.write_bytes and os.fdopen.write; not gross filesystem IO',
                      'tests_run': result.testsRun, 'success': result.wasSuccessful()}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
