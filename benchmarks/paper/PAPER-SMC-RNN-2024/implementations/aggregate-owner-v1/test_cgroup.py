"""Generated source controls only; no cgroups, processes or Docker are exercised.

Real private temporary metadata and directory FDs are used. Every kernel
observation/mutation boundary is mocked; passing these tests cannot qualify
Linux behavior, a runtime image, CPU overshoot or scientific readiness.
"""
from contextlib import ExitStack
import importlib.util
import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('smc_generated_cgroup_source', HERE / 'cgroup.py')
cg = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cg)
FIXTURE_BYTES = 0


def charge_fixture(raw):
    # Charge attempts before writing; deletion never refunds the shared budget.
    global FIXTURE_BYTES
    FIXTURE_BYTES += len(raw)
    if FIXTURE_BYTES > 224 * 1024:
        raise AssertionError('cumulative generated JSON fixture budget exceeded')


class Writer:
    def __init__(self):
        self.published = []

    def publish(self, path, value, *, terminal=False):
        raw = cg.encoded(value)
        charge_fixture(raw)
        with Path(path).open('xb') as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        fd = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self.published.append((Path(path).name, terminal, json.loads(raw)))
        return cg.pin(raw)


class Kernel:
    """A memory-only kernel interface; it cannot access the selected /sys path."""
    def __init__(self):
        self.values = {}
        self.writes = []
        self.kill_hook = None
        self.fail_setting = None

    def key(self, fd):
        observed = os.fstat(fd)
        return (observed.st_dev, observed.st_ino)

    def state(self, fd):
        return self.values.setdefault(self.key(fd), {
            'cgroup.controllers': 'cpu memory pids\n',
            'cgroup.subtree_control': '',
            'cgroup.procs': '',
            'cgroup.type': 'domain\n',
            'cgroup.events': 'populated 0\nfrozen 0\n',
            'cpu.stat': 'usage_usec 0\nuser_usec 0\nsystem_usec 0\n',
            'memory.peak': '0\n',
            'memory.events': 'low 0\nhigh 0\nmax 0\noom 0\noom_kill 0\n',
            'pids.events': 'max 0\n',
        })

    def read(self, fd, name, cap=8192):
        value = self.state(fd)[name]
        if len(value.encode()) > cap:
            raise ValueError('generated kernel interface exceeds requested cap')
        return value

    def write(self, fd, name, value):
        if name == self.fail_setting:
            raise OSError('generated setting failure')
        self.writes.append((self.key(fd), name, value))
        state = self.state(fd)
        if name == 'cgroup.kill':
            if self.kill_hook is not None:
                self.kill_hook()
            state['cgroup.events'] = 'populated 0\nfrozen 0\n'
        elif name == 'cgroup.subtree_control':
            state[name] = ' '.join(part.removeprefix('+') for part in value.split()) + '\n'
        else:
            state[name] = value + '\n'


class ScopeControls(unittest.TestCase):
    def setUp(self):
        # Avoid /var -> /private/var aliases: production path checks remain real.
        self.temp = tempfile.TemporaryDirectory(prefix='.generated-cgroup-', dir=HERE)
        self.base = Path(self.temp.name)
        self.folder = self.base / 'owner'
        self.folder.mkdir(mode=0o700)
        (self.folder / 'events').mkdir(mode=0o700)
        (self.folder / 'process').mkdir(mode=0o700)
        self.kernel_root = self.base / 'generated-delegation'
        self.kernel_root.mkdir(mode=0o700)
        self.kernel = Kernel()
        self.writer = Writer()
        self.now = 110.0
        self.clock = {'outcome': 'improvement', 'origin': 100.0,
                      'controller_deadline': 200.0, 'deadline': 210.0,
                      'clock_identity': 'linux:01234567-89ab-cdef-0123-456789abcdef'}
        self.source = cg.pin(b'generated parent source\n')
        self.deployment = {
            'image': 'sha256:' + '1' * 64, 'docker_binary': '/generated/docker',
            'docker_socket': '/generated/docker.sock',
            'boot_id': '01234567-89ab-cdef-0123-456789abcdef',
            'delegation': {'path': '/sys/fs/cgroup/generated-smc-tests',
                           'st_dev': self.kernel_root.stat().st_dev,
                           'st_ino': self.kernel_root.stat().st_ino,
                           'uid': os.geteuid(), 'mount_id': 77,
                           'mount_point': '/sys/fs/cgroup', 'mount_root': '/',
                           'fs_type': 'cgroup2'},
            'pid_limit': 32, 'qualification': cg.pin(b'generated qualification\n'),
            'binding_pin': cg.pin(b'generated deployment binding\n'),
            'resource_policy': 'measured_caps_and_oom_kill_v1',
            'cgroup_driver': 'cgroupfs',
        }
        self.invocation_pin = self.save('INVOCATION.json', {'source': self.source, 'clock': self.clock})
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(cg.time, 'monotonic', side_effect=lambda: self.now))
        self.stack.enter_context(patch.object(cg.time, 'sleep', side_effect=self.sleep))
        self.stack.enter_context(patch.object(cg, '_magic', return_value=cg.CGROUP_MAGIC))
        self.stack.enter_context(patch.object(cg, '_read_kernel', side_effect=self.kernel.read))
        self.stack.enter_context(patch.object(cg, '_write_kernel', side_effect=self.kernel.write))
        self.stack.enter_context(patch.object(cg, '_pidfd_live', return_value=False))
        self.stack.enter_context(patch.object(cg, '_original_owner',
                                             side_effect=lambda folder: cg._file(folder / 'process/process_owner.json')))
        generated_root = self.kernel_root

        def generated_host(manager):
            manager._tick(closing=True)
            if manager.root_fd is None:
                manager.root_fd = os.open(generated_root, os.O_RDONLY | os.O_DIRECTORY)

        self.stack.enter_context(patch.object(cg.ScopeManager, '_host', generated_host))
        self.manager = cg.ScopeManager(self.deployment, self.clock, self.invocation_pin,
                                       self.source, self.writer, self.folder)
        self.event_index = 0

    def tearDown(self):
        # Only close generated regular-directory FDs retained by these controls.
        seen = set()
        for scope in self.manager.scopes.values():
            for key in ('fd', 'pidfd'):
                fd = scope.get(key)
                if type(fd) is int and fd not in seen:
                    seen.add(fd)
                    try:
                        os.close(fd)
                    except OSError:
                        pass
        if self.manager.root_fd is not None and self.manager.root_fd not in seen:
            try:
                os.close(self.manager.root_fd)
            except OSError:
                pass
        self.stack.close()
        self.temp.cleanup()

    def sleep(self, seconds):
        self.now += seconds

    def save(self, relative, value):
        path = self.folder / relative
        raw = cg.encoded(value)
        charge_fixture(raw)
        path.write_bytes(raw)
        return cg.pin(raw)

    def proposal(self, phase=None):
        phase = phase or cg.PHASES[0]
        name = 'smc-' + 'a' * 32 + ('-a' if phase == cg.PHASES[0] else '-b')
        plan = {'schema': 'smc_cgroup_plan_v1', 'phase_id': phase, 'name': name,
                'parent': self.deployment['delegation']['path'],
                'path': self.deployment['delegation']['path'] + '/' + name,
                'cgroup_parent': '/generated-smc-tests/' + name,
                'deployment_pin': self.deployment['binding_pin'],
                'invocation_pin': self.invocation_pin}
        # Full transport ABI; the CPU cutoff stays synthetic for source controls.
        limits = {'cpu_seconds': 10, 'memory_bytes': 8 * 1024**3,
                  'cpu_nanos': 6000000000, 'pids': 32,
                  'setup_seconds': 60, 'producer_seconds': 10800, 'capture_seconds': 300,
                  'cleanup_seconds': 60, 'scratch_bytes': 512 * 1024**2,
                  'max_files': 4, 'max_directories': 1, 'max_file_bytes': 512 * 1024**2,
                  'max_output_bytes': 1024**3 + 4096, 'manifest_bytes': 65536,
                  'max_cli_calls': 256, 'max_cli_bytes': 8 * 1024**2,
                  'inventory_bytes': 65536, 'source_read_bytes': 1024**2,
                  'host_write_bytes': 1024**2}
        request_pin = cg.pin(cg.encoded({'phase': phase, 'plan': plan, 'limits': limits}))
        return phase, plan, limits, request_pin

    def intent(self, phase, plan, limits, request_pin, *, source=None):
        index = self.event_index
        self.event_index += 1
        record = {'schema': 'smc_aggregate_transport_journal_v1', 'phase_id': phase,
                  'request_sha256': request_pin['sha256'], 'index': index,
                  'event': 'CGROUP-INTENT', 'value': {'plan': plan, 'limits': limits}}
        value = {'schema': 'smc_aggregate_owner_event_v1',
                 'owner_source': self.source if source is None else source,
                 'invocation_pin': self.invocation_pin,
                 'message': {'event': 'CGROUP-INTENT',
                             'value': {'record': record, 'pin': cg.pin(cg.encoded(record))}}}
        relative = 'events/EVENT-' + str(index) + '.json'
        return {'path': str(self.folder / relative), **self.save(relative, value)}

    def prepare(self):
        phase, plan, limits, request_pin = self.proposal()
        ref = self.intent(phase, plan, limits, request_pin)
        ack = self.manager.prepare(phase, plan, limits, intent_ref=ref, request_pin=request_pin)
        return phase, self.manager.scopes[phase], ack

    def counters(self, scope, *, cpu=0, peak=0, populated=0, memory_failure=False, pids_failure=False):
        state = self.kernel.state(scope['fd'])
        state.update({'cpu.stat': f'usage_usec {cpu}\nuser_usec {cpu}\nsystem_usec 0\n',
                      'memory.peak': str(peak) + '\n',
                      'cgroup.events': f'populated {populated}\nfrozen 0\n',
                      'memory.events': f'low 0\nhigh 0\nmax {int(memory_failure)}\noom 0\noom_kill 0\n',
                      'pids.events': f'max {int(pids_failure)}\n'})

    def original_owner(self):
        return self.save('process/process_owner.json', {
            'grant': {**self.clock, 'invocation_pin': self.invocation_pin}, 'pid': 60000, 'pgid': 60000})

    def closure(self):
        self.original_owner()
        document = {'schema': 'smc_parent_observed_controller_closure_v1',
                    'invocation_pin': self.invocation_pin, 'source': self.source, 'clock': self.clock,
                    'controller_group': {'absence_verified': True, 'pgid': 60000},
                    'acknowledged_cli': {'all_acknowledged_cli_absent': True},
                    'future_controller_and_acknowledged_cli_release_closed': True}
        return self.save('CONTROLLER_CLOSED.json', document)

    def attach(self, phase, *, births=None, live=True):
        scope = self.manager.scopes[phase]
        cid = 'c' * 64
        event = {'pid': 50000, 'container_id': cid, 'cgroup_parent': scope['plan']['cgroup_parent']}
        membership = '/' + str(Path(scope['plan']['path']).relative_to('/sys/fs/cgroup')) + '/' + cid
        birth = {'pid': event['pid'], 'start_ticks': 12345, 'cgroup': membership,
                 'namespaces': {'pid': 10, 'mnt': 11, 'cgroup': 12}}
        with ExitStack() as stack:
            stack.enter_context(patch.object(cg.os, 'pidfd_open', create=True,
                                             side_effect=lambda *args: os.dup(self.manager.root_fd)))
            stack.enter_context(patch.object(cg, '_process_birth', side_effect=births or [birth, birth]))
            stack.enter_context(patch.object(cg, '_pidfd_live', return_value=live))
            stack.enter_context(patch.object(cg, '_self_namespaces', return_value={'pid': 1, 'mnt': 1, 'cgroup': 1}))
            return self.manager.attach(phase, event)

    def provider_closure(self, phase, closure_pin, *, request=None):
        scope = self.manager.scopes[phase]
        ownership_pin = cg.pin(b'generated exact Provider ownership\n')
        receipt = {'schema': 'smc_aggregate_phase_receipt_v1', 'phase_id': phase,
                   'request_sha256': (request or scope['request_pin'])['sha256'],
                   'ownership_pin': ownership_pin, 'all_native_resources_closed': True, 'cli_reaped': True}
        receipt_pin = self.save('PROVIDER-PHASE.json', receipt)
        document = {'schema': 'smc_aggregate_provider_closure_v1',
                    'invocation_pin': self.invocation_pin, 'source': self.source, 'clock': self.clock,
                    'controller_closure_pin': closure_pin, 'recovery_cli_absent': True,
                    'phases': {phase: {'request_pin': scope['request_pin'], 'ownership_pin': ownership_pin,
                                       'producer_container_id': None if scope['producer'] is None else scope['producer']['event']['container_id'],
                                       'receipt_path': str(self.folder / 'PROVIDER-PHASE.json'),
                                       'receipt_pin': receipt_pin, 'all_resources_closed': True}}}
        return self.save('PROVIDER_CLOSED.json', document)

    def test_constructor_rejects_clock_from_different_deployment_boot(self):
        deployment = {**self.deployment, 'boot_id': 'ffffffff-ffff-ffff-ffff-ffffffffffff'}
        with self.assertRaisesRegex(ValueError, 'same-boot original monotonic clock'):
            cg.ScopeManager(deployment, self.clock, self.invocation_pin,
                            self.source, self.writer, self.folder)

    def test_prepare_requires_matching_durable_intent_before_creation(self):
        phase, plan, limits, request = self.proposal()
        missing = {'path': str(self.folder / 'events/EVENT-99.json'), **cg.pin(b'missing\n')}
        with self.assertRaises(FileNotFoundError):
            self.manager.prepare(phase, plan, limits, intent_ref=missing, request_pin=request)
        wrong = self.intent(phase, plan, limits, request, source=cg.pin(b'wrong source\n'))
        with self.assertRaisesRegex(ValueError, 'persisted parent cgroup intent'):
            self.manager.prepare(phase, plan, limits, intent_ref=wrong, request_pin=request)
        self.assertEqual(list(self.kernel_root.iterdir()), [])
        self.assertEqual(self.kernel.writes, [])

    def test_prepare_rejects_changed_request_before_creation(self):
        phase, plan, limits, request = self.proposal()
        intent = self.intent(phase, plan, limits, request)
        with self.assertRaisesRegex(ValueError, 'exact request/source/limits intent'):
            self.manager.prepare(phase, plan, limits, intent_ref=intent, request_pin=cg.pin(b'other request\n'))
        self.assertEqual(list(self.kernel_root.iterdir()), [])
        malformed = [dict(limits), dict(limits), dict(limits)]
        malformed[0].pop('host_write_bytes')
        malformed[1]['unexpected'] = 1
        malformed[2]['host_write_bytes'] = True
        for bad in malformed:
            request = cg.pin(cg.encoded({'phase': phase, 'plan': plan, 'limits': bad}))
            intent = self.intent(phase, plan, bad, request)
            with self.subTest(keys=sorted(bad), host_write=bad.get('host_write_bytes')), \
                    self.assertRaisesRegex(ValueError, 'exact complete positive-integer transport resource bounds'):
                self.manager.prepare(phase, plan, bad, intent_ref=intent, request_pin=request)
            self.assertEqual(list(self.kernel_root.iterdir()), [])
            self.assertEqual(self.kernel.writes, [])
        self.assertEqual(self.manager.scopes, {})

    def test_prepare_persists_exact_ownership_and_limit_readback_before_ack(self):
        phase, scope, ack = self.prepare()
        record_path = self.folder / ('CGROUP-' + phase + '-OWNER.json')
        owner = cg._file(record_path, ack['owner_pin'])
        self.assertEqual(owner['request_pin'], scope['request_pin'])
        self.assertEqual(owner['limits'], self.proposal(phase)[2])
        self.assertEqual(len(owner['limits']), 19)
        self.assertEqual(owner['clock'], self.clock)
        self.assertEqual(owner['source'], self.source)
        self.assertEqual(owner['deployment_pin'], self.deployment['binding_pin'])
        self.assertEqual(self.writer.published[-1][0], record_path.name)
        self.assertEqual(stat.S_IMODE(os.fstat(scope['fd']).st_mode), 0o700)
        values = self.kernel.state(scope['fd'])
        self.assertEqual(values['memory.max'], str(8 * 1024**3) + '\n')
        self.assertEqual(values['memory.swap.max'], '0\n')
        self.assertEqual(values['pids.max'], '32\n')
        self.assertEqual(values['cpu.max'], '600000 100000\n')
        self.assertEqual(set(values['cgroup.subtree_control'].split()), cg.CONTROLLERS)
        self.assertEqual(owner['initial']['counters']['cpu_usage_usec'], 0)

    def test_failed_limit_configuration_retains_owned_scope_without_ack(self):
        self.kernel.fail_setting = 'memory.swap.max'
        with self.assertRaisesRegex(OSError, 'generated setting failure'):
            self.prepare()
        scope = self.manager.scopes[cg.PHASES[0]]
        self.assertIsNone(scope['owner_pin'])
        self.assertEqual(len(list(self.kernel_root.iterdir())), 1)
        self.assertEqual(self.writer.published, [])
        self.assertNotIn('cgroup.kill', [row[1] for row in self.kernel.writes])

    def test_open_failure_after_mkdir_preserves_unknown_scope_without_false_closure(self):
        phase, plan, limits, request = self.proposal()
        intent = self.intent(phase, plan, limits, request)
        original_open = os.open

        def selective_open(path, *args, **kwargs):
            if path == plan['name'] and kwargs.get('dir_fd') == self.manager.root_fd:
                raise OSError('generated open-after-mkdir failure')
            return original_open(path, *args, **kwargs)

        with patch.object(cg.os, 'open', side_effect=selective_open):
            with self.assertRaisesRegex(OSError, 'open-after-mkdir failure'):
                self.manager.prepare(phase, plan, limits, intent_ref=intent, request_pin=request)
        self.assertTrue((self.kernel_root / plan['name']).is_dir())
        self.assertIsNone(self.manager.scopes[phase]['fd'])
        with patch.object(cg, '_group_absent', return_value=True):
            result = self.manager.close(self.closure())
        self.assertFalse(result['complete'])
        self.assertFalse(result['all_scopes_empty'])
        self.assertIsNone(result['scopes'][phase]['counters'])
        self.assertNotIn('cgroup.kill', [row[1] for row in self.kernel.writes])

    def test_fresh_nonzero_memory_history_cannot_be_subtracted_away(self):
        original_state = self.kernel.state

        def historical_state(fd):
            value = original_state(fd)
            value['memory.peak'] = '1\n'
            return value

        with patch.object(self.kernel, 'state', side_effect=historical_state):
            with self.assertRaisesRegex(ValueError, 'fresh unexplained CPU/memory/PID history'):
                self.prepare()
        self.assertIsNone(self.manager.scopes[cg.PHASES[0]]['owner_pin'])

    def test_scope_inode_substitution_is_rejected(self):
        _, scope, _ = self.prepare()
        original = self.kernel_root / scope['plan']['name']
        original.rename(self.kernel_root / 'preserved-original')
        original.mkdir(mode=0o700)
        with self.assertRaisesRegex(ValueError, 'same private original scope inode'):
            self.manager._scope_identity(scope)

    def test_symlinked_owner_event_directory_is_rejected(self):
        phase, plan, limits, request = self.proposal()
        intent = self.intent(phase, plan, limits, request)
        events = self.folder / 'events'
        events.rename(self.folder / 'original-events')
        events.symlink_to(self.folder / 'original-events', target_is_directory=True)
        with self.assertRaises(OSError):
            self.manager.prepare(phase, plan, limits, intent_ref=intent, request_pin=request)
        self.assertEqual(self.kernel.writes, [])

    def test_attach_rejects_dead_or_escaped_producer_before_ack(self):
        phase, scope, _ = self.prepare()
        with self.assertRaisesRegex(ValueError, 'live original producer pidfd'):
            self.attach(phase, live=False)
        escaped = {'pid': 50000, 'start_ticks': 12345, 'cgroup': '/unrelated/container',
                   'namespaces': {'pid': 10, 'mnt': 11, 'cgroup': 12}}
        with self.assertRaisesRegex(ValueError, 'same producer birth'):
            self.attach(phase, births=[escaped, escaped])
        self.assertIsNone(scope['producer'])
        self.assertFalse((self.folder / ('CGROUP-' + phase + '-ATTACHED.json')).exists())

    def test_attach_persists_real_metadata_join_for_mocked_birth(self):
        phase, scope, _ = self.prepare()
        attached = self.attach(phase)
        saved = cg._file(self.folder / ('CGROUP-' + phase + '-ATTACHED.json'), attached['attachment_pin'])
        self.assertEqual(saved['request_pin'], scope['request_pin'])
        self.assertEqual(saved['owner_pin'], scope['owner_pin'])
        self.assertEqual(saved['invocation_pin'], self.invocation_pin)
        self.assertEqual(saved['birth']['start_ticks'], 12345)
        self.assertIsNotNone(scope['pidfd'])

    def test_poll_retains_cpu_memory_violations_without_killing_live_controller(self):
        phase, scope, _ = self.prepare()
        self.counters(scope, cpu=10000001, peak=8 * 1024**3 + 1, populated=1,
                      memory_failure=True, pids_failure=True)
        with self.assertRaises(cg.ScopeViolation) as failure:
            self.manager.poll()
        observed = failure.exception.evidence['scopes'][phase]
        self.assertEqual(set(observed['violations']),
                         {'aggregate_cpu_limit', 'aggregate_memory_limit'})
        self.assertEqual(observed['counters']['cpu_usage_usec'], 10000001)
        self.assertFalse(observed['zero_cpu_overshoot_claim'])
        self.assertTrue((self.folder / 'CGROUP-VIOLATION.json').exists())
        self.assertNotIn('cgroup.kill', [row[1] for row in self.kernel.writes])

    def test_handled_denials_are_retained_but_oom_kill_fails(self):
        phase, scope, _ = self.prepare()
        self.counters(scope, cpu=100, peak=1000, memory_failure=True, pids_failure=True)
        state = self.kernel.state(scope['fd'])
        state['memory.events'] = 'low 0\nhigh 0\nmax 1\noom 1\noom_kill 0\n'
        observed = self.manager.poll()['scopes'][phase]
        self.assertTrue(observed['within_limits'])
        self.assertEqual(observed['counters']['memory_events']['oom'], 1)
        self.assertEqual(observed['counters']['pids_events']['max'], 1)
        state['memory.events'] = 'low 0\nhigh 0\nmax 1\noom 1\noom_kill 1\n'
        with self.assertRaises(cg.ScopeViolation) as failure:
            self.manager.poll()
        self.assertEqual(failure.exception.evidence['scopes'][phase]['violations'], ['aggregate_memory_limit'])
        self.assertNotIn('cgroup.kill', [row[1] for row in self.kernel.writes])

    def test_poll_original_controller_deadline_never_becomes_new_interval(self):
        _, scope, _ = self.prepare()
        self.counters(scope, cpu=1)
        self.now = self.clock['controller_deadline']
        with self.assertRaises(cg.ScopeViolation):
            self.manager.poll()
        self.assertEqual(self.manager.clock, self.clock)
        self.assertNotIn('cgroup.kill', [row[1] for row in self.kernel.writes])

    def test_finish_retains_nonempty_failure_and_does_not_accept_phase(self):
        phase, scope, _ = self.prepare()
        self.attach(phase)
        self.counters(scope, cpu=123, populated=1)
        with self.assertRaisesRegex(ValueError, 'closed within-limit hierarchy'):
            self.manager.finish(phase)
        saved = cg._file(self.folder / ('CGROUP-' + phase + '-FINISHED.json'))
        self.assertFalse(saved['empty'])
        self.assertEqual(saved['counters']['cpu_usage_usec'], 123)
        self.assertFalse(scope['finished'])

    def test_finish_reads_final_counters_after_live_to_empty_transition(self):
        phase, scope, _ = self.prepare()
        self.attach(phase)
        events = iter(['populated 1\nfrozen 0\n', 'populated 0\nfrozen 0\n',
                       'populated 0\nfrozen 0\n', 'populated 0\nfrozen 0\n'])
        usages = iter([100, 200])

        def transition(fd, name, cap=8192):
            if name == 'cgroup.events':
                return next(events)
            if name == 'cpu.stat':
                value = next(usages)
                return f'usage_usec {value}\nuser_usec {value}\nsystem_usec 0\n'
            return self.kernel.read(fd, name, cap)

        with patch.object(cg, '_read_kernel', side_effect=transition):
            finished = self.manager.finish(phase)
        self.assertTrue(finished['empty'])
        self.assertEqual(finished['counters']['cpu_usage_usec'], 200)
        self.assertEqual(finished['counters']['cgroup_events_before']['populated'], 0)

    def test_close_refuses_bad_pin_or_live_controller_before_group_kill(self):
        _, scope, _ = self.prepare()
        self.counters(scope, populated=1)
        closure_pin = self.closure()
        with patch.object(cg, '_group_absent', return_value=True):
            with self.assertRaisesRegex(ValueError, 'exact owner metadata pin'):
                self.manager.close(cg.pin(b'not the closure\n'))
        with patch.object(cg, '_group_absent', return_value=False):
            with self.assertRaisesRegex(ValueError, 'observed original controller group remains absent'):
                self.manager.close(closure_pin)
        self.assertNotIn('cgroup.kill', [row[1] for row in self.kernel.writes])

    def test_close_kills_only_after_gate_and_retains_overcap_cost(self):
        phase, scope, _ = self.prepare()
        self.counters(scope, cpu=10000001, populated=1)
        closure_pin = self.closure()
        calls = []
        with patch.object(cg, '_group_absent', side_effect=lambda group: calls.append(group) or True):
            self.kernel.kill_hook = lambda: self.assertGreaterEqual(len(calls), 2)
            result = self.manager.close(closure_pin)
        self.assertTrue(result['complete'])
        self.assertTrue(result['all_scopes_empty'])
        self.assertFalse(result['within_limits'])
        self.assertEqual(result['scopes'][phase]['counters']['cpu_usage_usec'], 10000001)
        self.assertEqual([row[1] for row in self.kernel.writes].count('cgroup.kill'), 1)
        self.assertTrue((self.kernel_root / scope['plan']['name']).exists())

    def test_expired_close_preserves_last_observation_as_unknown_final_cost(self):
        phase, scope, _ = self.prepare()
        self.counters(scope, cpu=99, populated=1)
        self.manager.poll()
        closure_pin = self.closure()
        self.now = self.clock['deadline']
        with patch.object(cg, '_group_absent', return_value=True):
            result = self.manager.close(closure_pin)
        self.assertFalse(result['complete'])
        self.assertFalse(result['counters_complete'])
        self.assertIsNone(result['scopes'][phase]['counters'])
        self.assertEqual(result['scopes'][phase]['last_known_observation']['counters']['cpu_usage_usec'], 99)
        self.assertNotIn('cgroup.kill', [row[1] for row in self.kernel.writes])
        self.assertEqual(self.manager.clock['deadline'], 210.0)

    def test_remove_requires_matching_actual_provider_receipt(self):
        phase, scope, _ = self.prepare()
        closure_pin = self.closure()
        with patch.object(cg, '_group_absent', return_value=True):
            self.manager.close(closure_pin)
            bad = self.provider_closure(phase, closure_pin, request=cg.pin(b'other request\n'))
            with self.assertRaisesRegex(ValueError, 'actual normal Provider resource closure'):
                self.manager.remove(bad)
        self.assertTrue((self.kernel_root / scope['plan']['name']).exists())
        self.assertFalse(scope['removed'])

    def test_remove_rejects_reused_scope_inode_after_provider_closure(self):
        phase, scope, _ = self.prepare()
        closure_pin = self.closure()
        with patch.object(cg, '_group_absent', return_value=True):
            self.manager.close(closure_pin)
            provider_pin = self.provider_closure(phase, closure_pin)
            original = self.kernel_root / scope['plan']['name']
            original.rename(self.kernel_root / 'preserved-original')
            original.mkdir(mode=0o700)
            removed = self.manager.remove(provider_pin)
        self.assertFalse(removed['complete'])
        self.assertFalse(removed['all_scopes_removed'])
        self.assertTrue(original.is_dir())
        self.assertTrue((self.kernel_root / 'preserved-original').is_dir())

    def test_remove_occurs_only_after_closed_counters_and_provider_receipt(self):
        phase, scope, _ = self.prepare()
        self.attach(phase)
        self.counters(scope, cpu=100, peak=1000)
        finished = self.manager.finish(phase)
        self.assertTrue(finished['empty'])
        self.assertTrue((self.kernel_root / scope['plan']['name']).exists())
        with self.assertRaisesRegex(ValueError, 'closed counters retained before provider recovery'):
            self.manager.remove(cg.pin(b'not yet produced\n'))
        closure_pin = self.closure()
        with patch.object(cg, '_group_absent', return_value=True):
            self.manager.close(closure_pin)
            with self.assertRaises(FileNotFoundError):
                self.manager.remove(cg.pin(b'missing provider record\n'))
            provider_pin = self.provider_closure(phase, closure_pin)
            removed = self.manager.remove(provider_pin)
        self.assertTrue(removed['complete'])
        self.assertTrue(removed['all_scopes_removed'])
        self.assertFalse((self.kernel_root / scope['plan']['name']).exists())
        self.assertTrue((self.folder / ('CGROUP-' + phase + '-CLOSED.json')).exists())

    def test_remove_refuses_late_aggregate_cost_even_after_provider_closure(self):
        phase, scope, _ = self.prepare()
        self.counters(scope, cpu=100)
        closure_pin = self.closure()
        with patch.object(cg, '_group_absent', return_value=True):
            self.manager.close(closure_pin)
            provider_pin = self.provider_closure(phase, closure_pin)
            self.counters(scope, cpu=101)
            removed = self.manager.remove(provider_pin)
        self.assertFalse(removed['complete'])
        self.assertTrue((self.kernel_root / scope['plan']['name']).exists())
        self.assertIn('no late aggregate cost', removed['errors'][0]['message'])

    def test_emergency_live_original_group_refuses_scope_stop(self):
        phase, scope, _ = self.prepare()
        self.counters(scope, cpu=10, populated=1)
        self.original_owner()
        with patch.object(cg, '_group_absent', return_value=False), \
                patch.object(cg, '_close_original_custody') as custody:
            result = self.manager.emergency_close(object())
        custody.assert_not_called()
        self.assertFalse(result['cleanup_complete'])
        self.assertIsNone(result['scopes'][phase]['final_observation'])
        self.assertNotIn('cgroup.kill', [row[1] for row in self.kernel.writes])
        self.assertTrue((self.kernel_root / scope['plan']['name']).is_dir())

    def test_emergency_custody_exception_refuses_scope_stop(self):
        phase, scope, _ = self.prepare()
        self.counters(scope, populated=1)
        self.original_owner()
        with patch.object(cg, '_group_absent', return_value=True), \
                patch.object(cg, '_close_original_custody', side_effect=ValueError('generated custody failure')):
            result = self.manager.emergency_close(object())
        self.assertFalse(result['cleanup_complete'])
        self.assertIsNone(result['scopes'][phase]['final_observation'])
        self.assertEqual(result['errors'][0]['message'], 'generated custody failure')
        self.assertNotIn('cgroup.kill', [row[1] for row in self.kernel.writes])

    def test_emergency_custody_nonabsence_refuses_scope_stop(self):
        phase, scope, _ = self.prepare()
        self.counters(scope, populated=1)
        self.original_owner()
        original_custody = object()
        with patch.object(cg, '_group_absent', return_value=True), \
                patch.object(cg, '_close_original_custody',
                             return_value={'all_acknowledged_cli_absent': False}) as custody:
            result = self.manager.emergency_close(original_custody)
        custody.assert_called_once_with(original_custody, self.clock['deadline'])
        self.assertFalse(result['cleanup_complete'])
        self.assertIsNone(result['scopes'][phase]['final_observation'])
        self.assertNotIn('cgroup.kill', [row[1] for row in self.kernel.writes])

    def test_emergency_success_preserves_cost_without_grade_or_provider_or_removal(self):
        phase, scope, _ = self.prepare()
        self.counters(scope, cpu=10000001, populated=1)
        self.original_owner()
        gates = []
        original_custody = object()

        def close_custody(custody, deadline):
            self.assertIs(custody, original_custody)
            self.assertEqual(deadline, self.clock['deadline'])
            self.assertEqual(gates, ['group'])
            gates.append('custody')
            return {'all_acknowledged_cli_absent': True}

        self.kernel.kill_hook = lambda: self.assertEqual(gates, ['group', 'custody', 'group', 'group'])
        with patch.object(cg, '_group_absent', side_effect=lambda group: gates.append('group') or True), \
                patch.object(cg, '_close_original_custody', side_effect=close_custody):
            result = self.manager.emergency_close(original_custody)
        self.assertTrue(result['cleanup_complete'])
        self.assertEqual(result['scopes'][phase]['final_observation']['counters']['cpu_usage_usec'], 10000001)
        self.assertFalse(result['scopes'][phase]['final_observation']['within_limits'])
        for key in ('complete', 'gradeable', 'qualified', 'provider_recovery_attempted', 'scope_removal_attempted'):
            self.assertIs(result[key], False)
        self.assertFalse((self.folder / 'CONTROLLER_CLOSED.json').exists())
        self.assertFalse((self.folder / 'PROVIDER_CLOSED.json').exists())
        self.assertTrue((self.kernel_root / scope['plan']['name']).is_dir())
        self.assertIsNone(self.manager.closed)
        with self.assertRaisesRegex(ValueError, 'after emergency'):
            self.manager.remove(cg.pin(b'no provider proof\n'))
        with self.assertRaisesRegex(ValueError, 'one retained emergency attempt'):
            self.manager.emergency_close(original_custody)

    def test_emergency_retains_unknown_identity_and_closes_only_observed_descriptor(self):
        with patch.object(cg, '_identity', side_effect=OSError('generated first identity failure')):
            with self.assertRaisesRegex(OSError, 'first identity failure'):
                self.prepare()
        phase = cg.PHASES[0]
        scope = self.manager.scopes[phase]
        retained_fd = scope['fd']
        self.assertIsInstance(retained_fd, int)
        os.fstat(retained_fd)
        self.assertIsNone(scope['identity'])
        self.assertEqual(self.kernel.writes, [])
        self.original_owner()
        with patch.object(cg, '_group_absent', return_value=True), \
                patch.object(cg, '_close_original_custody',
                             return_value={'all_acknowledged_cli_absent': True}):
            result = self.manager.emergency_close(object())
        self.assertFalse(result['cleanup_complete'])
        self.assertIsNone(result['scopes'][phase]['final_observation'])
        self.assertIsNone(result['scopes'][phase]['last_known_observation'])
        self.assertIsNone(scope['fd'])
        with self.assertRaises(OSError):
            os.fstat(retained_fd)
        self.assertEqual(self.kernel.writes, [])
        self.assertTrue((self.kernel_root / scope['plan']['name']).is_dir())


if __name__ == '__main__':
    suite = unittest.main(verbosity=2, exit=False)
    print(json.dumps({'charged_generated_json_bytes': FIXTURE_BYTES,
                      'kernel_operations_mocked': True, 'runtime_qualified': False}))
    raise SystemExit(not suite.result.wasSuccessful())
