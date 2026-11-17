"""Generated raw submission/control products; no neural source or model runs."""
import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bridge as impl

CANDIDATE = 'c' * 64


def job():
    x = np.arange(8 * 30, dtype=np.float64).reshape(8, 30) / 100
    return {'session': 'p1_1', 'field': 'unit', 'family': 'context', 'layer': 5,
            'lag_index': 17, 'lag_bins': -3, 'x': x,
            'y': np.column_stack((x[:, 0] + 2, -2 * x[:, 1] + 1)),
            'qid': np.repeat([10., 20., 30., 40.], 2), 'time_indices': np.arange(8, dtype=np.int64) + 100}


def requests(value):
    for label in np.unique(value['qid']):
        train, query = value['qid'] != label, value['qid'] == label
        context = {key: value[key] for key in impl.CONTEXT_KEYS if key != 'held_qid'}
        context.update(held_qid=float(label), train_time_indices=value['time_indices'][train],
                       test_time_indices=value['time_indices'][query], train_qid=value['qid'][train])
        yield value['x'][train], value['y'][train], value['x'][query], context


def submission(root, value, *, mutate_prediction=None, mutate_row=None):
    root.mkdir(); (root / 'predictions').mkdir()
    rows = []
    for i, (tx, ty, qx, context) in enumerate(requests(value)):
        descriptor, request_sha = impl.request_identity(tx, ty, qx, context)
        prediction = np.column_stack((qx[:, 0] + 2, -2 * qx[:, 1] + 1))
        if mutate_prediction:
            prediction = mutate_prediction(i, prediction)
        buffer = io.BytesIO(); np.save(buffer, prediction, allow_pickle=False)
        raw = buffer.getvalue(); relative = f'predictions/{i:09d}.npy'
        (root / relative).write_bytes(raw)
        row = {'ordinal': i, 'request_sha256': request_sha, 'prediction': {'path': relative, **impl.pin(raw)}}
        if mutate_row: mutate_row(i, row)
        rows.append(impl.encoded(row))
    index = b''.join(rows); (root / 'REQUESTS.jsonl').write_bytes(index)
    manifest = {'schema': 'language-original-raw-prediction-submission/v1', 'candidate_sha256': CANDIDATE,
                'condition': 'paper_data', 'requests': impl.pin(index), 'request_count': len(rows)}
    raw = impl.encoded(manifest); (root / 'SUBMISSION.json').write_bytes(raw)
    return impl.pin(raw)['sha256']


def open_submission(root, sha, **kwargs):
    values = dict(manifest_sha256=sha, candidate_sha256=CANDIDATE, condition='paper_data',
                  max_requests=100, read_limit=16 * 1024**2, working_limit=64 * 1024**2)
    values.update(kwargs)
    return impl.Submission(root, **values)


class RawSubmissionTests(unittest.TestCase):
    def test_finish_streams_inventory_and_refuses_extra_prediction_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / 'candidate'; value = job(); sha = submission(root, value)
            with open_submission(root, sha) as frozen:
                for row in requests(value): frozen(*row)
                (root / 'predictions/extra').mkdir()
                with patch.object(impl.os, 'walk', side_effect=AssertionError('must stream')):
                    with self.assertRaises(ValueError): frozen.finish()

    def test_insufficient_read_allocation_refused_before_manifest_open(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            with patch.object(impl, 'read_file', side_effect=AssertionError('must not read')):
                with self.assertRaisesRegex(ValueError, 'before manifest'):
                    open_submission(root, '0' * 64, read_limit=1)

    def test_float32_predictions_keep_raw_identity_and_source_private_scoring(self):
        _, _, workflow, _, _ = impl.load_source()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / 'candidate'; value = job()
            sha = submission(root, value, mutate_prediction=lambda i, a: a.astype(np.float32))
            saved = []
            with open_submission(root, sha) as frozen:
                correlations, used = workflow.compute_session.__globals__['predict_job'](
                    value, frozen, remaining_requests=4, sink=saved.append)
                frozen.finish()
            self.assertEqual(used, 4)
            self.assertEqual(saved[0]['predictions'].dtype, np.float64)
            np.testing.assert_allclose(correlations, [1, 1], rtol=0, atol=1e-12)

    def test_real_source_held_qid_path_scores_predictions_and_retains_private_products(self):
        _, _, workflow, _, _ = impl.load_source()
        predict_job = workflow.compute_session.__globals__['predict_job']
        value = job()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); candidate = root / 'candidate'
            sha = submission(candidate, value)
            output = workflow.ExclusiveOutput(root / 'private', byte_limit=4 * 1024**2)
            sink = impl.PrivateProducts(output, working_limit=64 * 1024**2)
            with open_submission(candidate, sha) as frozen:
                correlations, count = predict_job(value, frozen, remaining_requests=4, sink=sink)
                receipt = frozen.finish()
            np.testing.assert_allclose(correlations, [1., 1.], rtol=0, atol=1e-15)
            self.assertEqual(count, 4); self.assertEqual(receipt['raw_prediction_requests'], 4)
            self.assertFalse(receipt['candidate_code_executed_by_scorer'])
            with np.load(root / 'private/private-products/000000.npz', allow_pickle=False) as saved:
                self.assertEqual(set(saved.files), {'qid', 'time_indices', 'predictions', 'targets', 'correlations'})
                np.testing.assert_array_equal(saved['targets'], value['y'])
                np.testing.assert_array_equal(saved['predictions'], value['y'])
                np.testing.assert_array_equal(saved['qid'], value['qid'])
                for i in range(2):
                    self.assertEqual(np.corrcoef(saved['predictions'][:, i], saved['targets'][:, i])[1, 0], correlations[i])

    def test_changed_query_training_or_row_identity_is_refused(self):
        for kind in ('query', 'train_target', 'row', 'qid', 'layer'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve() / 'candidate'; value = job(); sha = submission(root, value)
                tx, ty, qx, context = next(requests(value))
                if kind == 'query': qx[0, 0] += 1
                if kind == 'train_target': ty[0, 0] += 1
                if kind == 'row': context['test_time_indices'] += 1
                if kind == 'qid': context['held_qid'] = 11.
                if kind == 'layer': context['layer'] += 1
                with open_submission(root, sha) as frozen, self.assertRaises(ValueError):
                    frozen(tx, ty, qx, context)

    def test_swapped_request_and_prediction_file_order_refused(self):
        for kind in ('ordinal', 'path'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve() / 'candidate'; value = job()
                def mutate(i, row):
                    if i == 0:
                        if kind == 'ordinal': row['ordinal'] = 1
                        else: row['prediction']['path'] = '../private.npy'
                sha = submission(root, value, mutate_row=mutate)
                with open_submission(root, sha) as frozen, self.assertRaises(ValueError): frozen(*next(requests(value)))

    def test_nonfinite_or_wrong_shape_predictions_refused(self):
        for kind in ('nan', 'shape'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary).resolve() / 'candidate'; value = job()
                def mutate(i, array):
                    if kind == 'shape': return array[:, :1]
                    array[0, 0] = np.nan; return array
                sha = submission(root, value, mutate_prediction=mutate)
                with open_submission(root, sha) as frozen, self.assertRaises(ValueError): frozen(*next(requests(value)))

    def test_changed_prediction_bytes_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / 'candidate'; value = job(); sha = submission(root, value)
            path = root / 'predictions/000000000.npy'; raw = bytearray(path.read_bytes()); raw[-1] ^= 1; path.write_bytes(raw)
            with open_submission(root, sha) as frozen, self.assertRaisesRegex(ValueError, 'prediction bytes changed'):
                frozen(*next(requests(value)))

    def test_unconsumed_or_extra_submission_products_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / 'candidate'; value = job(); sha = submission(root, value)
            with open_submission(root, sha) as frozen, self.assertRaisesRegex(ValueError, 'Incomplete or extra'):
                frozen.finish()
            with open_submission(root, sha) as frozen:
                for row in requests(value): frozen(*row)
                (root / 'extra').write_text('unreferenced')
                with self.assertRaisesRegex(ValueError, 'Unreferenced'): frozen.finish()

    def test_frozen_identity_condition_and_request_caps_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / 'candidate'; sha = submission(root, job())
            for change in ({'manifest_sha256': '0' * 64}, {'candidate_sha256': '0' * 64},
                           {'condition': 'paper_data_author_code'}, {'max_requests': 3}, {'read_limit': 1}):
                with self.subTest(change=change), self.assertRaises(ValueError): open_submission(root, sha, **change)

    def test_symlink_fifo_and_hardlink_predictions_refused(self):
        for kind in ('symlink', 'fifo', 'hardlink'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as temporary:
                parent = Path(temporary).resolve(); root = parent / 'candidate'; value = job(); sha = submission(root, value)
                path = root / 'predictions/000000000.npy'; moved = parent / 'moved'; path.rename(moved)
                if kind == 'symlink': path.symlink_to(moved)
                elif kind == 'fifo': os.mkfifo(path)
                else: os.link(moved, path)
                with open_submission(root, sha) as frozen, self.assertRaises(ValueError): frozen(*next(requests(value)))


class RequestBoundaryTests(unittest.TestCase):
    def test_partial_session_roster_refused_before_private_source_reads(self):
        class Reader:
            geometry = {'p1_1': {}}
            def population_weights(self): raise AssertionError('must not read')
        with self.assertRaisesRegex(ValueError, 'Complete original14-session'):
            impl.score_complete(Reader(), None, None, max_requests=1, working_limit=1,
                                reference_archive='/does-not-exist', reference_read_limit=1,
                                permutation_budget=900000, numpy_version=np.__version__, scipy_version='unused')

    def test_export_one_fold_excludes_query_targets_and_other_folds(self):
        _, _, workflow, _, _ = impl.load_source()
        tx, ty, qx, context = next(requests(job()))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve() / 'request'
            output = workflow.ExclusiveOutput(root, byte_limit=2 * 1024**2)
            sha = impl.export_request(tx, ty, qx, context, output, working_limit=64 * 1024**2)
            record = json.loads((root / 'REQUEST.json').read_text())
            self.assertEqual(record['request_sha256'], sha)
            self.assertEqual(set(record['files']), {'train_x', 'train_y', 'query_x', 'train_time_indices', 'query_time_indices', 'train_qid'})
            self.assertFalse(record['descriptor']['query_targets_in_request'])
            self.assertFalse((root / 'query_y.npy').exists())
            np.testing.assert_array_equal(np.load(root / 'train_y.npy', allow_pickle=False), ty)
            np.testing.assert_array_equal(np.load(root / 'query_x.npy', allow_pickle=False), qx)

    def test_request_digest_does_not_alias_mutable_context(self):
        tx, ty, qx, context = next(requests(job()))
        descriptor, sha = impl.request_identity(tx, ty, qx, context)
        original = copy.deepcopy(descriptor)
        context['held_qid'] = 99.; context['test_time_indices'][0] = 999
        self.assertEqual(descriptor, original)
        self.assertEqual(impl.pin(impl.encoded(descriptor))['sha256'], sha)

    def test_private_products_and_request_export_admit_limits_before_writes(self):
        _, _, workflow, _, _ = impl.load_source()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            output = workflow.ExclusiveOutput(root / 'public', byte_limit=1)
            with self.assertRaisesRegex(ValueError, 'Reserve complete request'):
                impl.export_request(*next(requests(job())), output, working_limit=64 * 1024**2)
            self.assertEqual(output.files, {})
            output2 = workflow.ExclusiveOutput(root / 'private', byte_limit=1)
            record = {key: np.ones((10, 2)) for key in ('qid', 'time_indices', 'predictions', 'targets', 'correlations')}
            with self.assertRaisesRegex(ValueError, 'Reserve complete private product'):
                impl.PrivateProducts(output2, working_limit=64 * 1024**2)(record)
            self.assertEqual(output2.files, {})

    def test_duplicate_json_keys_and_constants_refused(self):
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}'):
            with self.assertRaises(ValueError): impl.parse(raw)

    def test_isolated_cli_exposes_source_scoring_not_candidate_execution(self):
        run = subprocess.run([sys.executable, '-I', '-B', str(Path(impl.__file__)), '--help'],
                             capture_output=True, text=True, timeout=10)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn('--submission-sha256', run.stdout)
        self.assertIn('--reference-archive', run.stdout)
        self.assertNotIn('--candidate-command', run.stdout)


if __name__ == '__main__': unittest.main()
