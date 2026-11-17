"""RAM-only controls. Never execute authentic supervisor, Docker, arrays or a model."""
import argparse
import ast
import copy
import hashlib
from pathlib import Path
import types
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
m = types.ModuleType('neural069_generated_adapter')
m.__file__ = str(HERE/'run_program.py')
exec(compile((HERE/'run_program.py').read_bytes(), m.__file__, 'exec'), m.__dict__)


def review():
    return {'schema': 'neural069_registration_review_v1', 'approved': True, 'task_id': 'NEURAL-069',
            'source': {'adapter_manifest': {'bytes': 1000, 'sha256': 'a'*64}, 'original_manifest': dict(m.DONOR_PIN)},
            'program': {'path': '/invented/program.py', **m.pin(b'pass')},
            'commit': {'path': '/invented/commit', 'metadata': {'bytes': 500, 'sha256': 'b'*64}},
            'package': '/invented/package', 'output': '/invented/output', 'docker_socket': '/invented/docker.sock',
            'environment': {'PATH': '/invented/bin', 'DOCKER_CONFIG': None, 'DOCKER_TLS_VERIFY': None, 'DOCKER_CERT_PATH': None},
            'resources': {'candidate_seconds': 20, 'memory_bytes': 536870912, 'cpu': 1,
                          'attempt_retained_and_write_bytes': 20000000, 'existing_commit_cap_bytes': 300000,
                          'adapter_read_cap_bytes': 1048576, 'free_floor_bytes': 21474836480, 'other_bytes': 17}}


def check(v, other=17):
    return m.validate_review(v, program='/invented/program.py', output='/invented/output', other=other)


def lock():
    return {'cases': [{'id': 'invented-'+str(i)} for i in range(80)]}


def commit():
    return {'schema': 'neural069_program_commit_v1', 'task_id': 'NEURAL-069', 'program': m.pin(b'pass'),
            'source_manifest': dict(m.DONOR_PIN), 'lock': dict(m.LOCK_PIN), 'image': m.IMAGE,
            'candidate_seconds': 20, 'memory_bytes': 536870912, 'cpu': 1,
            'full_cases': [x['id'] for x in lock()['cases']]}


def prepared():
    p = {'review': review(), 'review_pin': m.pin(b'invented'), 'commit': commit(),
         'origin': 100, 'output': Path('/invented/output'), 'donor': Path('/invented/donor'),
         'original_manifest': {'runtime_files': {}}, 'reader': types.SimpleNamespace(end=160)}
    return p


def receipt():
    return {'schema': 'neural069_host_exit_v1', 'status': 'closed', 'source_manifest': dict(m.DONOR_PIN),
            'commit': review()['commit']['metadata'], 'program': m.pin(b'pass'), 'image': m.IMAGE,
            'attempt': '/invented/output/attempt', 'private_scoring_called': False,
            'child': {'natural_exit': True, 'process_reaped': True, 'streams_closed': True, 'timed_out': False,
                      'exit_code': 0, 'error_type': None}, 'whole_seconds': 500, 'host_seconds_before_receipt': 30,
            'outputs': [{'path': 'invented-'+str(i)} for i in range(81)]}


def result():
    return {'status': 'closed', 'receipt': m.pin(m.encoded(receipt())), 'outputs': 81, 'worker_natural_exit': True}


class Controls(unittest.TestCase):
    def test_01_exact_operator_contract(self):
        self.assertEqual(check(review()), m.pin(b'pass'))
        for key, value in [('approved', False), ('schema', 'other'), ('task_id', 'NEURAL-070'), ('extra', 1)]:
            v = review(); v[key] = value
            with self.assertRaises(ValueError): check(v)

    def test_02_types_and_resource_identity(self):
        for key, value in [('cpu', True), ('candidate_seconds', 0), ('candidate_seconds', 7201),
                           ('memory_bytes', 536870911), ('attempt_retained_and_write_bytes', 20000001), ('other_bytes', 18)]:
            v = review(); v['resources'][key] = value
            with self.assertRaises(ValueError): check(v)
        for other in (True, -1, 1.0):
            with self.assertRaises(ValueError): check(review(), other)
        v = review(); v['source']['original_manifest']['bytes'] = 990.0
        with self.assertRaises(ValueError): check(v)

    def test_03_program_output_and_environment_not_invented(self):
        for key, value in [('output', '/other/output'), ('docker_socket', 'relative')]:
            v = review(); v[key] = value
            with self.assertRaises(ValueError): check(v)
        v = review(); v['program']['path'] = '/other/program.py'
        with self.assertRaises(ValueError): check(v)
        for key, value in [('PATH', ''), ('DOCKER_TLS_VERIFY', '1'), ('DOCKER_CERT_PATH', '/invented/certs')]:
            v = review(); v['environment'][key] = value
            with self.assertRaises(ValueError): check(v)

    def test_04_no_duplicate_nonfinite_or_bad_pin(self):
        for b in (b'{"x":0,"x":1}', b'{"x":NaN}'):
            with self.assertRaises(ValueError): m.parse(b)
        for v in ({'bytes': True, 'sha256': 'a'*64}, {'bytes': 4, 'sha256': 'A'*64}):
            with self.assertRaises(ValueError): m.descriptor(v, 8)

    def test_05_bad_review_precedes_source_or_commit_access(self):
        v = review(); v['program']['path'] = '/other/program.py'
        reader = types.SimpleNamespace(capture=mock.Mock(return_value=m.encoded(v)))
        a = argparse.Namespace(program=Path('/invented/program.py'), output=Path('/invented/output'),
                               review=Path('/invented/review.json'), other_reserve_bytes=17)
        with self.assertRaises(ValueError): m.prepare(a, 100, reader=reader)
        self.assertEqual(reader.capture.call_count, 1)

    def test_06_commit_requires_complete_ordered80_and_same_program(self):
        self.assertEqual(m.validate_commit(commit(), review(), lock()), commit())
        for mutate in (lambda c: c['full_cases'].pop(), lambda c: c['full_cases'].reverse(),
                       lambda c: c.update(program=m.pin(b'evil')), lambda c: c.update(candidate_seconds=21),
                       lambda c: c.update(cpu=True), lambda c: c.update(image='other')):
            c = commit(); mutate(c)
            with self.assertRaises(ValueError): m.validate_commit(c, review(), lock())

    def test_07_exact_clock_bridge_source_and_other_functions_unchanged(self):
        p = m.REPO/m.DONOR_REL/'supervise.py'; original = p.read_bytes()
        self.assertEqual((len(original), hashlib.sha256(original).hexdigest()),
                         (15873, '9b265daba01c41e8b4960920a6cde622a57a15f22ddb5ac00f49987b687fbf97'))
        current = (HERE/'supervise_origin.py').read_bytes()
        self.assertEqual(current, m.bridge_bytes(original))
        a = ast.parse(original); b = ast.parse(current)
        self.assertEqual(len(a.body), len(b.body))
        for x, y in zip(a.body, b.body):
            if isinstance(x, ast.FunctionDef) and x.name == 'supervise':
                self.assertEqual([k.arg for k in y.args.kwonlyargs], ['started'])
                self.assertEqual(ast.dump(x.body[-1], include_attributes=False), ast.dump(y.body[-1], include_attributes=False))
            else:
                self.assertEqual(ast.dump(x, include_attributes=False), ast.dump(y, include_attributes=False))

    def test_08_real_bridge_function_remaining_startup_only(self):
        a = ast.parse((HERE/'supervise_origin.py').read_bytes())
        f = next(x for x in a.body if isinstance(x, ast.FunctionDef) and x.name == 'supervise')
        # Compile only the inert function definition; never bootstrap donor modules.
        module = ast.Module(body=[f], type_ignores=[]); ast.fix_missing_locations(module)
        class StopBeforeIO(Exception): pass
        sig = types.SimpleNamespace(SIGALRM=1, ITIMER_REAL=2, signal=mock.Mock(return_value='old'),
                                    setitimer=mock.Mock(return_value=(0.0, 0.0)))
        namespace = {'time': types.SimpleNamespace(monotonic=lambda: 110), 'need': m.need, 'signal': sig,
                     'path': mock.Mock(side_effect=StopBeforeIO), 'WRITE': None}
        exec(compile(module, '<invented-bridge-check>', 'exec'), namespace)
        with self.assertRaises(StopBeforeIO):
            namespace['supervise'](None, None, None, None, None, None, None, started=100)
        self.assertEqual(sig.setitimer.call_args_list[0].args, (2, 50))
        self.assertEqual(sig.setitimer.call_args_list[-1].args, (2, 0))
        sig.signal.reset_mock()
        with self.assertRaises(ValueError):
            namespace['supervise'](None, None, None, None, None, None, None, started=50)
        sig.signal.assert_not_called()

    def test_09_capture_budget_and_deadline_prevent_open(self):
        r = m.Reader(160); r.charged = m.READ_CAP
        with mock.patch.object(m.time, 'monotonic', return_value=100), mock.patch.object(m.os, 'open') as opened:
            with self.assertRaises(ValueError): r.capture('/invented/source', 4)
            opened.assert_not_called()
        clock = [100]
        def late(p): clock[0] = 160; return Path(p)
        with mock.patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), mock.patch.object(m, 'ordinary', side_effect=late), mock.patch.object(m.os, 'open') as opened:
            with self.assertRaises(TimeoutError): m.Reader(160).capture('/invented/source', 4)
            opened.assert_not_called()

    def test_10_closed_receipt_semantics(self):
        m.validate_return(result(), receipt(), prepared())
        for change in ({'natural_exit': False}, {'exit_code': True}, {'exit_code': 2}, {'streams_closed': False}, {'timed_out': True}):
            v = receipt(); v['child'].update(change)
            with self.assertRaises(ValueError): m.validate_return(result(), v, prepared())
        v = receipt(); v['outputs'].pop()
        with self.assertRaises(ValueError): m.validate_return(result(), v, prepared())
        v = receipt(); v['host_seconds_before_receipt'] = float('nan')
        with self.assertRaises(ValueError): m.validate_return(result(), v, prepared())

    def test_11_forward_origin_environment_and_postjoin_no_reset(self):
        p = prepared(); p['reader'].capture = mock.Mock(side_effect=[m.encoded(receipt()), b'original-manifest'])
        runtime = types.SimpleNamespace(supervise=mock.Mock(return_value=result()))
        env = {k: v for k, v in review()['environment'].items() if v is not None}
        with mock.patch.object(m.time, 'monotonic', return_value=110), mock.patch.object(m.os, 'environ', env), mock.patch.object(m.signal, 'setitimer') as timer:
            returned, end = m.execute_prepared(p, compiler=lambda _: runtime)
        self.assertEqual(end, 600); self.assertEqual(returned, result())
        self.assertEqual(runtime.supervise.call_args.kwargs, {'started': 100})
        self.assertEqual(timer.call_args_list[0].args, (m.signal.ITIMER_REAL, 0))
        self.assertEqual(timer.call_args_list[1].args, (m.signal.ITIMER_REAL, 490))
        self.assertEqual(p['reader'].end, 600)
        compiler = mock.Mock()
        with mock.patch.object(m.time, 'monotonic', return_value=110), mock.patch.object(m.os, 'environ', {}):
            with self.assertRaises(ValueError): m.execute_prepared(prepared(), compiler=compiler)
        compiler.assert_not_called()

    def test_12_late_success_and_terminal_refuse(self):
        p = prepared(); clock = [110]
        def late(*a, **kw): clock[0] = 600; return result()
        env = {k: v for k, v in review()['environment'].items() if v is not None}
        with mock.patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), mock.patch.object(m.os, 'environ', env), mock.patch.object(m.signal, 'setitimer'):
            with self.assertRaises(TimeoutError): m.execute_prepared(p, compiler=lambda _: types.SimpleNamespace(supervise=late))
        clock[0] = 110
        class Selector:
            def __enter__(self): return self
            def __exit__(self, *_): return False
            def register(self, *_): pass
            def select(self, *_): clock[0] = 600; return [1]
        with mock.patch.object(m.time, 'monotonic', side_effect=lambda: clock[0]), mock.patch.object(m.selectors, 'DefaultSelector', return_value=Selector()), mock.patch.object(m.os, 'get_blocking', return_value=True), mock.patch.object(m.os, 'set_blocking'), mock.patch.object(m.os, 'write') as written:
            with self.assertRaises(TimeoutError): m.terminal({'status': 'closed'}, 600)
            written.assert_not_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
