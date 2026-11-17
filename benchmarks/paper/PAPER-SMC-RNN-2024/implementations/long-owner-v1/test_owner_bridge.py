"""Generated custody/clock controls; no Docker, original arrays or candidates."""
from pathlib import Path
import copy
import fcntl
import os
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch, Mock
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common as C
import journal as J
import cli_custody as CC
import owned_episode as E
import runner as R

P = {'bytes': 1, 'sha256': 'a' * 64}


class LegacyFixture:
    COMMAND = ['fixed', 'source', 'entry']
    TRANSPORT_SHA = 'b' * 64
    PROFILES = {'improvement': {'cpu_seconds': 7200, 'wall_seconds': 10800,
                              'memory_bytes': 4294967296, 'threads': 1}}

    def __init__(self):
        self.protocol = {'source': P, 'outcome': 'improvement'}
        self.runtime = {'image': 'sha256:' + 'c' * 64, 'source_read_bytes': 80000, 'host_write_bytes': 60000}

    def admit_protocol(self, *unused):
        return self.protocol, self.runtime

    @staticmethod
    def read(path):
        return C.read(path)

    @staticmethod
    def resources(*unused):
        return {'producer_seconds': 10800, 'setup_seconds': 60, 'capture_seconds': 300,
                'cleanup_seconds': 60, 'source_read_bytes': 40000, 'host_write_bytes': 30000}

    @staticmethod
    def validate_closed(request, receipt):
        C.need(receipt['status'] == 'captured' and receipt['request_sha256'] == C.pin(C.encoded(request))['sha256'],
               'Exact complete fake receipt')


class OwnerBridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='smc-owner-bridge-')
        self.root = Path(self.tmp.name).resolve()
        self.owner = self.root / 'owner'
        self.owner.mkdir(mode=0o700)
        (self.owner / 'process').mkdir(mode=0o700)
        (self.owner / 'events').mkdir(mode=0o700)
        self.output = self.root / 'output'
        (self.output / 'jobs').mkdir(parents=True)
        now = time.monotonic()
        self.invocation = {'clock': {'origin': now - 1, 'controller_deadline': now + 30,
            'deadline': now + 90, 'clock_identity': 'generated'}, 'protocol_path': str(self.root / 'protocol.json'),
            'protocol_pin': P, 'output': str(self.output), 'owner': str(self.owner), 'source': P,
            'transport_cost_allocation': {'original_child_read_ceiling': 80000}}
        self.legacy = LegacyFixture()
        self.custody = Mock()
        self.writer = C.OwnerWriter(123)
        self.journal = J.ParentJournal(self.owner / 'events', self.invocation, P, P,
                                       self.legacy, self.custody, self.writer)

    def tearDown(self):
        self.tmp.cleanup()

    def message(self, name, value):
        return {'schema': 'smc_owner_rpc_v1', 'invocation_pin': P,
                'sequence': self.journal.sequence, 'event': name, 'value': value}

    def ready(self):
        self.journal.accept(self.message('CONTROLLER-READY', {'fixture': True}), controller_check=lambda v: None)

    def prepare(self):
        self.ready()
        for index, phase in enumerate(C.CONDITIONS):
            folder = self.output / 'jobs' / phase
            folder.mkdir()
            exposure = C.publish(folder / 'EXPOSURE.json', {'fixture': phase})
            request = {'schema': 'osl_owned_phase_request_v1', 'phase_id': phase, 'action': 'held_attempt',
                'role': 'A' if index == 0 else 'B', 'image': self.legacy.runtime['image'],
                'command': self.legacy.COMMAND, 'workdir': '/work', 'source': P, 'exposure': exposure,
                'clock': {k: self.invocation['clock'][k] for k in ('origin',)},
                'resources': self.legacy.resources(), 'output': {'kind': 'generic', 'manifest': 'OUTPUTS.json'}}
            request['clock']['phase_deadline'] = self.invocation['clock']['controller_deadline']
            request_file = C.publish(folder / 'REQUEST.json', request)
            self.journal.accept(self.message('PREPARED', {'request': request, 'request_file': request_file}))

    def provider(self, name, value, phase=C.CONDITIONS[0]):
        row = {'schema': 'osl_transport_journal_v1', 'phase_id': phase,
            'request_sha256': C.pin(C.encoded(self.journal.prepared[phase]))['sha256'],
            'index': self.journal.indices[phase], 'event': name, 'value': value}
        return self.message(name, {'record': row, 'pin': C.pin(C.encoded(row))})

    def own(self, phase=C.CONDITIONS[0]):
        prefix = 'osl-' + 'd' * 24
        own = {'schema': 'osl_phase_ownership_v1', 'phase_id': phase,
            'request_pin': C.pin(C.encoded(self.journal.prepared[phase])),
            'engine_source_pin': {'bytes': 1, 'sha256': self.legacy.TRANSPORT_SHA},
            'original_deadline': self.invocation['clock']['deadline'],
            'phase_deadline': self.invocation['clock']['controller_deadline'],
            'attempt_prefix': prefix, 'resources': {key: {'kind': 'volume' if key == 'volume' else 'container',
                'name': prefix + '-' + key, 'owner': prefix + '/' + key,
                'attempted': False, 'acknowledged': False} for key in ('volume', 'holder', 'producer')}}
        self.journal.accept(self.provider('OWNERSHIP', {'ownership': own, 'ownership_pin': C.pin(C.encoded(own))}, phase))

    def test_partial_frames_and_duplicate_json_are_not_repaired(self):
        raw = C.frame({'x': 1})
        b = bytearray(raw[:5])
        self.assertIsNone(C.extract(b))
        b.extend(raw[5:])
        self.assertEqual(C.extract(b), {'x': 1})
        self.assertEqual(b, b'')
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            C.parse(b'{"a":1,"a":2}')
        with self.assertRaises(ValueError):
            C.frame({'x': float('nan')})

    def test_actual_parent_check_before_first_ack(self):
        check = Mock(side_effect=ValueError('wrong birth'))
        with self.assertRaises(ValueError):
            self.journal.accept(self.message('CONTROLLER-READY', {}), controller_check=check)
        self.assertEqual(list((self.owner / 'events').iterdir()), [])
        self.assertEqual(self.journal.sequence, 0)

    def test_both_prepared_before_provider_release(self):
        self.prepare()
        self.journal.prepared.pop(C.CONDITIONS[1])
        with self.assertRaisesRegex(ValueError, 'Both frozen'):
            self.own()

    def test_new_clock_and_changed_source_refused(self):
        self.prepare()
        phase = C.CONDITIONS[0]
        self.journal.prepared[phase]['source'] = {'bytes': 1, 'sha256': 'e' * 64}
        # Reconstructed PREPARED must fail, even if its saved bytes are rehashed.
        request = self.journal.prepared.pop(phase)
        p = self.output / 'jobs' / phase / 'REQUEST.json'
        p.unlink()
        request_file = C.publish(p, request)
        with self.assertRaisesRegex(ValueError, 'Exact source'):
            self.journal.accept(self.message('PREPARED', {'request': request, 'request_file': request_file}))

    def test_ownership_original_deadline_cannot_refresh(self):
        self.prepare()
        self.own()
        phase = C.CONDITIONS[0]
        altered = copy.deepcopy(self.journal.ownership[phase])
        altered['ownership']['original_deadline'] += 1
        altered['ownership_pin'] = C.pin(C.encoded(altered['ownership']))
        self.journal.ownership.clear()
        self.journal.indices[phase] = 0
        with self.assertRaisesRegex(ValueError, 'preactivation'):
            self.journal.accept(self.provider('OWNERSHIP', altered))

    def test_cli_capture_and_fsync_precede_ack(self):
        self.prepare()
        self.own()
        end = self.invocation['clock']['controller_deadline'] - 1
        self.journal.accept(self.provider('CLI-INTENT', {'index': 0, 'phase': 'image', 'cap': 131072, 'original_end': end}))
        event = {'index': 0, 'phase': 'image', 'original_end': end}
        message = self.provider('CLI-CHILD', event)
        expected_path = self.owner / 'events' / ('EVENT-' + str(self.journal.sequence).zfill(6) + '.json')
        def capture(value, cutoff):
            self.assertFalse(expected_path.exists())
            self.assertEqual(cutoff, self.invocation['clock']['controller_deadline'])
        self.custody.capture.side_effect = capture
        answer = self.journal.accept(message)
        self.assertTrue(expected_path.exists())
        self.assertEqual(answer['message_pin'], C.pin(C.encoded(message)))
        self.custody.capture.assert_called_once()

    def test_capture_or_publication_failure_never_acknowledges(self):
        self.prepare()
        self.own()
        end = self.invocation['clock']['controller_deadline'] - 1
        self.journal.accept(self.provider('CLI-INTENT', {'index': 0, 'phase': 'image', 'cap': 1, 'original_end': end}))
        self.custody.capture.side_effect = ValueError('birth mismatch')
        with self.assertRaisesRegex(ValueError, 'birth mismatch'):
            self.journal.accept(self.provider('CLI-CHILD', {'index': 0, 'phase': 'image', 'original_end': end}))
        before = self.writer.used
        with patch.object(C, 'publish', side_effect=OSError('disk')):
            with self.assertRaises(OSError):
                self.writer.publish(self.owner / 'failed.json', {'x': 1})
        self.assertGreater(self.writer.used, before)

    def test_whole_owner_budget_reserves_terminal_failure(self):
        self.writer.used = C.JOURNAL_CAP - self.writer.terminal_reserve
        with self.assertRaisesRegex(ValueError, 'Whole owner'):
            self.writer.publish(self.owner / 'denied.json', {'event': 1})
        self.writer.publish(self.owner / 'terminal.json', {'failed': True}, terminal=True)
        self.assertTrue((self.owner / 'terminal.json').exists())

    def test_compact_request_binding_not_pretty_hash(self):
        self.prepare()
        self.own()
        message = self.provider('CLI-INTENT', {'index': 0, 'phase': 'image', 'cap': 1,
                                               'original_end': self.invocation['clock']['controller_deadline'] - 1})
        import json
        row = message['value']['record']
        row['request_sha256'] = C.pin((json.dumps(self.journal.prepared[C.CONDITIONS[0]], indent=2) + '\n').encode())['sha256']
        message['value']['pin'] = C.pin(C.encoded(row))
        with self.assertRaisesRegex(ValueError, 'record identity'):
            self.journal.accept(message)

    def test_unplanned_resource_and_duplicate_event_refused(self):
        self.prepare()
        self.own()
        message = self.provider('CREATE-ATTEMPT', {'kind': 'volume', 'name': 'unowned', 'owner': 'wrong'})
        with self.assertRaisesRegex(ValueError, 'planned resource'):
            self.journal.accept(message)
        prior = self.message('CONTROLLER-READY', {})
        prior['sequence'] -= 1
        with self.assertRaisesRegex(ValueError, 'synchronous sequence'):
            self.journal.accept(prior)

    def test_recovery_grant_explicit_and_bounded(self):
        with self.assertRaises(ValueError):
            R.recovery_budget(True, 131072)
        with self.assertRaises(ValueError):
            R.recovery_budget(1024**3, 131072)
        good = R.recovery_budget(2 * 1024**2, 1024**2)
        self.assertEqual(good['per_phase_cli_calls'], 64)

    def test_pidfd_capture_before_release_and_refusal(self):
        engine = Mock()
        token = {'pid': 1234, 'pgid': 1234, 'session_id': 1234}
        event = {'pid': 1234, 'pgid': 1234, 'process_identity': token,
                 'docker_exec_still_gated': True, 'independent_group': True,
                 'original_end': time.monotonic() + 10}
        custody = CC.CliCustody(engine, event['original_end'] + 20)
        engine.process_identity.return_value = {**token, 'changed': True}
        with patch.object(CC.os, 'pidfd_open', return_value=88, create=True), \
             patch.object(CC.os, 'close') as close:
            with self.assertRaises(ValueError):
                custody.capture(event, event['original_end'] + 1)
        close.assert_called_once_with(88)
        self.assertEqual(custody.children, [])

    def test_pidfd_not_numeric_group_signal_and_unknown_group_fails(self):
        custody = CC.CliCustody(Mock(), time.monotonic() + 1)
        custody.children = [{'fd': 88, 'token': {'pid': 1234, 'pgid': 1234}, 'original_end': time.monotonic() + 1}]
        with patch.object(CC.signal, 'pidfd_send_signal', create=True) as signal_fd, \
             patch.object(CC.select, 'select', return_value=([88], [], [])), \
             patch.object(CC, 'reap_pidfd'), \
             patch.object(CC.os, 'killpg') as group_probe, patch.object(CC.os, 'close'):
            outcome = custody.close(time.monotonic() + .005)
        self.assertFalse(outcome['all_acknowledged_cli_absent'])
        signal_fd.assert_called_once()
        self.assertTrue(all(call.args[1] == 0 for call in group_probe.call_args_list))

    def test_observed_absence_persisted_before_pidfd_retirement(self):
        custody = CC.CliCustody(Mock(), time.monotonic() + 20)
        custody.children = [{'fd': 88, 'token': {'pid': 1234, 'pgid': 1234}, 'original_end': time.monotonic() + 10}]
        with patch.object(CC.select, 'select', return_value=([88], [], [])), \
             patch.object(CC, 'reap_pidfd'), \
             patch.object(CC.os, 'killpg', side_effect=ProcessLookupError), patch.object(CC.os, 'close') as close:
            def durable(row):
                close.assert_not_called()
                self.assertTrue(row['group_absent'])
            custody.retire_exited(durable)
        self.assertEqual(custody.children, [])
        self.assertEqual(len(custody.retired), 1)
        close.assert_called_once_with(88)

    def test_exact_controller_pidfd_reap(self):
        with patch.object(R.os, 'P_PIDFD', 3, create=True), \
             patch.object(R.os, 'waitid', create=True, side_effect=ChildProcessError) as reap:
            R.reap_controller({'fd': 88})
        reap.assert_called_once_with(3, 88, os.WEXITED | os.WNOHANG)

    def test_owner_setup_failure_releases_lock_and_preserves_error(self):
        invocation = copy.deepcopy(self.invocation)
        invocation['source'] = P
        with patch.object(R, 'make_invocation', return_value=(invocation, P, self.legacy, self.legacy.runtime)), \
             patch.object(R, 'engine_for', side_effect=ValueError('generated setup failure')), \
             patch.object(R.process_owner, 'stop', return_value={'absence_verified': True}):
            with self.assertRaisesRegex(ValueError, 'Preserved terminal'):
                R.execute('unused', 'unused', 'unused', 'unused', 1, 1)
        result = C.read(self.owner / 'RESULT.json')
        self.assertEqual(result['error']['type'], 'ValueError')
        self.assertEqual(result['status'], 'failed')
        with (self.owner / 'OWNER.lock').open('rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_grade_refuses_child_draft_without_parent_closure(self):
        C.publish(self.owner / 'INVOCATION.json', self.invocation)
        invocation_pin = C.pin(C.body(self.owner / 'INVOCATION.json'))
        closure = {'invocation_pin': invocation_pin, 'source': P, 'clock': self.invocation['clock'],
                   'future_controller_and_acknowledged_cli_release_closed': False,
                   'controller_group': {'absence_verified': False},
                   'acknowledged_cli': {'all_acknowledged_cli_absent': False}}
        closure_pin = C.publish(self.owner / 'CONTROLLER_CLOSED.json', closure)
        result = {'status': 'closed_pair', 'error': None, 'recovery_error': None, 'cleanup_errors': [],
                  'recovery_cli': {'all_acknowledged_cli_absent': True},
                  'controller_execution': {'natural_exit': True}, 'source': P,
                  'invocation_pin': invocation_pin, 'controller_closure_pin': closure_pin}
        result_pin = C.publish(self.owner / 'RESULT.json', result)
        with patch.object(R.legacy, 'source_identity', return_value=P), patch.object(R.legacy, 'load') as load:
            with self.assertRaisesRegex(ValueError, 'parent closure'):
                R.grade(self.owner, result_pin['sha256'], 'unopened-target', 'unused', 'unused', 1)
        load.assert_not_called()

    def test_complete_two_arm_composition_uses_only_precommitted_clock(self):
        # Only original-format arrays/Provider execution are mocked. This drives
        # the successor's real complete two-arm preparation/closure composition.
        self.output.rmdir() if not any(self.output.iterdir()) else None
        import shutil
        shutil.rmtree(self.output)
        materials = self.root / 'materials'
        materials.mkdir()
        protocol_folder = self.root / 'protocol'
        protocol_folder.mkdir()
        transport = self.root / 'transport'
        transport.mkdir()
        C.publish(transport / 'SOURCE_MANIFEST.json', {'generated': True})
        for phase in C.CONDITIONS:
            (protocol_folder / phase).mkdir()
            C.publish(protocol_folder / phase / 'declaration.json', {'generated': phase})
        protocol = {'source': P, 'outcome': 'improvement', 'pair_path': str(materials / 'pair_manifest.json'),
            'task_path': str(self.root / 'task.json'), 'programs': {phase: {'program': P, 'declaration': P}
                                                               for phase in C.CONDITIONS}}
        runtime = {'image': 'sha256:' + 'c' * 64, 'qualification': {'path': 'generated', **P},
                   'docker_binary': 'unused', 'docker_socket': 'unused', 'source_read_bytes': 80000, 'host_write_bytes': 60000}
        calls, events, frozen = [], [], []
        inv = copy.deepcopy(self.invocation)
        inv['protocol_path'] = str(protocol_folder / 'PROTOCOL.json')
        def emit(name, value):
            events.append((name, value))
        class Provider:
            def __init__(self, *args):
                calls.append(('init', args))
            def execute_phase(inner, request, mounts, deadline, callback):
                self.assertEqual([x[0] for x in events[:2]], ['PREPARED', 'PREPARED'])
                self.assertIs(callback, emit)
                self.assertEqual(request['clock'], {'origin': inv['clock']['origin'],
                                                   'phase_deadline': inv['clock']['controller_deadline']})
                self.assertEqual(deadline, inv['clock']['deadline'])
                calls.append(('phase', request['phase_id'], request['resources']))
                folder = self.output / 'quarantine' / request['phase_id']
                folder.mkdir()
                C.publish(folder / 'rates.fixture.json', {'generated': True})
                receipt = {'phase_id': request['phase_id']}
                return {'receipt': receipt, 'receipt_pin': P, 'receipt_path': str(folder / 'receipt.fixture.json')}
        bench = types.SimpleNamespace(inspect_pair=Mock())
        def freeze(*args, **kwargs):
            frozen.append(args[4])
            C.publish(args[8], {'generated': args[4]})
        bench.freeze = freeze
        L = types.SimpleNamespace(admit_protocol=lambda *a: (protocol, runtime),
            qualify=lambda *a: {'image_inventory_sha256': 'f' * 64},
            public_context=lambda *a: ({}, {}), benchmark=lambda: bench,
            PAIR_SHA='a'*64, TASK_SHA='b'*64, PAIR_CAP=33554432,
            path=C.ordinary, encoded=C.encoded, request_bytes=C.encoded,
            publish=lambda p, raw, mode=0o400: self._raw_publish(p, raw),
            job_for=lambda *a: {'generated': True}, mounts_for=lambda *a: {}, mount_identity=lambda x: x,
            COMMAND=['fixed', 'entry'], resources=lambda *a: self.legacy.resources(),
            TRANSPORT=transport, provider_class=lambda: Provider, ROUTE='smc_restricted_single_process_pair_v1',
            observe_closed=lambda provider, request, result, deadline: result['receipt'],
            captured_predictions=lambda receipt, *a: {'offline': self.output / 'quarantine' / receipt['phase_id'] / 'rates.fixture.json'})
        report = E.execute(inv, P, P, emit, L)
        self.assertEqual(frozen, list(C.CONDITIONS))
        self.assertEqual([x[1] for x in calls if x[0] == 'phase'], list(C.CONDITIONS))
        self.assertEqual(events[-1][0], 'CONTROLLER-DONE')
        self.assertFalse(report['private_target_accessed'])
        self.assertTrue(report['owner_closure_still_required'])

    @staticmethod
    def _raw_publish(path, raw):
        with Path(path).open('xb') as stream:
            stream.write(raw)
        return C.pin(raw)

    def test_recovery_charges_full_unknown_child_before_additional_allowance(self):
        self.prepare()
        self.own()
        inv = copy.deepcopy(self.invocation)
        inv['recovery'] = R.recovery_budget(2**21, 2**20)
        transport = self.root / 'transport'
        transport.mkdir()
        C.publish(transport / 'SOURCE_MANIFEST.json', {'generated': True})
        instances = []
        class Provider:
            def __init__(inner, *args):
                inner.args = args
                instances.append(inner)
            def recover(inner, phase, request_pin, ownership_pin, deadline, journal, limits, closure_pin):
                self.assertEqual(inner.read_used, self.legacy.runtime['source_read_bytes'])
                self.assertEqual(inner.write_used, self.legacy.runtime['host_write_bytes'])
                self.assertEqual(deadline, inv['clock']['deadline'])
                self.assertEqual(limits['source_read_bytes'], 2**20)
                self.assertEqual(closure_pin, P)
                return {'receipt': {'all_resource_custody_closed': False, 'all_namespaces_empty': True},
                        'receipt_pin': P, 'final_transport_counters': {'read_bytes': 123, 'write_bytes': 45}}
        L = types.SimpleNamespace(provider_class=lambda: Provider, TRANSPORT=transport)
        runtime = {**self.legacy.runtime, 'docker_binary': 'unused', 'docker_socket': 'unused'}
        result = R.recover_phases(inv, P, L, runtime, self.journal, P, self.custody)
        self.assertEqual(instances[0].args[-2:], (80000 + 2**21, 60000 + 2**20))
        self.assertFalse(result[0]['all_resource_custody_closed'])

    def test_terminal_publication_failure_does_not_hold_owner_lock(self):
        invocation = copy.deepcopy(self.invocation)
        invocation['source'] = P
        original = C.OwnerWriter.publish
        def fail_closure(writer, path, value, **kwargs):
            if Path(path).name == 'CONTROLLER_CLOSED.json':
                raise OSError('generated failed closure publication')
            return original(writer, path, value, **kwargs)
        with patch.object(R, 'make_invocation', return_value=(invocation, P, self.legacy, self.legacy.runtime)), \
             patch.object(R, 'engine_for', side_effect=ValueError('generated setup failure')), \
             patch.object(R.process_owner, 'stop', return_value={'absence_verified': True}), \
             patch.object(C.OwnerWriter, 'publish', fail_closure):
            with self.assertRaises(OSError):
                R.execute('unused', 'unused', 'unused', 'unused', 1, 1)
        receipt = C.read(self.owner / 'TERMINAL_FAILURE.json')
        self.assertEqual(receipt['original_error']['type'], 'ValueError')
        self.assertEqual(receipt['terminal_error'], 'OSError')
        with (self.owner / 'OWNER.lock').open('rb') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)

    def test_later_retirement_failure_never_reuses_first_closed_fd(self):
        custody = CC.CliCustody(Mock(), time.monotonic() + 20)
        custody.children = [{'fd': fd, 'token': {'pid': pid, 'pgid': pid},
                             'original_end': time.monotonic() + 10}
                            for fd, pid in ((88, 1234), (99, 1235))]
        calls = []
        def publish(row):
            calls.append(row['process_identity']['pid'])
            if len(calls) == 2:
                raise OSError('second publication failed')
        with patch.object(CC.select, 'select', side_effect=lambda reads, *a: (reads, [], [])), \
             patch.object(CC, 'reap_pidfd'), \
             patch.object(CC.os, 'killpg', side_effect=ProcessLookupError), patch.object(CC.os, 'close') as close:
            with self.assertRaises(OSError):
                custody.retire_exited(publish)
        self.assertEqual([x['fd'] for x in custody.children], [99])
        self.assertEqual([x['process_identity']['pid'] for x in custody.retired], [1234])
        close.assert_called_once_with(88)

    def test_missed_cutoff_still_signals_owned_pidfd_without_new_wait(self):
        custody = CC.CliCustody(Mock(), time.monotonic() - 1)
        custody.children = [{'fd': 88, 'token': {'pid': 1234, 'pgid': 1234}, 'original_end': 1}]
        with patch.object(CC.signal, 'pidfd_send_signal', create=True) as send, \
             patch.object(CC.select, 'select') as waiting, patch.object(CC.os, 'close'):
            result = custody.close(time.monotonic() - 1)
        send.assert_called_once_with(88, CC.signal.SIGKILL, None, 0)
        waiting.assert_not_called()
        self.assertFalse(result['all_acknowledged_cli_absent'])

    def test_unknown_first_group_cannot_starve_second_owned_stop(self):
        custody = CC.CliCustody(Mock(), time.monotonic() + 1)
        custody.children = [{'fd': fd, 'token': {'pid': pid, 'pgid': pid}, 'original_end': 1}
                            for fd, pid in ((88, 1234), (99, 1235))]
        signals = []
        def inspect(reads, *unused):
            self.assertEqual(signals, [88, 99])
            return reads, [], []
        def probe(pgid, sig):
            if pgid == 1235:
                raise ProcessLookupError
        with patch.object(CC.signal, 'pidfd_send_signal', create=True, side_effect=lambda fd, *a: signals.append(fd)), \
             patch.object(CC.select, 'select', side_effect=inspect), patch.object(CC, 'reap_pidfd') as reap, \
             patch.object(CC.os, 'killpg', side_effect=probe), patch.object(CC.os, 'close'):
            result = custody.close(time.monotonic() + .005)
        self.assertFalse(result['all_acknowledged_cli_absent'])
        self.assertTrue(result['records'][1]['group_absent'])
        self.assertIn(unittest.mock.call(99), reap.call_args_list)

    def test_controller_eof_without_completion_fails_promptly(self):
        import socket
        parent, child = socket.socketpair()
        out_r, out_w = os.pipe()
        err_r, err_w = os.pipe()
        proc = types.SimpleNamespace(stdout=os.fdopen(out_r, 'rb'), stderr=os.fdopen(err_r, 'rb'))
        child.close()
        started = time.monotonic()
        try:
            with self.assertRaisesRegex(ValueError, 'channel ended'):
                R.pump(proc, parent, self.journal, self.invocation, {'token': 'generated'}, {})
        finally:
            parent.close()
            proc.stdout.close()
            proc.stderr.close()
            os.close(out_w)
            os.close(err_w)
        self.assertLess(time.monotonic() - started, 1)

    def test_crossing_deadline_during_publication_never_acknowledges(self):
        original = self.writer.publish
        def delayed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.invocation['clock']['controller_deadline'] = time.monotonic() - 1
            return result
        with patch.object(self.writer, 'publish', side_effect=delayed):
            with self.assertRaisesRegex(ValueError, 'Durable acknowledgement'):
                self.journal.accept(self.message('CONTROLLER-READY', {}), controller_check=lambda v: None)
        self.assertTrue((self.owner / 'events' / 'EVENT-000000.json').exists())

    def test_actual_controller_entry_joins_process_subdirectory_and_clock(self):
        import controller
        invocation = copy.deepcopy(self.invocation)
        invocation['clock']['outcome'] = 'improvement'
        invocation_pin = C.publish(self.owner / 'INVOCATION.json', invocation)
        argv = [str(HERE / 'controller.py'), '--invocation', str(self.owner / 'INVOCATION.json'),
                '--invocation-sha256', invocation_pin['sha256'], '--channel-fd', '123']
        owner = {'child_argv': [sys.executable, '-I', '-B', *argv], 'pid': 567, 'pgid': 567,
                 'token': 'a' * 32, 'grant': {**invocation['clock'], 'invocation_pin': invocation_pin}}
        channel = Mock()
        with patch.object(controller.sys, 'argv', argv), \
             patch.object(controller.process_owner, 'expected', return_value=(owner, [])) as expected, \
             patch.object(controller.process_owner, 'clock_identity', return_value='generated'), \
             patch.object(controller.legacy, 'source_identity', return_value=P), \
             patch.object(controller.legacy, 'load', return_value=self.legacy), \
             patch.object(controller.os, 'getppid', return_value=567), \
             patch.object(controller.os, 'getpgrp', return_value=567), \
             patch.object(controller.socket, 'socket'), patch.object(controller, 'Channel', return_value=channel), \
             patch.object(controller.owned_episode, 'execute') as execute:
            controller.main()
        expected.assert_called_once_with(self.owner / 'process')
        self.assertEqual(channel.call_args.args[0], 'CONTROLLER-READY')
        execute.assert_called_once_with(invocation, invocation_pin, P, channel, self.legacy)

    def test_unexpected_cleanup_wait_error_closes_every_owned_handle(self):
        custody = CC.CliCustody(Mock(), time.monotonic() + 20)
        custody.children = [{'fd': fd, 'token': {'pid': pid, 'pgid': pid}, 'original_end': 1}
                            for fd, pid in ((88, 1234), (99, 1235))]
        with patch.object(CC.signal, 'pidfd_send_signal', create=True) as send, \
             patch.object(CC.select, 'select', return_value=([], [], [])), \
             patch.object(CC.os, 'killpg'), patch.object(CC.time, 'sleep', side_effect=KeyboardInterrupt), \
             patch.object(CC.os, 'close') as close:
            result = custody.close(time.monotonic() + 1)
        self.assertEqual(close.call_args_list, [unittest.mock.call(88), unittest.mock.call(99)])
        self.assertFalse(result['all_acknowledged_cli_absent'])
        self.assertEqual({call.args[0] for call in send.call_args_list}, {88, 99})
        self.assertEqual(custody.children, [])

    def test_deferred_supervisor_stop_precedes_any_queued_ack(self):
        import socket
        parent, child = socket.socketpair()
        out_r, out_w = os.pipe()
        err_r, err_w = os.pipe()
        proc = types.SimpleNamespace(stdout=os.fdopen(out_r, 'rb'), stderr=os.fdopen(err_r, 'rb'))
        try:
            child.sendall(C.frame(self.message('CONTROLLER-READY', {})))
            with self.assertRaisesRegex(ValueError, 'termination requested'):
                R.pump(proc, parent, self.journal, self.invocation, {}, {}, [15])
        finally:
            parent.close()
            child.close()
            proc.stdout.close()
            proc.stderr.close()
            os.close(out_w)
            os.close(err_w)
        self.assertEqual(self.journal.sequence, 0)

    def test_stop_during_durable_publication_withholds_release_ack(self):
        import socket
        parent, child = socket.socketpair()
        out_r, out_w = os.pipe()
        err_r, err_w = os.pipe()
        proc = types.SimpleNamespace(stdout=os.fdopen(out_r, 'rb'), stderr=os.fdopen(err_r, 'rb'))
        cancelled = [None]
        message = self.message('CONTROLLER-READY', {})
        def publish_then_stop(*args, **kwargs):
            cancelled[0] = 15
            return {'schema': 'smc_owner_ack_v1', 'sequence': 0, 'message_pin': C.pin(C.encoded(message))}
        try:
            child.sendall(C.frame(message))
            with patch.object(self.journal, 'accept', side_effect=publish_then_stop):
                with self.assertRaisesRegex(ValueError, 'stop precedes native release'):
                    R.pump(proc, parent, self.journal, self.invocation, {}, {}, cancelled)
            child.setblocking(False)
            with self.assertRaises(BlockingIOError):
                child.recv(4096)
        finally:
            parent.close()
            child.close()
            proc.stdout.close()
            proc.stderr.close()
            os.close(out_w)
            os.close(err_w)


if __name__ == '__main__':
    unittest.main()
