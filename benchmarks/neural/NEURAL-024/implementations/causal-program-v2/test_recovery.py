"""Generated source/lifecycle controls; no Docker, real data or model calls."""
import contextlib
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

HERE = Path(__file__).absolute().parent
RUNTIME = 'authoring/rtt-neural-forecast-v1/causal-runtime-v1/'
LEGACY = '48ef3ea8f5dbfac57a4e0633d8245da59ff061a61cc5830d0b0c3e7e653e2299'
WRITTEN = 0


def module(path, name):
    value = types.ModuleType(name)
    value.__file__ = str(path)
    exec(compile(path.read_bytes(), str(path), 'exec'), value.__dict__)
    return value


r = module(HERE / 'recovery.py', '_test_recovery024')


def write(path, body):
    global WRITTEN
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    WRITTEN += len(body)


@contextlib.contextmanager
def original_modules(root, origin=None):
    old_path = sys.path[:]
    old_modules = dict(sys.modules)
    try:
        with patch.dict(os.environ, {'NEURAL024_DOCKER_HOST': 'unix:///operator/generated.sock',
                                     'NEURAL024_ORIGIN': repr(time.monotonic() if origin is None else origin)}):
            sys.path.insert(0, str(root / RUNTIME))
            common = module(root / RUNTIME / 'common.py', 'common')
            sys.modules['common'] = common
            protocol = module(root / RUNTIME / 'protocol.py', 'protocol')
            sys.modules['protocol'] = protocol
            profile = module(root / RUNTIME / 'rtt_profile.py', 'rtt_profile')
            sys.modules['rtt_profile'] = profile
            recovery = module(root / RUNTIME / 'rtt_recovery.py', 'rtt_recovery')
            sys.modules['rtt_recovery'] = recovery
            stream = module(root / RUNTIME / 'stream.py', 'stream')
            sys.modules['stream'] = stream
            runner = module(root / RUNTIME / 'run_program.py', '_original_runner024')
            controller = module(root / RUNTIME / 'controller.py', '_original_controller024')
            yield common, protocol, runner, controller
    finally:
        sys.path[:] = old_path
        for name in set(sys.modules) - set(old_modules):
            del sys.modules[name]
        for name, value in old_modules.items():
            if sys.modules.get(name) is not value:
                sys.modules[name] = value


class Controls(unittest.TestCase):
    def setUp(self):
        global WRITTEN
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'operator'
        result = r.materialize(self.root)
        WRITTEN += result['written_bytes']
        self.selected, _ = r.manifest()

    def grant(self):
        value = {'decision': 'authorize_one_neural024_causal_program_attempt', 'execution_authority': True,
                 'control': 'ordinary', 'freeze_sha256': self.selected['runtime_freeze']['sha256'],
                 'operator_docker_host': 'unix:///operator/generated.sock', 'prior_known_seconds': 2800}
        path = self.root / 'review.json'
        write(path, r.encode(value))
        return path, value

    def test_01_source_closure_and_unchanged_science(self):
        selected, captured = r.operator_source(self.root)
        self.assertEqual(len(captured), 51)
        self.assertEqual(len(selected['external_closure_files']), 18)
        self.assertEqual(set(selected['adaptations']), {
            'authoring/dmfc-timing/program-runner-v2/engine.py',
            'authoring/erp-neural-prediction-v1/reference-v1/runtime.py',
            'authoring/shared-program-runner-v2/QUALIFIED_IMPORTS.json', RUNTIME + 'run_program.py'})
        self.assertEqual(r.pin(captured['authoring/rtt-neural-forecast-v1/causal-science-v1/score_core.py'])['sha256'],
                         '20f79b56b4720696e74abd94e17ab4b4fc2a8b8039ef29a11921b3fc63c4ff39')
        self.assertEqual(r.pin(captured[RUNTIME + 'controller.py'])['sha256'],
                         'c084b444f6a4b682bcc15f0a57b7cc10c6157e323d8552e7cde97eb03ad7b1fb')
        self.assertFalse((self.root / 'artifacts-build').exists())
        with self.assertRaises(ValueError): r.materialize(self.root)

    def test_02_source_drift_and_import_cache_refused(self):
        path = self.root / RUNTIME / 'protocol.py'
        original = path.read_bytes()
        path.chmod(0o644)
        write(path, original + b'\n')
        with self.assertRaises(ValueError): r.operator_source(self.root)
        write(path, original)
        cache = path.parent / '__pycache__'
        cache.mkdir()
        with self.assertRaises(ValueError): r.operator_source(self.root)
        cache.rmdir()
        write(path.parent / 'unselected.py', b'raise RuntimeError("never imported")\n')
        with self.assertRaises(ValueError): r.operator_source(self.root)

    def test_03_captured_review_socket_and_environment(self):
        path, _ = self.grant()
        with patch.dict(os.environ, {'DOCKER_CONTEXT': 'wrong', 'DOCKER_HOST': 'wrong',
                                     'DOCKER_TLS_VERIFY': '1', 'PYTHONPATH': 'wrong'}):
            body, argv, env = r.dispatch(self.root, path, ['--program', '/operator/fixture.py'])
        self.assertEqual(r.pin(body), self.selected['files'][RUNTIME + 'run_program.py'])
        self.assertEqual(env['NEURAL024_DOCKER_HOST'], 'unix:///operator/generated.sock')
        self.assertEqual(env['NEURAL024_REVIEW_SHA256'], r.pin(path.read_bytes())['sha256'])
        self.assertNotIn('DOCKER_CONTEXT', env)
        self.assertNotIn('DOCKER_HOST', env)
        self.assertNotIn('DOCKER_TLS_VERIFY', env)
        self.assertNotIn('PYTHONPATH', env)
        self.assertEqual(argv[:3], [str(self.root / RUNTIME / 'run_program.py'), '--control', 'ordinary'])

    def test_04_bad_socket_authority_and_old_cost_floor(self):
        path, value = self.grant()
        for field, bad in (('operator_docker_host', 'tcp://example.invalid:2375'),
                           ('operator_docker_host', 'unix:///operator/../socket'),
                           ('operator_docker_host', 'unix:///operator/a\nsocket'),
                           ('execution_authority', False), ('freeze_sha256', LEGACY),
                           ('prior_known_seconds', 2020)):
            write(path, r.encode({**value, field: bad}))
            with self.assertRaises(ValueError): r.dispatch(self.root, path, [])

    def test_05_real_source_import_and_same_review_binding(self):
        path, value = self.grant()
        with original_modules(self.root) as (_, __, runner, ___):
            # The first authority checks refuse the changed review before any
            # external source/evidence or original payload path is inspected.
            with patch.dict(os.environ, {'NEURAL024_REVIEW_SHA256': '0' * 64}):
                with self.assertRaisesRegex(ValueError, 'Same captured'):
                    runner.source_gate(types.SimpleNamespace(review=path))
        r.operator_source(self.root)  # imports did not create a pyc/cache file

    def test_06_prior_receipt_and_allocation_joins_are_not_replaced_by_floor(self):
        with original_modules(self.root) as (_, __, runner, ___):
            prior = {'candidate_id': 'NEURAL-024', 'task_family': 'rtt_neural_causal_forecast',
                     'source_freeze_sha256': LEGACY, 'historical_lifetime_complete': False,
                     'all_owned_absent': True, 'all_activated_groups_absent': True,
                     'charged_seconds': 780, 'known_family_allowances_seconds_after': 2800}
            review = {'prior_receipt': 'closed', 'prior_known_seconds': 2800, 'prospective_after_seconds': 3580,
                      'budget_allocation': 'allocation', 'other_reserve_bytes': 352000000,
                      'program': {'sha256': '1' * 64}, 'method': {'sha256': '2' * 64},
                      'control': 'ordinary', 'output_path': 'artifacts-build/generated'}
            freeze = self.selected['runtime_freeze']['sha256']
            allocation = {'candidate_id': 'NEURAL-024', 'authorized': True, 'whole_seconds': 780,
                          'work_seconds': 720, 'candidate_seconds': 600, 'cleanup_seconds': 60,
                          'own_reserve_bytes': 176000000, 'other_reserve_bytes': 352000000,
                          'prior_known_seconds': 2800, 'prospective_after_seconds': 3580,
                          'historical_lifetime_complete': False, 'program': review['program'],
                          'method': review['method'], 'control': 'ordinary', 'output_path': review['output_path'],
                          'freeze_sha256': freeze}
            def pinned(key, _): return prior if key == 'closed' else allocation
            with patch.object(runner, 'pinned', pinned), patch.object(runner, 'assets', lambda: {'reference_receipt': 'old-reference'}):
                self.assertEqual(runner.prior_gate(review, freeze), 2800)
                for field, bad in (('source_freeze_sha256', 'f' * 64), ('all_owned_absent', False),
                                   ('all_activated_groups_absent', False), ('charged_seconds', 779),
                                   ('known_family_allowances_seconds_after', 2900)):
                    previous = prior[field]
                    prior[field] = bad
                    with self.assertRaises(ValueError): runner.prior_gate(review, freeze)
                    prior[field] = previous
                allocation['prior_known_seconds'] = 2020
                with self.assertRaises(ValueError): runner.prior_gate(review, freeze)

    def episode(self, fail=None):
        global WRITTEN
        run = self.root / ('generated-' + (fail or 'complete'))
        prepared = run / 'prepared'
        prepared.mkdir(parents=True)
        with original_modules(self.root) as (common, p, _, controller):
            body = b''.join(p.wire({'target_bin': 3000 + i, 'counts': [0] * 96}) for i in range(p.ROUNDS))
            obs = prepared / 'observations.jsonl'
            write(obs, body)
            files = {'observations.jsonl': common.lock(body)}
            edges = [60 + i * .02 for i in range(p.ROUNDS + 1)]
            schedule = {'intervals': [[edges[i], edges[i + 1]] for i in range(p.ROUNDS)]}
            tracker = {'syncs': 0, 'reads': 0, 'predicts': 0, 'stopped': False, 'fds': {}}

            class Budget:
                def check(self, _): pass
                def write(self, name, data, **kwargs): write(Path(name), data)

            class Engine:
                def __init__(self, *args): pass
                def create_task(self, *args): return None, {'generated': True}
                def inspect(self, *args):
                    return {'State': {'Status': 'exited', 'Running': False, 'Pid': 0, 'ExitCode': 0, 'OOMKilled': False}}

            class Stream:
                def __init__(self, *args):
                    self.next = {'status': 'ready'}
                    self.out = self.stdout = self.stderr = b''
                def send(self, raw):
                    message = json.loads(raw)
                    if message['status'] == 'initialize':
                        self.next = {'status': 'initialized', 'protocol': p.PROTOCOL}
                    elif message['status'] == 'predict':
                        sequence = message['sequence']
                        self_outer.assertEqual(sequence, tracker['predicts'])
                        self_outer.assertEqual(message['observation'], None if sequence == 0 else
                                               {'target_bin': 2999 + sequence, 'counts': [0] * 96})
                        means = [1.] * (95 if fail == 'partial' and sequence == 10 else 96)
                        self.next = {'sequence': sequence, 'nonce': message['nonce'], 'mean_counts': means}
                        tracker['predicts'] += 1
                    else:
                        self_outer.assertEqual(message['observation']['target_bin'], 25099)
                        tracker['stopped'] = True
                        self.next = {'status': 'stopped'}
                def line(self): return p.wire(self.next)
                def finish(self): pass
                def close(self): return {'attach_cli_reaped': True}

            class Handle:
                def __init__(self, value, name): self.value, self.name = value, name
                def __getattr__(self, name): return getattr(self.value, name)
                def __enter__(self): return self
                def __exit__(self, *args): return self.value.__exit__(*args)
                def write(self, data):
                    global WRITTEN
                    count = self.value.write(data)
                    WRITTEN += count
                    return count
                def readline(self, cap):
                    self_outer.assertEqual(tracker['syncs'], tracker['reads'] + 1)
                    tracker['reads'] += 1
                    return self.value.readline(cap)

            self_outer = self
            original_open, original_fdopen = os.open, os.fdopen
            def opened(path, *args, **kwargs):
                fd = original_open(path, *args, **kwargs)
                tracker['fds'][fd] = str(path)
                return fd
            def fdopened(fd, *args, **kwargs):
                value = original_fdopen(fd, *args, **kwargs)
                name = tracker['fds'].get(fd, '')
                return Handle(value, name) if name in (str(obs), str(run / 'candidate/commits.jsonl')) else value
            def synced(fd):
                if tracker['fds'].get(fd) == str(run / 'candidate/commits.jsonl') and os.fstat(fd).st_size:
                    # This is a generated call-order check, not a kernel fsync
                    # qualification or timing measurement.
                    tracker['syncs'] += 1
            with patch.object(controller, 'StreamEngine', Engine), patch.object(controller, 'Stream', Stream), \
                 patch.object(controller, 'mapping', lambda *_: {}), \
                 patch.object(controller, 'remove', lambda *_: [{'absence_verified': True}]), \
                 patch.object(os, 'open', opened), patch.object(os, 'fdopen', fdopened), patch.object(os, 'fsync', synced):
                result = controller.participant(run, schedule, files, Budget(), time.monotonic() + 700, {})
            return result, tracker

    def test_07_complete_original_22100_round_loop_and_commit_before_read(self):
        result, tracker = self.episode()
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['committed'], 22100)
        self.assertEqual(result['feedback_rows_sent'], 22100)
        self.assertEqual(tracker['reads'], 22100)
        self.assertEqual(tracker['predicts'], 22100)
        self.assertTrue(tracker['stopped'])
        self.assertTrue(result['all_owned_absent'])
        self.assertTrue(result['attach_cli_reaped'])

    def test_08_partial_vector_never_reveals_current_count(self):
        result, tracker = self.episode('partial')
        self.assertEqual(result['status'], 'invalid_or_failed_candidate')
        self.assertEqual(result['committed'], 10)
        self.assertEqual(tracker['reads'], 10)
        self.assertFalse(tracker['stopped'])

    def test_09_slow_source_startup_does_not_refresh_original_clock(self):
        origin = time.monotonic() - 45
        with original_modules(self.root, origin=origin) as (_, __, runner, ___):
            self.assertEqual(runner.START, origin)
            self.assertEqual(runner.END, origin + 780)
            self.assertLess(runner.START + runner.WORK - time.monotonic(), 675)
            self.assertEqual(runner.WHOLE, 780)
        with self.assertRaisesRegex(ValueError, 'Original portable launch origin'):
            with original_modules(self.root, origin=time.monotonic()-61): pass


if __name__ == '__main__':
    print(json.dumps({'python': platform.python_version(), 'authentic_payloads': 0, 'native_runs': 0,
                     'model_calls': 0, 'fsync_scope': 'generated invocation ordering, not kernel durability'}))
    result = unittest.main(exit=False, verbosity=2).result
    print(json.dumps({'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                     'known_generated_write_bytes': WRITTEN, 'temporary_fixtures_removed': True,
                     'counter_scope': 'all source materialization plus generated frame/journal/budget writes'}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
