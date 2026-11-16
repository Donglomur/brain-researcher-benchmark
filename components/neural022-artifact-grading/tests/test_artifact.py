"""Portable generated-only CLI, scientific invariants and file-boundary checks."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('artifact_score', PACKAGE / 'private/score.py')
s = importlib.util.module_from_spec(spec); spec.loader.exec_module(s)
import numpy as np


def descriptor(path, root):
    body = path.read_bytes()
    return {'path': path.relative_to(root).as_posix(), 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()}


class GeneratedArtifact(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.package = self.root / 'package'; (self.package / 'private').mkdir(parents=True)
        shutil.copy2(PACKAGE / 'private/score.py', self.package / 'private/score.py')
        shutil.copytree(PACKAGE / 'private/vendor', self.package / 'private/vendor', ignore=shutil.ignore_patterns('__pycache__'))
        self.rows = []
        for mode, counts in [('passive', [5, 3, 3, 6, 3, 6, 6, 8]), ('active', [10, 7, 8, 6, 4, 11, 3, 3])]:
            for direction, count in zip(range(0, 360, 45), counts):
                for _ in range(count): self.rows.append({'id': f'{len(self.rows)+1:024x}', 'mode': mode, 'direction': direction})
        public = self.package / 'cases.json'
        public.write_bytes(s.io.encoded_json({'schema': 'neural022_public_cases_v1', 'cases': self.rows}))
        reference = self.package / 'reference.npz'
        values = {'ids': np.array([x['id'] for x in self.rows], dtype='<U24'), 'velocity': np.zeros((92, 2), dtype='<f8')}
        for j, name in enumerate(s.candidate.METHODS): values[name] = np.tile([j / 10, 0.], (92, 1)).astype('<f8')
        reference.write_bytes(s.io.encoded_npz(values))
        self.op = {'task_id': 'NEURAL-022', 'public': {'cases.json': descriptor(public, self.package)},
                   'private': descriptor(reference, self.package), 'expected_fixed_reference': {
                       'losses': {mode: {name: (j / 10) ** 2 for j, name in enumerate(s.candidate.METHODS)} for mode in ['passive', 'active']},
                       'primary_active_minus_passive_neural_loss': -.01}}
        self.prediction = {'schema': 'neural022_predictions_v1', 'predictions': [{'id': x['id'], 'velocity': [1., 2.]} for x in self.rows]}
        self.commit = self.commit_prediction(self.prediction)
        (self.package / 'private/operator_manifest.json').write_bytes(s.io.encoded_json(self.op))
    def tearDown(self): self.temp.cleanup()
    def commit_prediction(self, value, name='predictions.json'):
        p = self.root / name; p.write_bytes(s.io.encoded_json(value))
        return {'schema_version': 1, 'task_id': 'NEURAL-022', 'file': descriptor(p, self.root)}
    def assess(self, value=None): return s.assess(self.package, self.op, self.commit if value is None else value, self.root)
    def cli(self, commit=None, output='result.json'):
        path = self.root / 'submission.json'; path.write_bytes(s.io.encoded_json(self.commit if commit is None else commit))
        env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
        run = subprocess.run([sys.executable, '-I', '-B', str(self.package / 'private/score.py'), '--submission', str(path), '--output', str(self.root / output)],
                             capture_output=True, timeout=10, env=env)
        self.assertLess(len(run.stdout) + len(run.stderr), 65536)
        report = self.root / output
        return run, json.loads(report.read_bytes()) if report.exists() else None
    def test_complete_hand_score_all_comparisons(self):
        result = self.assess(); self.assertEqual(result['status'], 'scored_exposed_transfer_candidate')
        self.assertEqual(result['score'], 5.); self.assertEqual(result['target_loader_calls'], 1)
        detail = result['result']; self.assertEqual(detail['independent_animals'], 1)
        self.assertEqual(detail['candidate_identity'], 'candidate_program')
        self.assertAlmostEqual(detail['candidate_minus_fixed_passive_neural'], 4.99)
        for mode, n in [('passive', 40), ('active', 52)]:
            self.assertEqual(detail['metrics'][mode]['trials'], n)
            self.assertEqual(len(detail['metrics'][mode]['candidate_minus_fixed_reference']), 7)
        self.assertEqual(len(detail['direction_strata']), 16)
        self.assertAlmostEqual(detail['original_reference_diagnostic']['value'], -.01)
        self.assertFalse(result['producer_absence_verified'])
    def test_trial_weighting_not_direction_macro(self):
        for row, context in zip(self.prediction['predictions'], self.rows): row['velocity'] = [1. if context['direction'] == 45 else 2., 0.]
        result = self.assess(self.commit_prediction(self.prediction))
        self.assertEqual(result['score'], (3 + 37 * 4) / 40)
        self.assertNotEqual(result['score'], (1 + 7 * 4) / 8)
    def test_negative_gap_and_candidate_identity(self):
        for row in self.prediction['predictions']: row['velocity'] = [0., 0.]
        result = self.assess(self.commit_prediction(self.prediction))
        self.assertLess(result['result']['candidate_minus_fixed_passive_neural'], 0)
        self.assertEqual(result['result']['candidate_identity'], 'candidate_program')
    def test_complete_malformed_variants_before_missing_reference(self):
        (self.package / 'reference.npz').unlink()
        variants = []
        v = copy.deepcopy(self.prediction); v['predictions'].pop(); variants.append(v)
        v = copy.deepcopy(self.prediction); v['predictions'].reverse(); variants.append(v)
        v = copy.deepcopy(self.prediction); v['predictions'][-1]['id'] = v['predictions'][0]['id']; variants.append(v)
        v = copy.deepcopy(self.prediction); v['predictions'][-1]['id'] = 'f' * 24; variants.append(v)
        v = copy.deepcopy(self.prediction); v['predictions'][-1]['velocity'] = [True, 0.]; variants.append(v)
        v = copy.deepcopy(self.prediction); v['predictions'][-1]['velocity'] = [0.]; variants.append(v)
        v = copy.deepcopy(self.prediction); v['predictions'][-1]['extra'] = 1; variants.append(v)
        for i, value in enumerate(variants):
            with self.subTest(i=i):
                result = self.assess(self.commit_prediction(value))
                self.assertEqual(result['status'], 'invalid_submission'); self.assertIsNone(result['score'])
                self.assertEqual(result['target_loader_calls'], 0)
    def test_commit_hash_mismatch_before_operator_inputs(self):
        self.commit['file']['sha256'] = '0' * 64; self.op = {}
        result = self.assess(); self.assertEqual(result['status'], 'invalid_submission')
        self.assertEqual(result['target_loader_calls'], 0)
    def test_reference_scalar_mismatch_operator_error(self):
        self.op['expected_fixed_reference']['losses']['passive']['zero'] = 9.
        result = self.assess(); self.assertEqual(result['status'], 'operator_error'); self.assertIsNone(result['score'])
    def test_extreme_finite_not_clipped(self):
        self.prediction['predictions'][-1]['velocity'] = [1e308, 1e308]
        result = self.assess(self.commit_prediction(self.prediction))
        self.assertEqual(result['status'], 'unsupported_numerical_result'); self.assertIsNone(result['score'])
    def test_actual_cli_generated_complete(self):
        run, result = self.cli(); self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(result['status'], 'scored_exposed_transfer_candidate'); self.assertEqual(result['score'], 5.)
    def test_actual_cli_invalid_before_missing_bindings(self):
        (self.package / 'private/operator_manifest.json').unlink()
        path = self.root / 'bad.json'; path.write_bytes(b'{"x":1,"x":2}')
        env = dict(os.environ, OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1')
        run = subprocess.run([sys.executable, '-I', '-B', str(self.package / 'private/score.py'), '--submission', str(path), '--output', str(self.root / 'bad-result.json')],
                             capture_output=True, timeout=10, env=env)
        self.assertEqual(run.returncode, 0, run.stderr)
        result = json.loads((self.root / 'bad-result.json').read_bytes()); self.assertEqual(result['status'], 'invalid_submission')
        self.assertEqual(result['target_loader_calls'], 0)
    def test_actual_cli_missing_operator_is_not_candidate_score(self):
        (self.package / 'private/operator_manifest.json').unlink()
        run, result = self.cli(); self.assertEqual(run.returncode, 2, run.stderr)
        self.assertEqual(result['status'], 'operator_error'); self.assertIsNone(result['score'])
    def test_actual_cli_no_report_overwrite(self):
        out = self.root / 'result.json'; out.write_bytes(b'{"sentinel":true}')
        run, result = self.cli(); self.assertNotEqual(run.returncode, 0)
        self.assertEqual(result, {'sentinel': True})
    def test_npz_extra_and_object_members_rejected(self):
        schema = s.io.schema('target', s.candidate.METHODS)
        normal = {'ids': np.array([x['id'] for x in self.rows], dtype='<U24'), 'velocity': np.zeros((92, 2), dtype='<f8')}
        for changed in [dict(normal, extra=np.zeros(1)), dict(normal, velocity=np.zeros((92, 2), dtype=object)), dict(normal, velocity=np.zeros((91, 2), dtype='<f8'))]:
            with self.assertRaises(ValueError): s.io.npz(s.io.encoded_npz(changed), schema)


class ReaderBoundary(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.path = self.root / 'generated.json'; self.path.write_bytes(b'{}')
    def tearDown(self): self.temp.cleanup()
    def test_preopen_growth_rejected(self):
        regular = s.regular
        def changed(path, cap):
            result = regular(path, cap); result.write_bytes(b'{}' + b' ' * (cap - 1)); return result
        with patch.object(s, 'regular', side_effect=changed):
            with self.assertRaises(ValueError): s.read_json(self.path, 16)
    def test_exact_cap_and_bounded_read_request(self):
        self.path.write_bytes(b'{}' + b' ' * 14); read = os.read; requests = []
        def bounded(fd, n): requests.append(n); return read(fd, n)
        with patch.object(s.os, 'read', side_effect=bounded): self.assertEqual(s.read_json(self.path, 16), {})
        self.assertEqual(requests, [17])
    def test_during_read_growth_and_link_changes_rejected(self):
        read = os.read
        for change in ['grow', 'link']:
            self.path.write_bytes(b'{}')
            def changed(fd, n):
                body = read(fd, n)
                if change == 'grow': self.path.write_bytes(b'{} ')
                else: os.link(self.path, self.root / 'alias')
                return body
            with patch.object(s.os, 'read', side_effect=changed):
                with self.assertRaises(ValueError): s.read_json(self.path, 16)
    def test_symlink_and_fifo_substitution_refused(self):
        regular = s.regular
        for kind in ['symlink', 'fifo']:
            if self.path.exists() or self.path.is_symlink(): self.path.unlink()
            self.path.write_bytes(b'{}'); target = self.root / 'target'; target.write_bytes(b'{}')
            def changed(path, cap):
                result = regular(path, cap); result.unlink()
                if kind == 'symlink': result.symlink_to(target)
                else: os.mkfifo(result)
                return result
            with patch.object(s, 'regular', side_effect=changed):
                with self.assertRaises((ValueError, OSError)): s.read_json(self.path, 16)
    def test_descriptor_closed_success_read_failure_parse_failure(self):
        actual = os.open
        for kind in ['success', 'read', 'parse']:
            self.path.write_bytes(b'{}' if kind != 'parse' else b'{'); opened = []
            def capture(*args, **kwargs):
                fd = actual(*args, **kwargs); opened.append(fd); return fd
            with patch.object(s.os, 'open', side_effect=capture):
                if kind == 'read':
                    with patch.object(s.os, 'read', side_effect=OSError('generated read failure')):
                        with self.assertRaises(OSError): s.read_json(self.path, 16)
                elif kind == 'parse':
                    with self.assertRaises(ValueError): s.read_json(self.path, 16)
                else: self.assertEqual(s.read_json(self.path, 16), {})
            self.assertEqual(len(opened), 1)
            with self.assertRaises(OSError): os.fstat(opened[0])
    def test_duplicate_nonfinite_and_trailing_json_rejected(self):
        for body in [b'{"x":1,"x":2}', b'{"x":NaN}', b'{}{}', b'\xff']:
            self.path.write_bytes(body)
            with self.assertRaises((ValueError, UnicodeError)): s.read_json(self.path, 100)


if __name__ == '__main__':
    start = time.monotonic(); cpu = time.process_time()
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__]))
    print(json.dumps({'status': 'passed' if result.wasSuccessful() else 'failed', 'tests': result.testsRun,
                      'python': sys.version.split()[0], 'numpy': np.__version__, 'generated_only': True,
                      'elapsed_seconds': time.monotonic() - start, 'parent_cpu_seconds': time.process_time() - cpu,
                      'parent_maxrss_native': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                      'children_maxrss_native': resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss,
                      'maxrss_unit': 'bytes' if sys.platform == 'darwin' else 'KiB',
                      'children_cpu_seconds': resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime + resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime}))
    raise SystemExit(0 if result.wasSuccessful() else 1)
