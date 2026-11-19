"""Affected generated controls only; no packets, waveforms, models or native child.

The coordinator selects one source-pool campaign. The author does not execute
this module. All successful callback values below are generated protocol fixtures,
not observed delivery, predictions or scientific results. Fixture disk writes: 0.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import types

HERE = Path(__file__).resolve().parent
DRIVER_PATH = HERE / 'driver.py'
ADAPTER_PATH = HERE.parent / 'full32-paired-runtime-v1/runtime.py'
ADAPTER_PIN = (22886, 'dd51078480d8bd3ada5e063e02b7cadc8eb4c95807c7c55d6b9530875ca3622f')


def load_source(name, path, expected=None):
    body = path.read_bytes()
    if expected is not None and (len(body), hashlib.sha256(body).hexdigest()) != expected:
        raise ValueError('Selected generated control adapter changed')
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    exec(compile(body, str(path), 'exec'), module.__dict__)
    return module


D = load_source('full6400_delivery_control_subject', DRIVER_PATH)
A = load_source('full6400_delivery_control_adapter', ADAPTER_PATH, ADAPTER_PIN)
NO = 'GENERATED NO TOOLS.'
YES = 'GENERATED QUERY TOOLS ALLOWED.'
DEMOS = '\n'.join('FULL GENERATED DEMONSTRATION %d: label%d; all declared samples.' % (i, i % 2)
                  for i in range(4))


def ids(count):
    return tuple('q-%032x' % i for i in range(count))


def context(identifier, condition):
    prompt = DEMOS + '\nQUERY ' + identifier + ': complete generated query.\n' + (NO if condition == D.CONDITIONS[0] else YES)
    return {'trial_id': identifier, 'condition': condition, 'prompt': prompt,
            'context_sha256': hashlib.sha256(prompt.encode()).hexdigest()}


def successful(ordinal, program, pid=None):
    """Generated complete closure structure for the existing acceptance helper."""
    pid = 10000 + ordinal if pid is None else pid
    envelope = {key: program[key] for key in ('trial_id', 'condition', 'context_sha256')}
    envelope.update(status='ok', error=None, response=json.dumps({
        'trial_id': program['trial_id'], 'target_probability': 0.5}))
    end = {'schema': 'erp-full6400-owned-episode-v1', 'generated_protocol_only': False,
           'diagnostic_mode': 'concurrent_bounded_stderr_v1', 'status': 'ok', 'pid': pid,
           'trial_id': program['trial_id'], 'condition': program['condition'],
           'context_sha256': program['context_sha256'], 'returncode': 0,
           'normal_exit_observed': True, 'stdout_EOF_observed': True,
           'owned_cleanup': {'pid': pid, 'cleanup_complete': True, 'reaped': True,
                             'group_absence_observed': True},
           'stderr_capture': {'eof_observed': True, 'reader_joined': True, 'closed': True,
                              'overflow': False, 'error': None, 'observed_bytes': 0,
                              'retained_bytes': 0}}
    return envelope, end, D.pin(D.encode({'generated_case_ordinal': ordinal,
                                       'trial_id': program['trial_id']}))


class Full6400DeliveryControls(unittest.TestCase):
    def run_case(self, count=3, **changes):
        options = dict(trial_ids=ids(count), context_for=context, episode_call=successful,
                       projection_sink=lambda *args: None, status_sink=lambda row: None,
                       budget=D.Budget(), no_tools=NO, program_tools=YES, adapter=A,
                       now=lambda: 0.0, work_deadline=3600.0, continuity_bytes=321,
                       expected_count=count)
        options.update(changes)
        return D.drive_roster(**options)

    def test_full6400_census_and_exact_matched_information(self):
        calls, projected, journal = [], [], []
        def project(ordinal, direct, commitment):
            self.assertEqual(set(direct), {'trial_id', 'condition', 'prompt', 'context_sha256'})
            self.assertEqual(direct, context('q-%032x' % ordinal, D.CONDITIONS[0]))
            self.assertIn(DEMOS, direct['prompt'])
            self.assertEqual(direct['prompt'].count('FULL GENERATED DEMONSTRATION'), 4)
            self.assertEqual(commitment['direct_context'], D.pin(direct['prompt'].encode()))
            self.assertFalse(commitment['direct_model_called'])
            projected.append(ordinal)
        def invoke(ordinal, program):
            self.assertEqual(set(program), {'trial_id', 'condition', 'prompt', 'context_sha256'})
            self.assertEqual(program, context('q-%032x' % ordinal, D.CONDITIONS[1]))
            self.assertEqual(program['prompt'].replace(YES, NO), context(program['trial_id'], D.CONDITIONS[0])['prompt'])
            self.assertNotIn('roster', program)
            self.assertNotIn('person', program)
            self.assertNotIn('answers', program)
            calls.append(ordinal)
            return successful(ordinal, program)
        result = self.run_case(6400, projection_sink=project, episode_call=invoke,
                               status_sink=lambda row: journal.append((row['ordinal'], row['status'])))
        self.assertTrue(result['complete'])
        self.assertEqual(result['counts'], {'closed_pass': 6400, 'failed_closed': 0,
                                           'failed_unresolved': 0, 'unattempted': 0})
        self.assertEqual([row['trial_id'] for row in result['census']], list(ids(6400)))
        self.assertEqual(calls, list(range(6400)))
        self.assertEqual(projected, calls)
        self.assertEqual(journal, [(i, state) for i in range(6400) for state in ('dispatching', 'closed_pass')])
        self.assertEqual(result['direct_projection_count'], 6400)
        self.assertEqual(result['process_dispatch_count'], 6400)
        self.assertTrue(result['all_exercised_children_closed'])
        self.assertEqual(result['read_bytes_conservatively_charged'], 6400 * (D.QUERY_READ + D.PIPE_READ + 321))
        self.assertEqual(result['artifact_bytes_conservatively_reserved'],
                         6400 * (D.DIRECT_WRITE + D.EPISODE_WRITE + D.COMMITMENT_WRITE))

    def test_full_roster_refuses_missing_duplicate_unsorted_or_nonopaque_ids(self):
        good = ids(6400)
        variants = [good[:-1], good + (good[-1],), (good[0],) + good[:-1],
                    tuple(reversed(good)), ('sub-008',) + good[1:]]
        for variant in variants:
            with self.subTest(reason=variant[:2], count=len(variant)):
                with self.assertRaises(ValueError):
                    D.prepare_census(variant)
        census = D.prepare_census(good)
        self.assertEqual(len(census), 6400)
        self.assertTrue(all(row['status'] == 'unattempted' and row['pid'] is None for row in census))

    def test_full_demo_or_projection_metadata_changes_refuse_before_dispatch(self):
        for change in ('drop_demo', 'extra_permission', 'extra_metadata'):
            calls = []
            def bad_context(identifier, condition):
                value = context(identifier, condition)
                if condition == D.CONDITIONS[1]:
                    if change == 'drop_demo':
                        value['prompt'] = value['prompt'].replace('FULL GENERATED DEMONSTRATION 3', 'MISSING')
                    elif change == 'extra_permission':
                        value['prompt'] += YES
                    else:
                        value['manifest'] = 'GENERATED OPERATOR-ONLY VALUE'
                    value['context_sha256'] = hashlib.sha256(value['prompt'].encode()).hexdigest()
                return value
            with self.subTest(change=change):
                result = self.run_case(context_for=bad_context,
                                       episode_call=lambda *args: calls.append(args))
                self.assertFalse(result['complete'])
                self.assertEqual(calls, [])
                self.assertEqual(result['counts']['failed_closed'], 1)
                self.assertEqual(result['counts']['unattempted'], 2)

    def test_first_failure_stops_and_preserves_closed_or_unresolved_tail(self):
        for failure in ('failed_response', 'stderr_exhausted', 'unresolved_group', 'callback_interrupted'):
            calls = []
            def invoke(ordinal, program):
                calls.append(ordinal)
                if ordinal == 1 and failure == 'callback_interrupted':
                    raise InterruptedError('Generated interruption after dispatch entry')
                envelope, end, receipt = successful(ordinal, program)
                if ordinal == 1:
                    if failure == 'failed_response':
                        envelope.update(status='error', response=None, error='generated_first_response_failure')
                        end.update(status='error', returncode=2)
                    elif failure == 'stderr_exhausted':
                        end['stderr_capture'].update(eof_observed=False, overflow=True,
                                                     error='stderr_read_limit', observed_bytes=65536, retained_bytes=16384)
                    else:
                        end['owned_cleanup']['group_absence_observed'] = False
                return envelope, end, receipt
            with self.subTest(failure=failure):
                result = self.run_case(episode_call=invoke)
                self.assertEqual(calls, [0, 1])
                self.assertFalse(result['complete'])
                self.assertEqual(result['census'][0]['status'], 'closed_pass')
                self.assertEqual(result['census'][1]['status'],
                                 'failed_closed' if failure in ('failed_response', 'stderr_exhausted') else 'failed_unresolved')
                self.assertEqual(result['census'][2]['status'], 'unattempted')
                self.assertEqual(result['all_exercised_children_closed'], failure in ('failed_response', 'stderr_exhausted'))

        # Interrupting final aggregation must not replace the caller's live
        # inventory with its initial all-unattempted snapshot.
        class AggregateInterruptBudget:
            def __init__(self):
                self.inner = D.Budget()
            @property
            def cases_reserved(self):
                return self.inner.cases_reserved
            def reserve_case(self, count):
                self.inner.reserve_case(count)
            @property
            def read_charged(self):
                raise InterruptedError('Generated final aggregation interruption')
            @property
            def write_reserved(self):
                return self.inner.write_reserved
        shared = D.prepare_census(ids(3), expected_count=3)
        def interrupted_episode(ordinal, program):
            if ordinal == 1:
                raise InterruptedError('Generated entered-episode interruption')
            return successful(ordinal, program)
        with self.assertRaises(InterruptedError):
            self.run_case(census=shared, budget=AggregateInterruptBudget(),
                          episode_call=interrupted_episode)
        self.assertEqual([row['status'] for row in shared],
                         ['closed_pass', 'failed_unresolved', 'unattempted'])
        self.assertFalse(shared[1]['closure_complete'])
        self.assertIsNotNone(shared[0]['case_receipt'])

    def test_absolute_deadline_is_not_reset_for_each_case(self):
        clock, calls = [0.0], []
        def invoke(ordinal, program):
            calls.append(ordinal)
            clock[0] = 35.0
            return successful(ordinal, program)
        result = self.run_case(now=lambda: clock[0], work_deadline=69.0, episode_call=invoke)
        self.assertEqual(calls, [0])
        self.assertEqual(result['counts']['closed_pass'], 1)
        self.assertEqual(result['counts']['unattempted'], 2)
        self.assertFalse(result['complete'])
        self.assertEqual(result['stop_reason']['ordinal'], 1)
        self.assertEqual(result['census'][1]['pid'], None)

    def test_cumulative_read_write_reservations_are_atomic_and_precede_context(self):
        for invalid in (-1, True, '321', 1.5):
            budget = D.Budget()
            with self.assertRaises(ValueError):
                budget.reserve_case(invalid)
            self.assertEqual((budget.read_charged, budget.write_reserved, budget.cases_reserved), (0, 0, 0))
        writes = []
        def fake_write(path, body, budget, reserved):
            writes.append((path, body, reserved))
            if body == b'fail':
                raise OSError('Generated partial write failure')
            return D.pin(body)
        writer = D.ReservedWriter(types.SimpleNamespace(write_new=fake_write), 8)
        writer.write('generated-in-memory-only', b'abcd')
        with self.assertRaises(OSError):
            writer.write('generated-in-memory-only', b'fail')
        self.assertEqual(writer.written, 8)
        with self.assertRaises(ValueError):
            writer.write('generated-in-memory-only', b'x')
        self.assertEqual(len(writes), 2)
        self.assertTrue(all(row[2] is True for row in writes))
        for failing_charge in ((81, 0), (0, 71), (-1, 0), (0, True)):
            budget = D.Budget(100, 100)
            budget.reserve(20, 30)
            with self.assertRaises(ValueError):
                budget.reserve(*failing_charge)
            self.assertEqual((budget.read_charged, budget.write_reserved, budget.cases_reserved), (20, 30, 0))
        for exhausted in ('read', 'write'):
            case_read = D.QUERY_READ + D.PIPE_READ + 321
            case_write = D.DIRECT_WRITE + D.EPISODE_WRITE + D.COMMITMENT_WRITE
            budget = D.Budget(case_read if exhausted == 'read' else case_read * 3,
                              case_write if exhausted == 'write' else case_write * 3)
            contexts, calls = [], []
            def projected(identifier, condition):
                contexts.append((identifier, condition))
                return context(identifier, condition)
            def invoke(ordinal, program):
                calls.append(ordinal)
                return successful(ordinal, program)
            result = self.run_case(budget=budget, context_for=projected, episode_call=invoke)
            self.assertEqual(calls, [0])
            self.assertEqual(len(contexts), 2)
            self.assertEqual(budget.cases_reserved, 1)
            self.assertEqual((budget.read_charged, budget.write_reserved), (case_read, case_write))
            self.assertEqual(result['counts']['unattempted'], 2)
            self.assertFalse(result['complete'])

    def test_durable_sink_failure_prevents_next_or_current_native_dispatch(self):
        for point in ('projection', 'dispatching', 'closed_pass'):
            calls = []
            def project(*args):
                if point == 'projection':
                    raise OSError('Generated bounded output failure')
            def status(row):
                if row['status'] == point:
                    raise OSError('Generated journal durability failure')
            def invoke(ordinal, program):
                calls.append(ordinal)
                return successful(ordinal, program)
            with self.subTest(point=point):
                result = self.run_case(projection_sink=project, status_sink=status, episode_call=invoke)
                self.assertEqual(calls, [0] if point == 'closed_pass' else [])
                self.assertFalse(result['complete'])
                self.assertIsNotNone(result['stop_reason'])
                self.assertTrue(all(row['status'] == 'unattempted' for row in result['census'][1:]))

    def test_recycled_pid_is_not_context_replay_permission(self):
        # PID numbers can legitimately recycle; context-bound independent closure
        # receipts and actual per-call Popen ownership establish process instances.
        result = self.run_case(episode_call=lambda i, p: successful(i, p, pid=12345))
        self.assertTrue(result['complete'])
        active_calls = []
        def uncleared(ordinal, program):
            active_calls.append(ordinal)
            envelope, end, receipt = successful(ordinal, program, pid=12345)
            end['owned_cleanup']['group_absence_observed'] = False
            return envelope, end, receipt
        unsafe = self.run_case(episode_call=uncleared)
        self.assertEqual(active_calls, [0])
        self.assertEqual(unsafe['counts']['failed_unresolved'], 1)
        self.assertEqual(unsafe['counts']['unattempted'], 2)
        self.assertFalse(unsafe['all_exercised_children_closed'])
        first, calls = [], []
        def replay(ordinal, program):
            calls.append(ordinal)
            if ordinal == 0:
                value = successful(ordinal, program)
                first.append(value)
                return value
            return first[0]
        rejected = self.run_case(episode_call=replay)
        self.assertEqual(calls, [0, 1])
        self.assertFalse(rejected['complete'])
        self.assertEqual(rejected['counts']['closed_pass'], 1)
        self.assertEqual(rejected['counts']['failed_closed'], 1)
        self.assertEqual(rejected['counts']['unattempted'], 1)

    def test_owner_clock_handoff_consumes_admission_time_without_real_timer(self):
        # Replace the complete signal object: this never changes the source-pool
        # process's real handlers/timer and never enters packet/native work.
        def exercise(now, started=100.0, deadline=4300.0, existing=(0.0, 0.0)):
            timers, handlers, entered = [], [], []
            fake_signal = types.SimpleNamespace(
                ITIMER_REAL=1, SIGALRM=14, SIGTERM=15, SIGHUP=1, SIGINT=2,
                getitimer=lambda kind: existing,
                setitimer=lambda *args: timers.append(args),
                signal=lambda signum, handler: handlers.append((signum, handler)) or ('original-' + str(signum)))
            def selected_work(config, begin, end):
                entered.append((config, begin, end))
                return {'generated_clock_control_only': True}
            with patch.object(D, 'signal', fake_signal), \
                 patch.object(D, 'time', types.SimpleNamespace(monotonic=lambda: now)), \
                 patch.object(D, 'validate_config', lambda config: config), \
                 patch.object(D, '_run', selected_work):
                try:
                    value = D.run({'generated_clock_only': True},
                                  operation_started=started, operation_deadline=deadline)
                except ValueError:
                    return None, timers, handlers, entered
            return value, timers, handlers, entered
        value, timers, handlers, entered = exercise(137.0)
        self.assertEqual(value, {'generated_clock_control_only': True})
        self.assertEqual(timers, [(1, 4043.0), (1, 0)])
        self.assertEqual(entered, [({'generated_clock_only': True}, 100.0, 4180.0)])
        self.assertEqual(len(handlers), 8)
        for options in ({'now': 3666.0}, {'now': 137.0, 'deadline': 4301.0},
                        {'now': 137.0, 'started': 138.0, 'deadline': 4338.0},
                        {'now': 137.0, 'deadline': float('inf')},
                        {'now': 137.0, 'existing': (1.0, 0.0)}):
            with self.subTest(options=options):
                value, timers, handlers, entered = exercise(**options)
                self.assertIsNone(value)
                self.assertEqual((timers, handlers, entered), ([], [], []))

    def test_exact_selected_global_resource_and_retention_profile(self):
        self.assertEqual(D.COUNT, 6400)
        self.assertEqual(D.LIMITS, {'work_seconds': 3600, 'whole_seconds': 4200,
                                  'episode_seconds': 30, 'cleanup_seconds': 5,
                                  'read_bytes': 6 * 1024**3, 'write_bytes': 6 * 1024**3 - 2 * 1024**2,
                                  'owner_settlement_seconds': 120})
        self.assertEqual(D.BASE_PACKET_READ, 5374989)
        self.assertEqual((D.QUERY_READ, D.PIPE_READ), (120000, 69637))
        self.assertEqual((D.DIRECT_WRITE, D.EPISODE_WRITE, D.COMMITMENT_WRITE), (196608, 524288, 4096))
        self.assertEqual(D.CENSUS_RESERVE, 16 * 1024**2)
        self.assertEqual(D.CLIENT_CAP, 65536)
        self.assertLess(6400 * (D.DIRECT_WRITE + D.EPISODE_WRITE + D.COMMITMENT_WRITE) + D.CENSUS_RESERVE,
                        D.LIMITS['write_bytes'])


if __name__ == '__main__':
    unittest.main()
