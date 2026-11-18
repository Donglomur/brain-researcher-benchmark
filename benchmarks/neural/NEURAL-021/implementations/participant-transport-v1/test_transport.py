"""Generated message/replay controls; no processes, authentic arrays or targets.

Process and authentic loader qualification require a separate native protocol.
These tests do not repeat the existing delivery/scorer test suites.
"""
import io
import json
import hashlib
from pathlib import Path
import signal
import struct
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import transport as t
IMPLEMENTATIONS = Path(__file__).resolve().parent.parent


def fixture(delivery):
    counts = tuple(tuple(100 * b + u for u in range(65)) for b in range(35))
    history = delivery.expand_counts(counts)
    conditions = [0] * 52 + [1] * 40
    cases = {'schema': 'neural021_public_cases_v1', 'task_id': 'NEURAL-021', 'time_bins': 30,
             'feature_shape': [30, 6, 65], 'units': 'm/s', 'conditions': {'0': 'active', '1': 'passive'},
             'queries': [{'trial_id': 'q%04d' % i, 'condition': delivery.CONDITIONS[c]}
                         for i, c in enumerate(conditions)]}
    train = {'spike_counts': [history] * 272, 'condition': [0, 1] * 136,
             'velocity_m_s': [[[j / 10, -j / 20] for j in range(30)]] * 272}
    query = {'spike_counts': [history] * 92, 'condition': conditions}
    return delivery.Packet.from_arrays(train, query, delivery.encode(cases))


class MemoryChannel:
    """Generated framed bytes. Does not model or establish OS isolation."""
    def __init__(self, requests):
        self.incoming = io.BytesIO(b''.join(t.frame(t.encode(row), t.MAX_REQUEST) for row in requests))
        self.response_hashes = []
        self.total_sent = 0

    def read_exact(self, size):
        return self.incoming.read(size)

    def write(self, body):
        size = struct.unpack('!I', body[:4])[0]
        if size != len(body) - 4:
            raise AssertionError('bad response frame')
        self.response_hashes.append(t.pin(body[4:]))
        self.total_sent += len(body)


def script(mode, calibration=True):
    rows = []
    def add(op, **fields):
        rows.append({'seq': len(rows), 'op': op, **fields})
    if calibration:
        add('calibration', index=0)
        add('calibration', index=271)
    for i in range(92):
        key = 'q%04d' % i
        add('view', trial_id=key)
        if i == 0 and mode == 'typed_viewer':
            add('crop', trial_id=key, unit_start=60, unit_stop=65, bin_start=29, bin_stop=35)
        add('answer', trial_id=key, velocity_m_s=[[i + j / 100, -i - j / 200] for j in range(30)])
    add('finish')
    return rows


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grade, cls.sources = t.load_sources(IMPLEMENTATIONS)
        cls.packet = fixture(cls.sources['delivery'])

    def exchange(self, mode='direct_observation'):
        return t.Exchange(self.sources, self.packet, mode)

    def test_full_both_modes_original_replay_and_wire_commitments(self):
        submissions = []
        for mode in ('direct_observation', 'typed_viewer'):
            exchange = self.exchange(mode)
            channel = MemoryChannel(script(mode))
            transcript = exchange.run(channel)
            submission, receipt = exchange.pending
            replay = self.grade.replay(self.sources, self.packet, mode, submission, receipt)
            self.assertEqual(replay['queries'], 92)
            self.assertEqual(replay['distinct_calibration_trials_viewed'], 2)
            self.assertEqual(channel.total_sent, transcript['response_wire_bytes'])
            self.assertEqual(channel.response_hashes[0], transcript['hello'])
            self.assertEqual(channel.response_hashes[1:], [row['response'] for row in transcript['frames']])
            self.assertTrue(transcript['exchange_alone_is_not_admission'])
            self.assertFalse(json.loads(receipt)['runtime_qualified'])
            previous = '0' * 64
            for row in transcript['frames']:
                self.assertEqual(row['previous_sha256'], previous)
                self.assertEqual(row['sha256'], t.pin(t.encode({k: v for k, v in row.items() if k != 'sha256'}))['sha256'])
                previous = row['sha256']
            submissions.append(submission)
        self.assertEqual(*submissions)

    def test_complete_submission_does_not_require_calibration_exposure(self):
        exchange = self.exchange()
        exchange.run(MemoryChannel(script('direct_observation', calibration=False)))
        replay = self.grade.replay(self.sources, self.packet, exchange.mode, *exchange.pending)
        self.assertEqual(replay['distinct_calibration_trials_viewed'], 0)
        self.assertEqual(json.loads(exchange.hello())['calibration_count'], 272)

    def test_hello_has_exact_roster_and_no_packet_or_operator_paths(self):
        hello = json.loads(self.exchange().hello())
        self.assertEqual(len(hello['queries']), 92)
        self.assertEqual(hello['queries'][0], {'trial_id': 'q0000', 'condition': 'active'})
        self.assertNotIn('crop', hello['actions'])
        self.assertIn('crop', json.loads(self.exchange('typed_viewer').hello())['actions'])
        for token in ('spike_counts', 'training_velocity', 'targets.json', '/Users/', 'Session('):
            self.assertNotIn(token, t.encode(hello).decode())

    def test_exact_action_fields_types_and_sequence(self):
        bad = [
            {'seq': False, 'op': 'finish'}, {'seq': 1, 'op': 'finish'},
            {'seq': 0, 'op': 'python', 'code': '1+1'},
            {'seq': 0, 'op': 'calibration', 'index': True},
            {'seq': 0, 'op': 'calibration', 'index': -1},
            {'seq': 0, 'op': 'calibration', 'index': 272},
            {'seq': 0, 'op': 'view', 'trial_id': 'q0000', 'path': '/tmp/data'},
            {'seq': 0, 'op': 'view', 'trial_id': 'q9999'},
        ]
        for row in bad:
            with self.subTest(row=row), self.assertRaises(ValueError):
                self.exchange().dispatch(t.encode(row))

    def test_direct_crop_and_typed_crop_before_full_view_refused(self):
        crop = {'op': 'crop', 'trial_id': 'q0000', 'unit_start': 0, 'unit_stop': 2, 'bin_start': 0, 'bin_stop': 2}
        for mode in ('direct_observation', 'typed_viewer'):
            with self.assertRaises(ValueError):
                self.exchange(mode).dispatch(t.encode({'seq': 0, **crop}))
        ex = self.exchange('typed_viewer')
        ex.dispatch(t.encode({'seq': 0, 'op': 'view', 'trial_id': 'q0000'}))
        response = json.loads(ex.dispatch(t.encode({'seq': 1, **crop})))
        self.assertEqual(response['svg'].count('data-unit='), 4)

    def test_first_final_answer_full_support_and_no_subset_completion(self):
        ex = self.exchange()
        ex.dispatch(t.encode({'seq': 0, 'op': 'view', 'trial_id': 'q0000'}))
        for values in ([[0, 0]] * 29, [[False, 0]] * 30, [[1e7, 0]] * 30):
            with self.assertRaises(ValueError):
                ex.dispatch(t.encode({'seq': 1, 'op': 'answer', 'trial_id': 'q0000', 'velocity_m_s': values}))
        ex.dispatch(t.encode({'seq': 1, 'op': 'answer', 'trial_id': 'q0000', 'velocity_m_s': [[0, 0]] * 30}))
        with self.assertRaises(ValueError):
            ex.dispatch(t.encode({'seq': 2, 'op': 'answer', 'trial_id': 'q0000', 'velocity_m_s': [[1, 1]] * 30}))
        with self.assertRaises(ValueError):
            ex.dispatch(t.encode({'seq': 2, 'op': 'finish'}))
        self.assertIsNone(ex.pending)

    def test_duplicate_nonfinite_unicode_and_bounded_numeric_json(self):
        for raw in (b'{"seq":0,"seq":0,"op":"finish"}', b'{"seq":NaN}', b'{"seq":1e999}',
                    b'{"seq":' + b'1' * 25 + b'}', b'\xff', b'{"seq":0,}'):
            with self.subTest(raw=raw[:40]), self.assertRaises(ValueError):
                t.strict_json(raw)

    def test_frame_caps_apply_before_payload_and_truncation_is_refused(self):
        for length in (0, t.MAX_REQUEST + 1, 2**32 - 1):
            reader = mock.Mock()
            reader.read_exact.return_value = struct.pack('!I', length)
            with self.assertRaises(ValueError):
                t.read_frame(reader)
            reader.read_exact.assert_called_once_with(4)
        for pieces in ([b'\0'], [struct.pack('!I', 4), b'{}']):
            reader = mock.Mock()
            reader.read_exact.side_effect = pieces
            with self.assertRaises(ValueError):
                t.read_frame(reader)

    def test_unknown_or_premature_eof_cannot_produce_handoff(self):
        exchange = self.exchange()
        with self.assertRaises(ValueError):
            exchange.run(MemoryChannel([{'seq': 0, 'op': 'view', 'trial_id': 'q0000'}]))
        self.assertIsNone(exchange.pending)

    def test_message_and_cumulative_wire_budgets_fail_closed(self):
        with mock.patch.object(t, 'MAX_RECEIVED', 1), self.assertRaises(ValueError):
            self.exchange().run(MemoryChannel(script('direct_observation')))
        with mock.patch.object(t, 'MAX_SENT', 1), self.assertRaises(ValueError):
            self.exchange().run(MemoryChannel(script('direct_observation')))
        with mock.patch.object(t, 'MAX_MESSAGES', 0), self.assertRaises(ValueError):
            self.exchange().dispatch(t.encode({'seq': 0, 'op': 'view', 'trial_id': 'q0000'}))

    def test_extreme_generated_svg_fits_enforced_frame_cap(self):
        d = self.sources['delivery']
        trial = d.Trial('t0271', 'passive', tuple((2**63 - 1,) * 65 for _ in range(35)),
                        tuple((1.234567890123456e-200, -1.234567890123456e-200) for _ in range(30)))
        body = t.encode({'seq': 2047, 'type': 'svg', 'media_type': 'image/svg+xml', 'svg': d.render_svg(trial)})
        self.assertLess(len(body), t.MAX_RESPONSE)
        self.assertEqual(struct.unpack('!I', t.frame(body, t.MAX_RESPONSE)[:4])[0], len(body))

    def test_invalid_packet_refused_before_any_process_creation(self):
        with mock.patch.object(t.subprocess, 'Popen') as launch, self.assertRaises(ValueError):
            t.run_participant(self.grade, self.sources, object(), 'direct_observation',
                              ['/usr/bin/false'], str(Path(__file__).resolve().parent), 1, observer=lambda _: None)
        launch.assert_not_called()

    def test_symlinked_grade_directory_refused_before_source_open(self):
        with mock.patch.object(Path, 'is_symlink', lambda path: path.name == 'observation-grade-v1'), \
                mock.patch.object(t.os, 'open') as opening, self.assertRaises(ValueError):
            t.load_sources(IMPLEMENTATIONS)
        opening.assert_not_called()

    def _process_fixture(self):
        process = mock.Mock()
        process.pid = 987654321  # Never passed to an actual process/signal primitive.
        process.returncode = 0
        process.poll.return_value = 0
        return process

    def _fake_exchange(self, exchange, _channel):
        exchange.pending = (b'generated-submission', b'generated-receipt')
        return {'generated_lifecycle_fixture_only': True}

    def test_mocked_clean_closure_precedes_replay_and_restores_handlers(self):
        process = self._process_fixture()
        steps = []
        channel = mock.Mock()
        channel.close_success.side_effect = lambda: steps.append('closed') or {'owned_process_group_absent': True}
        cleanup = {'leader_reaped': True, 'owned_process_group_absent': True}
        old = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
        def replay(*_):
            self.assertIn('closed', steps)
            steps.append('replay')
            return {'generated_replay_stub': True}
        events = []
        with mock.patch.object(t.subprocess, 'Popen', return_value=process), \
                mock.patch.object(t, 'PipeChannel', return_value=channel), \
                mock.patch.object(t.Exchange, 'run', lambda exchange, channel: self._fake_exchange(exchange, channel)), \
                mock.patch.object(t, 'cleanup', return_value=cleanup), \
                mock.patch.object(self.grade, 'replay', side_effect=replay):
            result = t.run_participant(self.grade, self.sources, self.packet, 'direct_observation',
                ['/generated/participant'], str(Path(__file__).resolve().parent), 10, observer=events.append)
        self.assertEqual(steps, ['closed', 'replay'])
        self.assertEqual([e['phase'] for e in events],
            ['before_spawn', 'spawned', 'owned_participant_closed', 'replay_complete', 'cleanup_observed'])
        self.assertFalse(json.loads(result[3])['isolation_qualified'])
        self.assertEqual(json.loads(result[3])['admission'], t.ADMISSION)
        self.assertFalse(json.loads(result[3])['admission']['artifacts_alone_admissible'])
        self.assertEqual(old, {sig: signal.getsignal(sig) for sig in old})

    def test_mocked_termination_during_spawn_defers_until_pid_is_recorded(self):
        process = self._process_fixture()
        events = []
        cleanup = {'leader_reaped': True, 'owned_process_group_absent': True}
        def launch(*_, **__):
            # Direct invocation of the installed handler; no signal/process is sent.
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM, None)
            return process
        with mock.patch.object(t.subprocess, 'Popen', side_effect=launch), \
                mock.patch.object(t, 'cleanup', return_value=cleanup), \
                mock.patch.object(self.grade, 'replay') as replay, self.assertRaises(t.SignalTermination):
            t.run_participant(self.grade, self.sources, self.packet, 'direct_observation',
                ['/generated/participant'], str(Path(__file__).resolve().parent), 10, observer=events.append)
        self.assertEqual([e['phase'] for e in events], ['before_spawn', 'spawned', 'cleanup_observed'])
        self.assertEqual(events[1]['owned_process_group'], process.pid)
        replay.assert_not_called()

    def test_mocked_cleanup_uncertainty_cannot_return_success(self):
        process = self._process_fixture()
        channel = mock.Mock()
        channel.close_success.side_effect = t.Refusal('generated failed closure')
        events = []
        cleanup = {'leader_reaped': False, 'owned_process_group_absent': False}
        with mock.patch.object(t.subprocess, 'Popen', return_value=process), \
                mock.patch.object(t, 'PipeChannel', return_value=channel), \
                mock.patch.object(t.Exchange, 'run', lambda exchange, channel: self._fake_exchange(exchange, channel)), \
                mock.patch.object(t, 'cleanup', return_value=cleanup), \
                mock.patch.object(self.grade, 'replay') as replay, self.assertRaisesRegex(ValueError, 'cleanup incomplete'):
            t.run_participant(self.grade, self.sources, self.packet, 'direct_observation',
                ['/generated/participant'], str(Path(__file__).resolve().parent), 10, observer=events.append)
        self.assertFalse(events[-1]['owned_process_group_absent'])
        replay.assert_not_called()

    def test_mocked_replay_over_deadline_cannot_return_success(self):
        process = self._process_fixture()
        channel = mock.Mock()
        channel.close_success.return_value = {'owned_process_group_absent': True}
        clock = [0.0]
        def replay(*_):
            clock[0] = 2.0
            return {'generated_replay_stub': True}
        with mock.patch.object(t.subprocess, 'Popen', return_value=process), \
                mock.patch.object(t, 'PipeChannel', return_value=channel), \
                mock.patch.object(t.Exchange, 'run', lambda exchange, channel: self._fake_exchange(exchange, channel)), \
                mock.patch.object(t, 'cleanup', return_value={'leader_reaped': True, 'owned_process_group_absent': True}), \
                mock.patch.object(t.time, 'monotonic', side_effect=lambda: clock[0]), \
                mock.patch.object(self.grade, 'replay', side_effect=replay), self.assertRaisesRegex(ValueError, 'during replay'):
            t.run_participant(self.grade, self.sources, self.packet, 'direct_observation',
                ['/generated/participant'], str(Path(__file__).resolve().parent), 1, observer=lambda _: None)

    def test_mocked_spawn_observer_failure_still_cleans_and_restores_handlers(self):
        process = self._process_fixture()
        events = []
        old = {sig: signal.getsignal(sig) for sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)}
        def observer(event):
            events.append(event)
            if event['phase'] == 'spawned':
                raise OSError('generated journal failure')
        with mock.patch.object(t.subprocess, 'Popen', return_value=process), \
                mock.patch.object(t, 'cleanup', return_value={'leader_reaped': True, 'owned_process_group_absent': True}) as cleanup, \
                mock.patch.object(self.grade, 'replay') as replay, self.assertRaises(OSError):
            t.run_participant(self.grade, self.sources, self.packet, 'direct_observation',
                ['/generated/participant'], str(Path(__file__).resolve().parent), 10, observer=observer)
        cleanup.assert_called_once_with(process, False)
        self.assertEqual([e['phase'] for e in events], ['before_spawn', 'spawned', 'cleanup_observed'])
        self.assertEqual(old, {sig: signal.getsignal(sig) for sig in old})
        replay.assert_not_called()

    def test_mocked_final_fsync_overrun_leaves_only_unadmitted_artifacts(self):
        # Virtual files only: no fixture directory, process, arrays or real fsync.
        clock, files, active = [0.0], {}, [None]
        class MemoryFile(io.BytesIO):
            def close(self):
                pass
            def fileno(self):
                return 987654321
        class VirtualPath:
            def __init__(self, name):
                self.name = name
                self.parent = self
            def is_dir(self):
                return True
            def is_relative_to(self, other):
                return False
            def mkdir(self, **kwargs):
                pass
            def __truediv__(self, name):
                return VirtualPath(name)
            def open(self, mode):
                if mode != 'xb' or self.name in files:
                    raise AssertionError('fresh exclusive virtual output required')
                active[0] = self.name
                files[self.name] = MemoryFile()
                return files[self.name]
        public, output = VirtualPath('public'), VirtualPath('output')
        grade = mock.Mock(MAX_JSON=4194304, MAX_RESULT=262144)
        grade.ordinary_path.side_effect = lambda value: value
        sources = {'delivery': mock.Mock()}
        result = (b'{}', b'{}', b'{}', t.encode({'admission': dict(t.ADMISSION)}))
        def fsync(_):
            if active[0] == 'transport.json':
                clock[0] = 11.0
        with mock.patch.object(t, 'load_sources', return_value=(grade, sources)), \
                mock.patch.dict(sys.modules, {'numpy': types.ModuleType('numpy')}), \
                mock.patch.object(t.os.path, 'lexists', return_value=False), \
                mock.patch.object(t.os, 'chmod'), mock.patch.object(t.os, 'fsync', side_effect=fsync), \
                mock.patch.object(t.time, 'monotonic', side_effect=lambda: clock[0]), \
                mock.patch.object(t, 'run_participant', return_value=result), \
                self.assertRaisesRegex(ValueError, 'final acceptance'):
            t.operator_collect(public, 'direct_observation', ['/generated/participant'], public, output, 10)
        self.assertEqual(set(files), {'lifecycle.jsonl', 'submission.json', 'visual_receipt.json', 'replay.json', 'transport.json'})
        receipt = json.loads(files['transport.json'].getvalue())
        self.assertEqual(receipt['admission']['state'], 'unadmitted')
        self.assertFalse(receipt['admission']['artifacts_alone_admissible'])

    def test_mocked_pipe_closure_refuses_trailing_exit_group_and_stall(self):
        for kind in ('trailing', 'exit', 'group', 'stall'):
            process = self._process_fixture()
            if kind == 'exit':
                process.returncode = 2
            channel = object.__new__(t.PipeChannel)
            channel.process, channel.outfd, channel.errfd = process, 10, 11
            channel.err_open, channel.deadline = True, 10.0
            channel.stderr_bytes, channel.stderr_hash = 0, hashlib.sha256()
            with self.subTest(kind=kind), mock.patch.object(t.time, 'monotonic', return_value=11.0 if kind == 'stall' else 0.0), \
                    mock.patch.object(t.select, 'select', return_value=([10, 11], [], [])), \
                    mock.patch.object(t.os, 'read', return_value=b'x' if kind == 'trailing' else b''), \
                    mock.patch.object(t, 'group_exists', return_value=kind == 'group'), self.assertRaises(ValueError):
                channel.close_success()


if __name__ == '__main__':
    # Explicit trusted dependency root; no private data or source discovery.
    if len(sys.argv) > 1 and sys.argv[1].startswith('--implementations-root='):
        IMPLEMENTATIONS = Path(sys.argv.pop(1).split('=', 1)[1])
    else:
        IMPLEMENTATIONS = Path(__file__).resolve().parent.parent
    unittest.main(verbosity=2)
