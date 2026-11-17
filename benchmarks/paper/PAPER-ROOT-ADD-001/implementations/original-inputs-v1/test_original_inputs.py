"""Generated construction controls; no authentic data or estimator fitting."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch
import zipfile

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import inputs
import prediction
import workflow


def npy(value):
    out = io.BytesIO(); np.save(out, value, allow_pickle=False)
    return out.getvalue()


def generated_session(session='p1_1', units=2):
    rng = np.random.RandomState(5)
    geometry = {'id': session, 'person': session.split('_')[0], 'time_bins': 40,
                'units': units, 'word_rows': 3, 'llm_layers': 33}
    return {'session': session, 'geometry': geometry,
            'fr': rng.uniform(0, 1, (40, units)), 'speaker': np.ones((40, 2)),
            'timing': np.array([[0., 1.], [1., 2.], [2., 4.]]),
            'qid': np.array([0., 99999., 1.]),
            **{f: rng.normal(size=(3, 30, 1 if f in ('sem_syn', 'word2vec', 'syn') else 33))
               for f in inputs.FAMILIES}, 'input_receipts': {}}


class GeneratedArchives:
    def __init__(self, root, *, bad_member=None):
        self.data = generated_session()
        self.meta = {'sessions': [self.data['geometry']], 'archives': {}, 'members': {}}
        self.paths = {}
        array_names = {'fr': 'data_processed/p1_1/fr_matrix.npy',
                       'speaker': 'data_processed/p1_1/speaker_matrix.npy',
                       **{f: inputs.feature_member('p1_1', f) for f in inputs.FAMILIES}}
        entries = {n: npy(self.data[k][:, :, 0] if k in ('word2vec', 'sem_syn') else self.data[k])
                   for k, n in array_names.items()}
        entries['data_processed/p1_1/self_FR_aligned2word.npy'] = npy(np.ones((3, 3, 80)))
        entries['transcription/cleaned/p1_1.csv'] = b'start_time,end_time,qid\n0,1,0\n1,2,99999\n2,4,1\n'
        if bad_member:
            entries[bad_member[0]] = bad_member[1]
        for archive in ('data_processed.zip', 'DNN.zip', 'transcription.zip'):
            path = root / archive
            with zipfile.ZipFile(path, 'x', compression=zipfile.ZIP_DEFLATED) as out:
                for name, raw in entries.items():
                    if name.split('/')[0] + '.zip' != archive:
                        continue
                    out.writestr(name, raw)
            raw = path.read_bytes()
            self.paths[archive] = path
            self.meta['archives'][archive] = {'size': len(raw), 'checksum': 'md5:' + hashlib.md5(raw).hexdigest()}
            with zipfile.ZipFile(path) as z:
                for item in z.infolist():
                    row = {'archive': archive, 'bytes': item.file_size, 'compressed_bytes': item.compress_size,
                           'crc32': f'{item.CRC:08x}'}
                    if item.filename in array_names.values():
                        shape, order, dtype, _ = inputs.npy_header(entries[item.filename])
                        row.update({'shape': list(shape), 'dtype': str(dtype), 'fortran_order': order})
                    self.meta['members'][item.filename] = row

    def open(self, **kw):
        return inputs.ArchiveInputs(self.paths, read_limit=kw.get('read_limit', 16 * 1024**2),
                                   working_limit=kw.get('working_limit', 128 * 1024**2),
                                   metadata=kw.get('metadata', self.meta))


class SourceSemanticsTests(unittest.TestCase):
    def test_sentinel_and_overlap_write_features_but_preserve_prior_qid(self):
        timing = np.array([[0., .3], [.1, .4]])
        x, q = prediction.format_words(timing, np.array([8., 99999.]), np.array([[2.], [6.]]), 5)
        np.testing.assert_array_equal(x[:, 0], [2, 6, 6, 6, 4])
        np.testing.assert_array_equal(q, [8, 8, 8, 99999, 99999])

    def test_huge_timing_refused_before_integer_cast(self):
        with np.errstate(all='raise'):
            with self.assertRaisesRegex(ValueError, 'timing'):
                prediction.format_words(np.array([[0., 1e300]]), np.array([1.]), np.ones((1, 1)), 40)
            with self.assertRaisesRegex(ValueError, 'clock'):
                inputs.parse_words(b'start_time,end_time,qid\n0,1e300,1\n', {'word_rows': 1, 'time_bins': 40})

    def test_source_asymmetric_lags_include_positive_zero_qid_boundary(self):
        y, x, q, speaker = np.arange(8.)[:, None], (10 + np.arange(8.))[:, None], np.full(8, 9.), np.ones(8)
        xx, yy, qq, idx = prediction.lag_rows(y, x, speaker, q, 2)
        np.testing.assert_array_equal(xx[:, 0], [0, 0, 10, 11, 12, 13, 14, 15])
        np.testing.assert_array_equal(qq, [0, 0, 9, 9, 9, 9, 9, 9])
        np.testing.assert_array_equal(yy, y)
        xx, yy, qq, idx = prediction.lag_rows(y, x, speaker, q, -2)
        np.testing.assert_array_equal(yy[:, 0], [0, 0, 0, 1, 2, 3, 4, 5])
        np.testing.assert_array_equal(xx, x)

    def test_population_mean_then_source_smoothing_and_zero_endpoints(self):
        fr = np.column_stack((np.arange(30.), np.arange(30.) ** 2))
        p, u = prediction.smooth_targets(fr)
        expected = np.convolve(fr.mean(1), np.ones(3) / 3, mode='valid')
        np.testing.assert_allclose(p[1:-1, 0], expected)
        np.testing.assert_array_equal(p[[0, -1]], 0)
        np.testing.assert_array_equal(u[[0, -1]], 0)
        for i in range(2):
            np.testing.assert_allclose(u[1:-1, i], np.convolve(fr[:, i], np.ones(3) / 3, mode='valid'))

    def test_full4209_jobs_and_source_control_lags(self):
        data = generated_session()
        counts, lags = {}, {}
        for job in prediction.iter_jobs(data):
            f = job['field']; counts[f] = counts.get(f, 0) + 1
            lags.setdefault(f, set()).add(job['lag_bins'])
        self.assertEqual(sum(counts.values()), 4209)
        self.assertEqual(len(counts), 16)
        self.assertEqual(counts['unit'], 1320)
        self.assertEqual(lags['population'], set(range(-20, 20)))
        self.assertEqual(lags['random_token'], {-10})
        self.assertEqual(lags['syn'], {-3, -2, -1})

    def test_lexical_first_component_exclusion_and_syn_not_excluded(self):
        data = generated_session(); data['word2vec'][1] = np.nan
        words = [j for j in prediction.iter_jobs(data) if j['field'] == 'word2vec']
        self.assertEqual(len(words), 3)
        self.assertTrue(all(np.isfinite(j['x']).all() for j in words))
        data['syn'][1] = np.nan
        with self.assertRaisesRegex(ValueError, 'Finite retained'):
            list(prediction.iter_jobs(data))

    def test_sentence_swap_is_deterministic_with_replacement_and_singleton_fallback(self):
        q = np.array([2, 2, 0, 0, 1, 1, 3])
        result = prediction.sentence_swap_indices(q)
        np.testing.assert_array_equal(result, prediction.sentence_swap_indices(q))
        self.assertEqual(result[-1], 6)
        for offset, label in zip((0, 2, 4), (0, 1, 2)):
            self.assertNotEqual(q[result[offset]], label)
        with patch.object(prediction.random, 'Random') as factory:
            factory.return_value.choice.side_effect = lambda options: options[0]
            repeated = prediction.sentence_swap_indices(q)
        self.assertLess(len(np.unique(repeated)), len(q))

    def test_shuffle_matches_legacy_seed_after_smoothing(self):
        data = generated_session()
        p, _ = prediction.smooth_targets(data['fr'])
        job = next(j for j in prediction.iter_jobs(data) if j['field'] == 'time_shuffle' and j['lag_bins'] == 0)
        expected = np.random.RandomState(20).permutation(p)
        np.testing.assert_array_equal(job['y'], expected[job['time_indices']])

    def test_pooled_predictions_have_no_query_targets_and_complete_support(self):
        x = np.arange(12.).reshape(6, 2)
        y = (2 * x[:, 0] + 3)[:, None]
        job = {'x': x, 'y': y, 'qid': np.array([3., 3., 5., 5., 9., 9.]), 'time_indices': np.arange(6),
               'session': 'p1_1', 'field': 'population', 'family': 'context', 'layer': 5, 'lag_index': 17, 'lag_bins': -3}
        calls, sink = [], []
        def predict(train_x, train_y, query_x, context):
            self.assertNotIn('targets', context)
            self.assertTrue(np.all(context['train_qid'] != context['held_qid']))
            calls.append(context)
            return (2 * query_x[:, 0] + 3)[:, None]
        r, used = prediction.predict_job(job, predict, remaining_requests=3, sink=sink.append)
        np.testing.assert_allclose(r, [1.]); self.assertEqual(used, 3)
        np.testing.assert_array_equal(sink[0]['predictions'], y)
        self.assertEqual(len(calls), 3)

    def test_request_budget_and_invalid_predictions_fail(self):
        job = next(prediction.iter_jobs(generated_session()))
        with self.assertRaisesRegex(ValueError, 'allocation'):
            prediction.predict_job(job, lambda *a: self.fail('must not call'), remaining_requests=0, sink=lambda r: None)
        with self.assertRaisesRegex(ValueError, 'predictions'):
            prediction.predict_job(job, lambda *a: np.array([np.nan]), remaining_requests=100, sink=lambda r: None)

    def test_undefined_correlations_remain_nan_and_pooled_not_fold_mean(self):
        self.assertTrue(np.isnan(prediction.pooled_pearson(np.ones((6, 1)), np.ones((6, 1)))).all())
        y = np.arange(6.)[:, None]; p = np.array([2, 1, 0, 5, 4, 3.])[:, None]
        r = prediction.pooled_pearson(y, p)[0]
        self.assertAlmostEqual(r, np.corrcoef(p[:, 0], y[:, 0])[0, 1])
        self.assertGreater(r, -1)  # Each three-row fold separately has r=-1.

    def test_actual_complete_session_callback_produces_all_source_shapes(self):
        data = generated_session()
        selected = []
        def predict(train_x, train_y, query_x, context):
            return np.repeat(query_x[:, :1], train_y.shape[1], axis=1)
        def retain(record):
            if record['field'] == 'population' and record['layer'] == 5 and record['lag_bins'] == -3:
                selected.append(record)
        fields, receipt = prediction.compute_session(data, predict, max_requests=20000, sink=retain)
        self.assertEqual(receipt['jobs'], 4209)
        self.assertEqual(len(fields), 16)
        self.assertEqual(fields['unit'].shape, (2, 40, 33))
        self.assertEqual(fields['random_token'].shape, (33,))
        self.assertEqual(fields['sem_syn'].shape, (3, 1))
        self.assertEqual(len(selected), 1)
        expected = np.corrcoef(selected[0]['predictions'][:, 0], selected[0]['targets'][:, 0])[0, 1]
        self.assertAlmostEqual(fields['population'][17, 5], expected)

    def test_source_reference_refuses_unmatched_runtime_before_estimator(self):
        with patch.dict(sys.modules, {'sklearn': types.SimpleNamespace(__version__='0'),
                                     'scipy': types.SimpleNamespace(__version__='0')}):
            with self.assertRaisesRegex(ValueError, 'Historical source'):
                prediction.source_ridge_predictor()


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.root = Path(self.temp.name).resolve()
        self.fixture = GeneratedArchives(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_complete_session_and_separate_original_weight_counts(self):
        with self.fixture.open() as reader:
            data = reader.load_session('p1_1'); weights = reader.population_weights()
            np.testing.assert_array_equal(data['fr'], self.fixture.data['fr'])
            np.testing.assert_array_equal(data['qid'], [0, 99999, 1])
            self.assertEqual(weights['rows'][0]['count'], 3)
            self.assertEqual(data['fr'].shape[1], 2)
            self.assertFalse(weights['rows'][0]['receipt']['array_values_decoded'])
            self.assertEqual(len(data['input_receipts']), 13)

    def test_late_metadata_failure_precedes_all_member_reads(self):
        meta = copy.deepcopy(self.fixture.meta)
        meta['members'][list(meta['members'])[-1]]['crc32'] = '00000000'
        with patch.object(inputs.ArchiveInputs, 'read_member', side_effect=AssertionError('must not read')):
            with self.assertRaisesRegex(ValueError, 'member binding'):
                self.fixture.open(metadata=meta)

    def test_wrong_archive_checksum_and_incomplete_archive_set(self):
        meta = copy.deepcopy(self.fixture.meta); meta['archives']['DNN.zip']['checksum'] = 'md5:' + '0' * 32
        with self.assertRaisesRegex(ValueError, 'checksum'):
            self.fixture.open(metadata=meta)
        with self.assertRaisesRegex(ValueError, 'archive set'):
            inputs.ArchiveInputs({}, read_limit=1000, working_limit=1000, metadata=self.fixture.meta)

    def test_read_and_working_allocations_are_enforced(self):
        with self.assertRaisesRegex(ValueError, 'allocation'):
            self.fixture.open(read_limit=1)
        with self.fixture.open(working_limit=1024) as reader:
            with self.assertRaisesRegex(ValueError, 'working allocation'):
                reader.load_session('p1_1')
        with self.fixture.open() as reader:
            reader.read_limit = reader.charged
            with self.assertRaisesRegex(ValueError, 'allocation'):
                reader.population_weights()

    def test_mutated_archive_is_refused_after_authentication(self):
        with self.fixture.open() as reader:
            with self.fixture.paths['DNN.zip'].open('ab') as stream:
                stream.write(b'x')
            with self.assertRaisesRegex(ValueError, 'changed'):
                reader.load_session('p1_1')

    def test_symlink_archive_refused(self):
        path = self.fixture.paths['DNN.zip']; link = self.root / 'link.zip'; link.symlink_to(path)
        self.fixture.paths['DNN.zip'] = link
        with self.assertRaisesRegex(ValueError, 'symlink'):
            self.fixture.open()

    def test_weight_header_shape_and_numeric_extent_refused(self):
        with self.fixture.open() as reader:
            original = reader.read_member
            def malformed(name, **kw):
                return npy(np.ones((3, 3, 79))) if kw.get('header_only') else original(name, **kw)
            with patch.object(reader, 'read_member', side_effect=malformed):
                with self.assertRaisesRegex(ValueError, 'geometry'):
                    reader.population_weights()
        raw = npy(np.ones((3, 4)))
        expected = {'shape': [3, 4], 'dtype': 'float64', 'fortran_order': False}
        with self.assertRaisesRegex(ValueError, 'extent'):
            inputs.decode_numeric(raw + b'extra', expected)
        with self.assertRaisesRegex(ValueError, 'float64'):
            inputs.npy_header(npy(np.ones((2, 2), dtype=np.int64)))

    def test_preparation_runs_all_inputs_without_predictor_or_fit(self):
        with self.fixture.open() as reader, patch.object(prediction, 'source_ridge_predictor', side_effect=AssertionError('no fit')):
            result = workflow.prepare_inventory(reader)
        self.assertEqual(result['models_fitted'], 0)
        self.assertFalse(result['scientific_qualification'])
        self.assertEqual(len(result['sessions']), 1)
        self.assertEqual(len(result['sessions'][0]['input_receipts']), 13)


class IntegrationTests(unittest.TestCase):
    def test_preparation_cli_imports_in_isolated_mode_without_payload(self):
        result = subprocess.run([sys.executable, '-I', '-B', str(Path(workflow.__file__)), '--help'],
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--data-archive', result.stdout)

    def weights(self, sessions):
        return {'schema': 'language-original-population-weights/v1', 'rows': [
            {'session': s, 'count': i + 1, 'shape': [i + 1, 2, 80],
             'member': f'data_processed/{s}/self_FR_aligned2word.npy',
             'receipt': {'full_member_crc_verified': True, 'array_values_decoded': False, 'sha256': '0' * 64}}
            for i, s in enumerate(sessions)]}

    def test_weighted_population_uses_native_counts_and_primary_stays_equal_session(self):
        sp, _ = inputs.reducer()
        panel = {s: {f: np.full(shape, (i + 1) / 20) for f, shape in sp.shapes(s).items()}
                 for i, s in enumerate(sp.SESSION_UNITS)}
        weights = self.weights(panel); result = workflow.summarize_with_weights(panel, weights)
        values = np.arange(1, 15) / 20; counts = np.arange(1, 15)
        self.assertAlmostEqual(result['figure3b']['population']['mean'], values.mean())
        self.assertAlmostEqual(result['figure3e']['weighted_population_mean'][0][0], np.dot(values, counts / counts.sum()))
        self.assertFalse(result['cohort_identity_status']['cross_representation_unit_join_authenticated'])
        weights['rows'].pop()
        with self.assertRaisesRegex(ValueError, 'roster'):
            workflow.summarize_with_weights(panel, weights)

    def test_complete224_native_files_load_through_existing_reducer(self):
        sp, _ = inputs.reducer(); roster = sp.SESSION_UNITS
        class Reader:
            geometry = dict(roster); charged = 0; archive_receipts = {}
            population_weights = lambda obj: self.weights(roster)
            load_session = lambda obj, session: {'session': session}
        def generated_compute(data, predictor, **kwargs):
            session = data['session']
            fields = {f: np.full(shape, .25) for f, shape in sp.shapes(session).items()}
            return fields, {'sentence_prediction_requests': 1}
        with tempfile.TemporaryDirectory() as temp:
            output = workflow.ExclusiveOutput(Path(temp).resolve() / 'result', byte_limit=12 * 1024**2)
            with patch.object(workflow, 'compute_session', side_effect=generated_compute):
                result = workflow.produce_panel(Reader(), lambda *a: None, output, max_requests=14)
            loaded, receipts = sp.load_panel(output.root / 'result_llm')
            self.assertEqual(len(receipts), 224)
            self.assertEqual(result['prediction_requests'], 14)
            self.assertEqual(result['figure3b']['population']['mean'], .25)
            self.assertTrue((output.root / 'RESULT.json').is_file())
            self.assertEqual(sum(len(r['output_files']) for r in result['prediction_provenance']), 224)

    def test_exclusive_output_and_budget_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            output = workflow.ExclusiveOutput(Path(temp).resolve() / 'out', byte_limit=5)
            output.write('a', b'123')
            with self.assertRaisesRegex(ValueError, 'allocation'):
                output.write('b', b'123')
            with self.assertRaisesRegex(ValueError, 'Fresh'):
                output.write('a', b'x')
            with self.assertRaises(FileExistsError):
                workflow.ExclusiveOutput(output.root, byte_limit=5)

    def test_output_parent_symlink_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            output = workflow.ExclusiveOutput(root / 'out', byte_limit=100)
            (output.root / 'escape').symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                output.write('escape/forbidden', b'x')
            self.assertFalse((root / 'forbidden').exists())

    def test_nested_output_symlink_refused_before_directory_creation(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            output = workflow.ExclusiveOutput(root / 'out', byte_limit=100)
            (output.root / 'alias').symlink_to(root, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                output.write('alias/newdir/forbidden', b'x')
            self.assertFalse((root / 'newdir').exists())

    def test_prediction_trace_covers_targets_predictions_and_support(self):
        job = next(prediction.iter_jobs(generated_session()))
        a, b = workflow.PredictionDigestSink(), workflow.PredictionDigestSink()
        prediction.predict_job(job, lambda x, y, q, c: np.zeros((len(q), y.shape[1])), remaining_requests=100, sink=a)
        prediction.predict_job(job, lambda x, y, q, c: np.ones((len(q), y.shape[1])), remaining_requests=100, sink=b)
        self.assertNotEqual(a.receipt()['ordered_observation_trace_sha256'], b.receipt()['ordered_observation_trace_sha256'])
        self.assertFalse(a.receipt()['raw_predictions_retained'])


if __name__ == '__main__':
    unittest.main()
