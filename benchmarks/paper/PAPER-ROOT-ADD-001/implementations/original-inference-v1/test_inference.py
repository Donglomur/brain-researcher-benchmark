"""Generated source-helper comparisons; no authentic result arrays are read."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import warnings
import zipfile

import numpy as np
import scipy
from scipy.optimize import curve_fit, OptimizeWarning

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inference as impl

HERE = Path(__file__).resolve().parent
raw_helper = (HERE / 'figure3_author_helpers.py').read_bytes()
assert hashlib.sha256(raw_helper).hexdigest() == '3d61d21a3b0bd25e54afc7013395fe609ddae16578800ed29015efe6e840be39'
spec = importlib.util.spec_from_file_location('attributed_author_helpers', HERE / 'figure3_author_helpers.py')
author = importlib.util.module_from_spec(spec); spec.loader.exec_module(author)


def source_p(a, b, *, seed, draws):
    state = np.random.get_state()
    try:
        return author.permutation_test_1side(a, b, nsamp=draws, seed=seed)
    finally:
        np.random.set_state(state)


def generated_panel():
    _, _, sp, _ = impl.load_support()
    rng = np.random.RandomState(129)
    panel = {}
    ngram_means = author.exponential_func(np.array([1, 3, 5, 7, 10]), -.08, -.2, .12)
    for i, session in enumerate(sp.SESSION_UNITS):
        fields = {f: rng.uniform(-.02, .08, shape) for f, shape in sp.shapes(session).items()}
        for n, mean in zip((1, 3, 5, 7, 10), ngram_means):
            fields[f'ngram{n}'] = np.full(33, mean - .01)
            fields[f'ngram{n}'][n] = mean + (i - 6.5) * .0001
        panel[session] = fields
    weights = {'schema': 'language-original-population-weights/v1', 'rows': [
        {'session': session, 'count': i + 1, 'shape': [i + 1, 2, 80],
         'member': f'data_processed/{session}/self_FR_aligned2word.npy',
         'receipt': {'full_member_crc_verified': True, 'array_values_decoded': False, 'sha256': '0' * 64}}
        for i, session in enumerate(sp.SESSION_UNITS)]}
    return panel, weights


def summarize(panel, weights, budget=900000):
    return impl.complete_summary(panel, weights, permutation_budget=budget,
                                 expected_numpy_version=np.__version__, expected_scipy_version=scipy.__version__)


class PermutationTests(unittest.TestCase):
    def test_literal_source_helper_matches_both_seeds_and_precisions(self):
        for dtype in (np.float32, np.float64):
            a = np.linspace(-.1, .2, 42).astype(dtype)
            b = np.linspace(-.11, .19, 42).astype(dtype)
            for seed in (46, 20):
                expected = source_p(a, b, seed=seed, draws=127)
                actual = impl.permutation_one_sided(a, b, seed=seed, permutations=127)
                self.assertEqual(actual['p_one_sided_source'], expected)

    def test_resets_each_call_and_does_not_change_global_rng(self):
        a, b = np.arange(42.) / 42, np.arange(42.) / 43
        state = np.random.get_state()
        first = impl.permutation_one_sided(a, b, seed=46, permutations=113)
        second = impl.permutation_one_sided(a, b, seed=46, permutations=113)
        self.assertEqual(first, second)
        after = np.random.get_state()
        self.assertEqual(state[0], after[0]); np.testing.assert_array_equal(state[1], after[1])
        self.assertEqual(state[2:], after[2:])

    def test_ties_count_and_no_add_one_can_return_zero(self):
        tied = impl.permutation_one_sided(np.zeros(42), np.zeros(42), seed=20, permutations=100)
        self.assertEqual(tied['p_one_sided_source'], 1)
        zero = impl.permutation_one_sided(np.ones(42), -np.ones(42), seed=46, permutations=100)
        self.assertEqual(zero['p_one_sided_source'], 0)
        self.assertFalse(zero['add_one_correction'])

    def test_source_nan_to_zero_hazard_is_refused_without_dropping(self):
        a, b = np.ones(42), np.zeros(42); a[0] = np.nan
        self.assertEqual(source_p(a, b, seed=46, draws=20), 0)
        with self.assertRaisesRegex(ValueError, 'Finite complete'):
            impl.permutation_one_sided(a, b, seed=46, permutations=20)

    def test_permutation_draw_and_seed_bounds(self):
        for draws in (0, True, 100001):
            with self.assertRaisesRegex(ValueError, 'schedule'):
                impl.permutation_one_sided(np.ones(3), np.zeros(3), seed=46, permutations=draws)
        with self.assertRaisesRegex(ValueError, 'schedule'):
            impl.permutation_one_sided(np.ones(3), np.zeros(3), seed=-1)


class CurveTests(unittest.TestCase):
    def test_parameters_covariance_and_grid_match_literal_source_function(self):
        x = np.array([1, 3, 5, 7, 10]); y = author.exponential_func(x, -.08, -.2, .12)
        expected, covariance = curve_fit(author.exponential_func, x, y, p0=(-8, -.08, .08))
        report = impl.curve_report(y, expected_scipy_version=scipy.__version__)
        self.assertEqual(report['status'], 'computed')
        np.testing.assert_array_equal(report['parameters'], expected)
        np.testing.assert_array_equal(report['covariance'], covariance)
        grid = np.linspace(1, 10, 100)
        np.testing.assert_array_equal(report['x_fit'], grid)
        np.testing.assert_array_equal(report['y_fit'], author.exponential_func(grid, *expected))

    def test_source_default_call_and_nonfinite_covariance_are_explicit(self):
        def fake(func, x, y, **kwargs):
            self.assertEqual(kwargs, {'p0': (-8, -.08, .08)})
            warnings.warn('generated singular covariance', OptimizeWarning)
            return np.array([-.08, -.2, .12]), np.full((3, 3), np.inf)
        with patch('scipy.optimize.curve_fit', side_effect=fake) as fitting:
            result = impl.curve_report(np.linspace(.01, .05, 5), expected_scipy_version=scipy.__version__)
        self.assertEqual(fitting.call_count, 1)
        self.assertEqual(result['covariance'], [[None] * 3] * 3)
        self.assertEqual(result['warnings'][0]['category'], 'OptimizeWarning')

    def test_fit_failure_has_no_solver_retry(self):
        with patch('scipy.optimize.curve_fit', side_effect=RuntimeError('generated nonconvergence')) as fitting:
            result = impl.curve_report(np.ones(5), expected_scipy_version=scipy.__version__)
        self.assertEqual(fitting.call_count, 1)
        self.assertEqual(result['status'], 'failed_without_retry')
        self.assertIsNone(result['parameters'])

    def test_incomplete_or_wrong_runtime_fit_refused(self):
        for y in (np.ones(4), np.array([0, 1, 2, 3, np.nan])):
            with self.assertRaisesRegex(ValueError, 'Five complete'):
                impl.curve_report(y, expected_scipy_version=scipy.__version__)
        with self.assertRaisesRegex(ValueError, 'runtime mismatch'):
            impl.curve_report(np.ones(5), expected_scipy_version='wrong')


class WholeFamilyTests(unittest.TestCase):
    def test_complete_release_path_refuses_float32_before_reduction(self):
        panel, weights = generated_panel()
        panel['p1_1']['population'] = panel['p1_1']['population'].astype(np.float32)
        with patch.object(impl, 'permutation_one_sided', side_effect=AssertionError('must not test')):
            with self.assertRaisesRegex(ValueError, 'requires float64'):
                summarize(panel, weights)

    def test_exact_nine_contrast_schedule_and_42_row_major_observations(self):
        panel, weights = generated_panel(); calls = []
        def record(a, b, *, seed):
            calls.append((a.copy(), b.copy(), seed))
            return {'p_one_sided_source': .5, 'permutations': 100000}
        with patch.object(impl, 'permutation_one_sided', side_effect=record):
            report = summarize(panel, weights)
        self.assertEqual(len(calls), 9)
        self.assertEqual([r[2] for r in calls], [46] * 6 + [20] * 3)
        np.testing.assert_array_equal(calls[0][0], np.stack([r['population'][17:20, 5] for r in panel.values()]).reshape(-1))
        np.testing.assert_array_equal(calls[0][1], np.stack([r['syn'][:3, 0] for r in panel.values()]).reshape(-1))
        self.assertEqual([(r['left'], r['right'], r['source_seed']) for r in report['figure3b_source_contrasts']], list(impl.CONTRASTS))
        self.assertFalse(report['source_inference_scope']['contextual_vs_time_shuffle_contrast_added'])
        self.assertEqual(report['figure3b_selection']['layer_index_zero_based'], 5)

    def test_actual_full900000_draw_schedule_with_generated_results(self):
        panel, weights = generated_panel()
        report = summarize(panel, weights)
        self.assertEqual(sum(r['permutations'] for r in report['figure3b_source_contrasts']), 900000)
        self.assertTrue(report['source_permutation_tests_executed'])
        self.assertEqual(report['figure3c_source_fit']['status'], 'computed')
        self.assertFalse(report['scientific_qualification'])
        self.assertFalse(report['independent_AI_reproduction'])
        first = report['figure3b_source_contrasts'][0]
        a = np.stack([r['population'][17:20, 5] for r in panel.values()]).reshape(-1)
        b = np.stack([r['syn'][:3, 0] for r in panel.values()]).reshape(-1)
        self.assertEqual(first['p_one_sided_source'], source_p(a, b, seed=46, draws=100000))

    def test_budget_refused_before_reduction_and_runtime_guard(self):
        with patch.object(impl, 'load_support', side_effect=AssertionError('must not reduce')):
            with self.assertRaisesRegex(ValueError, '900000'):
                summarize({}, {}, budget=899999)
            with self.assertRaisesRegex(ValueError, 'NumPy runtime'):
                impl.complete_summary({}, {}, permutation_budget=900000, expected_numpy_version='wrong', expected_scipy_version=scipy.__version__)

    def test_undefined_observations_and_context_selection_are_not_repaired(self):
        panel, weights = generated_panel(); panel['p1_1']['population'][17, 5] = np.nan
        panel['p1_1']['ngram1'][0] = np.nan
        with patch.object(impl, 'permutation_one_sided', return_value={'p_one_sided_source': .5}) as permutation:
            report = summarize(panel, weights)
        self.assertEqual(permutation.call_count, 6)
        self.assertEqual([r['status'] for r in report['figure3b_source_contrasts'][:3]], ['undefined_input_not_tested'] * 3)
        self.assertEqual(report['figure3c_source_fit']['status'], 'undefined_input_not_fitted')
        self.assertFalse(report['source_permutation_tests_executed'])

    def test_bound_support_restores_existing_module_aliases(self):
        sentinel = object()
        with patch.dict(sys.modules, {'inputs': sentinel}):
            impl.load_support()
            self.assertIs(sys.modules['inputs'], sentinel)


class ArchiveReferenceTests(unittest.TestCase):
    def test_all224_original_results_stream_without_extraction(self):
        metadata = copy.deepcopy(impl.author_result_bindings())
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); archive = root / 'analysis.zip'
            with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED) as out:
                for name, row in metadata['members'].items():
                    stream = io.BytesIO(); np.save(stream, np.full(row['expected_shape'], .125), allow_pickle=False)
                    out.writestr(name, stream.getvalue())
            raw = archive.read_bytes()
            metadata['archives']['analysis.zip'].update(size=len(raw), checksum='md5:' + hashlib.md5(raw).hexdigest())
            with zipfile.ZipFile(archive) as z:
                for name, row in metadata['members'].items():
                    info = z.getinfo(name); row.update(bytes=info.file_size, compressed_bytes=info.compress_size, crc32=f'{info.CRC:08x}')
            with patch.object(impl, 'author_result_bindings', return_value=metadata):
                panel, receipt = impl.load_author_panel(archive, read_limit=30 * 1024**2, working_limit=64 * 1024**2)
            self.assertEqual(len(panel), 14)
            self.assertEqual(sum(len(r) for r in panel.values()), 224)
            self.assertEqual(len(receipt['member_receipts']), 224)
            self.assertEqual(receipt['extracted_files'], 0)
            self.assertEqual(list(root.iterdir()), [archive])
            self.assertEqual(panel['p8_1']['unit'].shape, (82, 40, 33))
            self.assertEqual(panel['p8_1']['unit'][0, 0, 0], .125)

    def test_full_panel_memory_admission_precedes_source_open(self):
        with self.assertRaisesRegex(ValueError, 'working allocation'):
            impl.load_author_panel('/does-not-exist', read_limit=1, working_limit=1)

    def test_isolated_cli_help_requires_no_payload(self):
        run = subprocess.run([sys.executable, '-I', '-B', str(HERE / 'inference.py'), '--help'],
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('--author-analysis-archive', run.stdout)


def generated_preparation_receipt():
    source_inputs, _, _, _ = impl.load_support()
    metadata = source_inputs.bindings()
    archives = {name: {'bytes': row['size'], 'md5': row['checksum'][4:], 'sha256': '0' * 64}
                for name, row in metadata['archives'].items() if name != 'analysis.zip'}
    receipts = {name: {'archive': row['archive'], 'bytes': row['bytes'], 'crc32': row['crc32'],
                      'sha256': '0' * 64, 'full_member_crc_verified': True,
                      'array_values_decoded': not name.endswith('/self_FR_aligned2word.npy')}
                for name, row in metadata['members'].items()}
    sessions, weights = [], []
    for geometry in metadata['sessions']:
        session = geometry['id']; weight_name = f'data_processed/{session}/self_FR_aligned2word.npy'
        count = metadata['members'][weight_name]['bytes'] // (geometry['word_rows'] * 80 * 8)
        weights.append({'session': session, 'count': count, 'shape': [count, geometry['word_rows'], 80],
                        'member': weight_name, 'fortran_order': False, 'receipt': receipts[weight_name]})
        pins = {key: {'shape': shape, 'dtype': '<f8', 'sha256_c_order': '0' * 64} for key, shape in (
            ('original_qid', [geometry['word_rows']]), ('original_timing', [geometry['word_rows'], 2]),
            ('prepared_population_response', [geometry['time_bins'], 1]),
            ('prepared_unit_responses', [geometry['time_bins'], geometry['units']]))}
        sessions.append({'session': session, 'geometry': geometry, 'csv_row_order_preserved': True, **pins,
                         'input_receipts': {name: row for name, row in receipts.items() if
                          (f'/{session}/' in name or name == f'transcription/cleaned/{session}.csv') and name != weight_name}})
    return {'schema': 'language-original-input-preparation/v1', 'sessions': sessions,
            'population_weights': {'schema': 'language-original-population-weights/v1', 'rows': weights,
                                   'archive_receipts': archives}, 'archive_receipts': archives,
            'prepared_arrays_persisted': False, 'models_fitted': 0,
            'logical_source_read_charge_bytes': sum(row['bytes'] + 1 for row in archives.values())
                                               + sum(row['bytes'] + 1 for row in receipts.values())}


class PreparationReceiptTests(unittest.TestCase):
    def test_complete_generated_receipt_binds_all196_members(self):
        prepared = generated_preparation_receipt()
        self.assertIs(impl.validate_preparation_receipt(prepared), prepared)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / 'PREPARATION.json'
            raw = json.dumps(prepared).encode(); path.write_bytes(raw)
            self.assertEqual(impl.read_preparation_receipt(path, hashlib.sha256(raw).hexdigest()), prepared)

    def test_partial_or_changed_lineage_refused(self):
        for mutation in ('session', 'member', 'archive', 'weight', 'shape', 'charge'):
            value = generated_preparation_receipt()
            if mutation == 'session': value['sessions'].pop()
            if mutation == 'member': value['sessions'][0]['input_receipts'].pop(next(iter(value['sessions'][0]['input_receipts'])))
            if mutation == 'archive': value['archive_receipts']['DNN.zip']['md5'] = '0' * 32
            if mutation == 'weight': value['population_weights']['rows'][0]['shape'][1] += 1
            if mutation == 'shape': value['sessions'][0]['prepared_population_response']['shape'].pop()
            if mutation == 'charge': value['logical_source_read_charge_bytes'] -= 1
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                impl.validate_preparation_receipt(value)

    def test_fifo_symlink_and_oversized_receipt_refused_before_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); target = root / 'ordinary'; target.write_bytes(b'{}')
            link = root / 'link'; link.symlink_to(target)
            fifo = root / 'fifo'; os.mkfifo(fifo)
            large = root / 'large'
            with large.open('xb') as stream: stream.truncate(4 * 1024**2 + 1)
            for path in (link, fifo, large):
                with self.subTest(path=path.name), patch.object(impl.os, 'open', side_effect=AssertionError('must not open')):
                    with self.assertRaises(ValueError): impl.read_preparation_receipt(path, '0' * 64)

    def test_duplicate_nonfinite_and_wrong_hash_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / 'receipt'
            for raw, pattern in ((b'{"a":1,"a":2}', 'Duplicate'), (b'{"a":NaN}', 'Nonfinite')):
                path.write_bytes(raw)
                with self.assertRaisesRegex(ValueError, pattern):
                    impl.read_preparation_receipt(path, hashlib.sha256(raw).hexdigest())
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                impl.read_preparation_receipt(path, '0' * 64)

    def test_changed_file_identity_refused_after_bounded_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary).resolve() / 'receipt'; raw = b'{}'; path.write_bytes(raw)
            original = impl.os.fstat; calls = []
            def change(fd):
                info = original(fd); calls.append(1)
                if len(calls) == 2: path.write_bytes(b'{} ')
                return original(fd)
            with patch.object(impl.os, 'fstat', side_effect=change):
                with self.assertRaisesRegex(ValueError, 'changed during bounded read'):
                    impl.read_preparation_receipt(path, hashlib.sha256(raw).hexdigest())


if __name__ == '__main__':
    unittest.main()
