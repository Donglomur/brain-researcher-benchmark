"""Generated tests of the new entry boundary, never authentic data or fits."""
import array
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import types
import unittest

HERE = Path(__file__).resolve().parent
SOURCE = Path(os.environ.get('FORAGING_EXISTING_SOURCE_ROOT', str(HERE.parent / 'program'))).resolve()

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

cli = load('_foraging_source_api_cli_test', HERE / 'cli.py')
common = load('_foraging_common_cli_test', SOURCE / 'common.py')

class Failure(ValueError):
    def __init__(self, message, attempted, completed):
        super().__init__(message)
        self.attempted_fits = attempted
        self.completed_sessions = completed

class Spy:
    AUTHOR_BYTES = 6
    AUTHOR_SHA256 = hashlib.sha256(b'author').hexdigest()
    ReplayFailure = Failure
    def __init__(self, behavior='complete'):
        self.behavior, self.calls = behavior, 0
    def replay_prepared(self, prepared, source, budget, capacity):
        self.calls += 1
        if self.behavior == 'fail':
            raise Failure('generated work failure', 17, 3)
        if self.behavior == 'unknown':
            raise RuntimeError('generated unknown interruption')
        ids = [r['session_id'] for r in prepared['records']]
        vectors = {sid: array.array('d', [.5] * 10) for sid in ids}
        if self.behavior == 'missing_last':
            del vectors[ids[-1]]
        if self.behavior == 'nonfinite_last':
            vectors[ids[-1]][-1] = float('nan')
        return {'schema': 'foraging_source_api_real_branch_v1', 'task_id': common.TASK,
                'completed_real_fits': 200, 'sessions': {sid: {'rows': 10} for sid in ids},
                'output_numeric_bytes': 3200, 'source_shuffle_companions_executed': False,
                'paper_reproduced': None, 'paper_win': None, 'improvement_ready': False}, vectors

class CallerBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.ids = [f'{i:024x}' for i in range(40)]
        prepared = {'records': [{'session_id': sid, 'rows': 10} for sid in self.ids]}
        raw = common.encode(prepared)
        (self.root / 'prepared.json').write_bytes(raw)
        (self.root / 'author.py').write_bytes(b'author')
        self.limits = {'read_bytes': 2097152, 'write_bytes': 2097152,
                       'retained_bytes': 2097152, 'other_future_bytes': 0,
                       'free_floor_bytes': 1, 'wall_seconds': 60}
        self.selection = {'schema': cli.SCHEMA, 'task_id': common.TASK, 'limits': self.limits,
                          'prepared': {'path': str(self.root/'prepared.json'), **common.pin(raw)},
                          'author_source': {'path': str(self.root/'author.py'), **common.pin(b'author')},
                          'output_root': str(self.root/'output'), 'output_numeric_capacity_bytes': 3200,
                          'metadata_cap_bytes': 262144, 'component_scope_acknowledged': True}
        self.state = {'stage': 'authority_admission', 'attempted_fits': 0, 'completed_sessions': 0}
    def tearDown(self):
        self.temp.cleanup()
    def execute(self, spy):
        self.modules = {'common': common, 'author_replay': spy}
        return cli._execute(self.selection, common.Budget(dict(self.limits), time.monotonic()),
                            self.modules, self.state)
    def test_complete_all40_outputs_keep_component_scope(self):
        spy = Spy()
        result = self.execute(spy)
        out = self.root/'output'
        manifest = json.loads((out/'COMPONENT_RESULT.json').read_bytes())
        self.assertEqual(spy.calls, 1)
        self.assertEqual(result['completed_real_fits'], 200)
        self.assertEqual(set(manifest['probabilities']), set(self.ids))
        self.assertEqual(len(list(out.glob('*.f64'))), 40)
        for sid in self.ids:
            body = (out/(sid+'.f64')).read_bytes()
            self.assertEqual(body, array.array('d', [.5]*10).tobytes())
            self.assertEqual(hashlib.sha256(body).hexdigest(), manifest['probabilities'][sid]['sha256'])
        self.assertIsNone(manifest['paper_reproduced'])
        self.assertIsNone(manifest['paper_win'])
        self.assertIs(manifest['overall_benchmark_ready'], False)
    def test_last_session_and_nonfinite_fail_before_any_export(self):
        for behavior in ['missing_last', 'nonfinite_last']:
            with self.subTest(behavior=behavior):
                with self.assertRaises(ValueError): self.execute(Spy(behavior))
                self.assertFalse((self.root/'output').exists())
    def test_cumulative_numeric_cap_and_existing_output_refuse(self):
        self.selection['output_numeric_capacity_bytes'] = 3199
        with self.assertRaises(ValueError): self.execute(Spy())
        self.assertFalse((self.root/'output').exists())
        self.selection['output_numeric_capacity_bytes'] = 3200
        (self.root/'output').mkdir()
        spy = Spy()
        with self.assertRaises(ValueError): self.execute(spy)
        self.assertEqual(spy.calls, 0)
    def test_failed_fit_counts_and_unknown_counts_stay_honest(self):
        for behavior, attempted, completed in [('fail',17,3), ('unknown',None,None)]:
            with self.subTest(behavior=behavior):
                spy = Spy(behavior)
                try: self.execute(spy)
                except Exception as exc: result = cli._failure(exc, self.state, self.modules)
                else: self.fail('failure was not raised')
                self.assertEqual(result['attempted_fits'], attempted)
                self.assertEqual(result['completed_sessions'], completed)
                self.assertFalse(result['partial_output_is_success'])
                self.assertFalse((self.root/'output').exists())
    def test_private_diagnostic_is_bounded_without_formatting(self):
        class Unprintable(Exception):
            def __str__(self): raise RuntimeError('formatting must not run')
        r = cli._failure(Unprintable(object()), self.state, {})
        self.assertIsNone(r['message_prefix'])
        r = cli._failure(ValueError('x'*3000), self.state, {})
        self.assertEqual(len(r['message_prefix']),1024)
        self.assertTrue(r['message_truncated'])
        self.assertLess(len(json.dumps(r).encode()), cli.DIAGNOSTIC_BYTES)
    def test_real_cli_source_refusal_before_authority_or_private_input(self):
        fake = self.root/'fake_source'; fake.mkdir()
        (fake/'common.py').write_text('raise RuntimeError("must not execute")')
        result = subprocess.run([sys.executable,'-B',str(HERE/'cli.py'),'--source-root',str(fake),
                                 '--authority',str(self.root/'not_present.json'),
                                 '--authority-sha256','0'*64], capture_output=True, timeout=10)
        self.assertEqual(result.returncode,2)
        report = json.loads(result.stdout)
        self.assertEqual(report['stage'],'source_capture')
        self.assertEqual(report['attempted_fits'],0)
        self.assertEqual(report['completed_sessions'],0)
        self.assertFalse(report['partial_output_is_success'])
        self.assertEqual(result.stderr,b'')
        self.assertNotIn('must not execute',result.stdout.decode())
        result = subprocess.run([sys.executable,'-B',str(HERE/'cli.py'),'--source-root',str(SOURCE),
                                 '--authority',str(self.root/'not_present.json'),
                                 '--authority-sha256','0'*64], capture_output=True, timeout=10)
        self.assertEqual(result.returncode,2)
        report = json.loads(result.stdout)
        self.assertEqual(report['stage'],'authority_admission')
        self.assertEqual(report['attempted_fits'],0)
        self.assertEqual(report['completed_sessions'],0)
        self.assertEqual(result.stderr,b'')

if __name__ == '__main__':
    unittest.main()
