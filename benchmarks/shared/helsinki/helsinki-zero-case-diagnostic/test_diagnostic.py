"""Generated interfaces only: never execute Docker, cgroups or the fixture."""
import copy
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('zero_case_diagnostic', HERE / 'diagnostic.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
SOURCE = (HERE / 'SOURCE.json').read_bytes()
MANIFEST, BODIES = d.authenticate(HERE, d.digest(SOURCE))
M = d.load_modules(HERE, BODIES)
C = M['common']
IMAGE = d.strict(BODIES['SYNTHETIC_IMAGE.json'])


def request(output):
    parent = output.parent.stat()
    return {'schema': d.SCHEMA, 'selection': {'operation_id': 'generated-only', 'mode': 'run',
        'authority_sha256': 'a' * 64, 'output': str(output), 'parent_device': parent.st_dev,
        'parent_inode': parent.st_ino}, 'provisioning_authority_sha256': 'b' * 64,
        'target': {'python': {'path': str(Path(sys.executable).resolve()), 'bytes': 1,
        'sha256': '1' * 64}, 'docker': {'path': '/generated/docker', 'bytes': 1,
        'sha256': '2' * 64}, 'socket': '/generated/socket', 'socket_guard': {
        'dev': 1, 'inode': 2, 'mode': 3, 'uid': os.getuid(), 'gid': 0, 'nlink': 1},
        'image_id': IMAGE['image_id'], 'architecture': 'amd64'}, 'provision': {
        'schema': M['parent_observer'].SCHEMA, 'boot_id': '00000000-0000-0000-0000-000000000000',
        'kernel_release': 'generated-kernel', 'mount_id': 1, 'cgroup_namespace_inode': 2,
        'delegation_path': '/sys/fs/cgroup/generated', 'delegation_device': 1,
        'delegation_inode': 2, 'daemon_id': 'generated-daemon', 'daemon_version': '0',
        'cgroup_driver': 'cgroupfs', 'cgroup_version': '2'}}


def daemon(p):
    return {'ID': p['daemon_id'], 'ServerVersion': p['daemon_version'],
        'KernelVersion': p['kernel_release'], 'OSType': 'linux', 'Architecture': 'x86_64',
        'CgroupDriver': 'cgroupfs', 'CgroupVersion': '2'}


class Diagnostic(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix='helsinki-generated-')
        self.root = Path(self.tmp).resolve()

    def tearDown(self):
        for base, dirs, files in os.walk(self.root):
            os.chmod(base, 0o700)
        shutil.rmtree(self.root)

    def test_manifest_identity_namespace_symlink(self):
        package = self.root / 'package'
        shutil.copytree(HERE, package)
        d.authenticate(package, d.digest(SOURCE))
        (package / 'unlisted.py').write_text('raise RuntimeError("must never import")\n')
        with self.assertRaisesRegex(ValueError, 'namespace'):
            d.authenticate(package, d.digest(SOURCE))
        (package / 'unlisted.py').unlink()
        target = package / 'EMPTY_INPUT.json'
        original = target.read_bytes()
        target.unlink(); target.symlink_to(HERE / 'EMPTY_INPUT.json')
        with self.assertRaisesRegex(ValueError, 'symlink'):
            d.authenticate(package, d.digest(SOURCE))
        target.unlink(); target.write_bytes(original + b' ')
        with self.assertRaisesRegex(ValueError, 'identity'):
            d.authenticate(package, d.digest(SOURCE))

    def test_selection_and_target_denials(self):
        output = self.root / 'op'; req = request(output)
        d.validate_request(req, 'run', output, IMAGE)
        for field, value in [('selection', None), ('provisioning_authority_sha256', None)]:
            bad = copy.deepcopy(req); bad[field] = value
            with self.assertRaises(ValueError): d.validate_request(bad, 'run', output, IMAGE)
        for field, value in [('image_id', 'sha256:' + '0' * 64), ('architecture', 'arm64')]:
            bad = copy.deepcopy(req); bad['target'][field] = value
            with self.assertRaises(ValueError): d.validate_request(bad, 'run', output, IMAGE)
        with self.assertRaises(ValueError): d.validate_request(req, 'check', output, IMAGE)

    def test_daemon_image_mismatches(self):
        req = request(self.root / 'op'); info = daemon(req['provision'])
        d.validate_daemon(info, req['provision'])
        for key, value in [('CgroupDriver', 'systemd'), ('CgroupVersion', '1'),
                           ('KernelVersion', 'other'), ('ID', 'other'), ('Architecture', 'aarch64')]:
            bad = dict(info); bad[key] = value
            with self.assertRaises(ValueError): d.validate_daemon(bad, req['provision'])
        good = {'Id': IMAGE['image_id'], 'Os': 'linux', 'Architecture': 'amd64', 'Config': {}}
        d.validate_image([good], IMAGE)
        for key, value in [('Id', 'sha256:' + '0' * 64), ('Architecture', 'arm64'),
                           ('Config', {'Volumes': {'/input': {}}})]:
            bad = dict(good); bad[key] = value
            with self.assertRaises(ValueError): d.validate_image([bad], IMAGE)

    def test_delegation_readonly_refusal_closes_fd(self):
        module = M['parent_observer']; fd = os.open(self.root, os.O_RDONLY)
        s = os.fstat(fd); p = request(self.root / 'op')['provision']
        p.update(delegation_device=s.st_dev, delegation_inode=s.st_ino)
        observer = types.SimpleNamespace(provision=p, _host=lambda: {'generated': True})
        values = {'cgroup.procs': '', 'cgroup.type': 'domain\n',
                  'cgroup.subtree_control': 'cpu memory pids\n'}
        with patch.object(module, 'open_directory', return_value=fd), \
             patch.object(module, 'filesystem_magic', return_value=module.MAGIC), \
             patch.object(module, 'children', return_value=['unrelated']), \
             patch.object(module, 'read_at', side_effect=lambda f,n,b: values[n]):
            with self.assertRaisesRegex(ValueError, 'exclusive delegation'):
                d.check_delegation(module, observer, C.Budget(time.monotonic()+10, 10000, 10000))
        with self.assertRaises(OSError) as raised: os.fstat(fd)
        self.assertEqual(raised.exception.errno, errno.EBADF)

    def test_preflight_wrong_driver_never_creates(self):
        req = request(self.root / 'op'); c = M['participant_container']
        policy = {'profile': M['participant_policy'].PROFILE, 'image': IMAGE['image_id'],
                  'runtime_manifest_sha256': 'a'*64, 'observer_source_sha256': 'b'*64,
                  'source_closure_sha256': 'c'*64, 'wall_seconds': 15,
                  'cpu_seconds': 120, 'memory_bytes': 1073741824}
        info = daemon(req['provision']); info['CgroupDriver'] = 'systemd'
        calls = []
        def command(argv, **kwargs):
            calls.append(argv)
            return {'complete': True, 'exit_code': 0}, C.encode(info), b''
        with patch.object(d.sys, 'platform', 'linux'), patch.object(d.platform, 'machine', return_value='x86_64'), \
             patch.object(d, 'authenticate_executable'), patch.object(c, 'daemon_guard'), \
             patch.object(c, 'configure_cli', return_value={}), patch.object(c, 'cli_argv', side_effect=lambda x:x), \
             patch.object(d, 'check_delegation', return_value={}), patch.object(c, 'command', side_effect=command), \
             patch.object(c, 'run_candidate', side_effect=AssertionError('native dispatch forbidden')):
            with self.assertRaisesRegex(ValueError, 'cgroupfs'):
                d.preflight(req, M, self.root, policy, IMAGE,
                    C.Budget(time.monotonic()+10, 1048576, 8388608), time.monotonic()+5)
        self.assertEqual(calls, [['info', '--format', '{{json .}}']])

    def test_closed_owned_flow_and_bad_output(self):
        output = self.root / 'op'; req = request(output); c = M['participant_container']
        observed = {}
        def run_candidate(**kw):
            observed.update(kw)
            self.assertEqual((kw['bundle_dir']/'solution.py').read_bytes(), BODIES['fixture_solution.py'])
            self.assertEqual((kw['input_dir']/'EMPTY_INPUT.json').read_bytes(), BODIES['EMPTY_INPUT.json'])
            root = kw['root']; root.mkdir(mode=0o700)
            submission = C.write(root/'SUBMISSION.private.bin', d.EXPECTED, kw['budget'])
            life = C.write(root/'LIFECYCLE.private.json', C.encode({'candidate_closed': True,
                'remaining_owned_cid': None, 'kernel_accounting': {'CPU_seconds': .125,
                'peak_memory_bytes': 9437184}}), kw['budget'])
            return c.ClosedRun(submission, life, c._CLOSED_TOKEN)
        with patch.object(d, 'preflight', return_value=object()), patch.object(c, 'run_candidate', side_effect=run_candidate):
            result = d.operate(req, 'run', output, M, BODIES, d.digest(SOURCE), time.monotonic())
        self.assertEqual(result['status'], 'synthetic_lifecycle_observed')
        self.assertFalse(result['runtime_qualified']); self.assertFalse(result['production_gate_changed'])
        self.assertEqual(observed['policy']['image'], IMAGE['image_id'])
        self.assertEqual(result, C.decode((output/'REPORT.json').read_bytes()))
        bad = c.ClosedRun({'path': str(output/'unrelated'), 'bytes': 0, 'sha256': d.digest(b'')},
                         {'path': str(output/'run/LIFECYCLE.private.json')}, c._CLOSED_TOKEN)
        with self.assertRaisesRegex(ValueError, 'artifact locations'):
            d.inspect_closed(bad, c, C, output/'run', C.Budget(time.monotonic()+5, 10000, 10000))

    def test_preflight_two_metadata_calls_only(self):
        req = request(self.root / 'op'); c = M['participant_container']
        policy = {'profile': M['participant_policy'].PROFILE, 'image': IMAGE['image_id'],
                  'runtime_manifest_sha256': 'a'*64, 'observer_source_sha256': 'b'*64,
                  'source_closure_sha256': 'c'*64, 'wall_seconds': 15,
                  'cpu_seconds': 120, 'memory_bytes': 1073741824}
        values = [daemon(req['provision']), [{'Id': IMAGE['image_id'], 'Os': 'linux',
                  'Architecture': 'amd64', 'Config': {}}]]
        calls = []
        def command(argv, **kw):
            calls.append(argv)
            record = {'complete': True, 'exit_code': 0}
            self.assertTrue(kw['observed']('finished', record))
            return record, C.encode(values[len(calls)-1]), b''
        with patch.object(d.sys, 'platform', 'linux'), patch.object(d.platform, 'machine', return_value='x86_64'), \
             patch.object(d, 'authenticate_executable'), patch.object(c, 'daemon_guard'), \
             patch.object(c, 'configure_cli', return_value={}), patch.object(c, 'cli_argv', side_effect=lambda x:x), \
             patch.object(d, 'check_delegation', return_value={}), patch.object(c, 'command', side_effect=command), \
             patch.object(c, 'run_candidate', side_effect=AssertionError('native dispatch forbidden')):
            observer = d.preflight(req, M, self.root, policy, IMAGE,
                    C.Budget(time.monotonic()+10, 1048576, 8388608), time.monotonic()+5)
        self.assertIsNone(observer.active)
        self.assertEqual(calls, [['info', '--format', '{{json .}}'], ['image', 'inspect', IMAGE['image_id']]])
        self.assertFalse(C.decode((self.root/'PREFLIGHT.json').read_bytes())['runtime_qualified'])

    def test_counterfeit_output_and_insufficient_counters(self):
        c = M['participant_container']
        for number, output, cpu, peak in ((0, b'{}\n', .1, 8388608),
                (1, d.EXPECTED, .099, 8388608), (2, d.EXPECTED, .1, 8388607)):
            root = self.root / str(number); root.mkdir()
            budget = C.Budget(time.monotonic()+5, 10000, 10000)
            artifact = C.write(root/'SUBMISSION.private.bin', output, budget)
            life = C.write(root/'LIFECYCLE.private.json', C.encode({'candidate_closed': True,
                'remaining_owned_cid': None, 'kernel_accounting': {'CPU_seconds': cpu,
                'peak_memory_bytes': peak}}), budget)
            with self.assertRaises(ValueError):
                d.inspect_closed(c.ClosedRun(artifact, life, c._CLOSED_TOKEN), c, C, root, budget)

    def test_failure_is_preserved_and_no_candidate_dispatch(self):
        output = self.root / 'op'; req = request(output); c = M['participant_container']
        with patch.object(d, 'preflight', side_effect=ValueError('generated missing delegation')), \
             patch.object(c, 'run_candidate', side_effect=AssertionError('must not dispatch')):
            result = d.operate(req, 'run', output, M, BODIES, d.digest(SOURCE), time.monotonic())
        self.assertEqual(result['status'], 'refused')
        self.assertEqual(result['failure']['message'], 'generated missing delegation')
        self.assertTrue((output/'REQUEST.json').is_file()); self.assertTrue((output/'REPORT.json').is_file())
        self.assertFalse((output/'run').exists())

    def test_static_cli_template_refuses_before_output(self):
        reqpath = HERE/'REQUEST.template.json'
        run = subprocess.run([sys.executable, '-I', '-B', str(HERE/'diagnostic.py'), 'check',
            '--source-sha256', d.digest(SOURCE), '--request', str(reqpath),
            '--request-sha256', d.digest(reqpath.read_bytes()), '--output', str(self.root/'no-create')],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5, check=False)
        self.assertEqual(run.returncode, 2); self.assertEqual(run.stderr, b'')
        self.assertIn('explicit operation selection', json.loads(run.stdout)['message'])
        self.assertFalse((self.root/'no-create').exists())

    def test_selected_preflight_cancellation_cleanup_restoration(self):
        c = M['participant_container']; output = self.root/'op'; req = request(output)
        signals = (d.signal.SIGTERM, d.signal.SIGINT)
        previous = {s: d.signal.getsignal(s) for s in signals}
        live = []; observed = []
        def preflight(*args):
            live.append(12345)  # invented registry only, never an actual PID lookup
            d.signal.getsignal(d.signal.SIGTERM)(d.signal.SIGTERM, None)
        def cleanup(until):
            observed.append([d.signal.getsignal(s) for s in signals])
            live.clear()
            return [{'generated': True, 'reaped': True, 'group_absent': True}]
        with patch.object(d, 'preflight', side_effect=preflight), \
             patch.object(c, 'registered_clients', side_effect=lambda:tuple(live)), \
             patch.object(c, 'cleanup_registered_clients', side_effect=cleanup), \
             patch.object(c, 'run_candidate', side_effect=AssertionError('must not dispatch')):
            result = d.operate(req, 'run', output, M, BODIES, d.digest(SOURCE), time.monotonic())
        self.assertEqual(result['status'], 'refused')
        self.assertIn('cancelled by signal', result['failure']['message'])
        self.assertEqual(result['remaining_client_records'], [])
        self.assertEqual(observed, [[d.signal.SIG_IGN, d.signal.SIG_IGN]])
        self.assertEqual({s:d.signal.getsignal(s) for s in signals}, previous)
        self.assertTrue((output/'REPORT.json').is_file())

    def test_guarded_check_valid_restores_handlers(self):
        c = M['participant_container']; output = self.root/'op'; req = request(output)
        req['selection']['mode'] = 'check'
        signals = (d.signal.SIGTERM, d.signal.SIGINT)
        previous = {s:d.signal.getsignal(s) for s in signals}
        with patch.object(d, 'preflight', return_value=None), \
             patch.object(c, 'run_candidate', side_effect=AssertionError('must not dispatch')):
            result = d.operate(req, 'check', output, M, BODIES, d.digest(SOURCE), time.monotonic())
        self.assertEqual(result['status'], 'conditional_prerequisites_observed')
        self.assertEqual({s:d.signal.getsignal(s) for s in signals}, previous)

    def test_guard_install_and_restore_failures_attempt_both(self):
        signals = (d.signal.SIGTERM, d.signal.SIGINT)
        old = {s: object() for s in signals}
        for failure_mode in ('second_install', 'first_restore'):
            calls = []; state = dict(old)
            def setter(signum, handler):
                calls.append((signum, handler))
                if failure_mode == 'second_install' and signum == signals[1] and callable(handler):
                    raise OSError('invented installation failure')
                if failure_mode == 'first_restore' and signum == signals[0] and handler is old[signum]:
                    raise OSError('invented restoration failure')
                state[signum] = handler
            action = patch.object(d, '_operate', return_value={'generated': True})
            with patch.object(d.signal, 'getsignal', side_effect=lambda s:state[s]), \
                 patch.object(d.signal, 'signal', side_effect=setter), action as body:
                with self.assertRaises(OSError):
                    d.operate({}, 'check', self.root/'none', M, BODIES, d.digest(SOURCE), time.monotonic())
            self.assertEqual([s for s,h in calls if h is old[s]], list(signals))
            if failure_mode == 'second_install': body.assert_not_called()
            else: body.assert_called_once()


if __name__ == '__main__':
    unittest.main()
