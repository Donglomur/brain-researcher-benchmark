"""Generated single-context controls; no authentic inputs or scientific scores."""
import copy
import contextlib
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
import zipfile

import numpy as np

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('context031_preflight', HERE / 'preflight.py')
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
WRITTEN = 0


def encoded(value):
    return (json.dumps(value, allow_nan=False, separators=(',', ':')) + '\n').encode()


def write(path, body):
    global WRITTEN
    path.write_bytes(body)
    WRITTEN += len(body)


def fixture(fold=0, view='baseline'):
    _, endpoint = p.dependencies()
    query = np.array([2, 9, 17], dtype='<i8')
    train = np.array([i for i in range(774) if i not in query], dtype='<i8')
    width = 4 if view == 'baseline' else 6
    values = dict(train_x=np.ones((771, width), dtype='<f8'),
                  train_y=np.ones(771, dtype='<f8'),
                  train_mouse=np.ones(771, dtype='<i8'), train_rowid=train,
                  query_x=np.ones((3, width), dtype='<f8'), query_rowid=query)
    stream = io.BytesIO()
    np.savez(stream, **values)
    data = stream.getvalue()
    manifest = dict(schema='neural031_ordinary_public_view_v1', candidate_id='NEURAL-031',
                    fold=fold, held_mouse=endpoint.MICE[fold], view=view, data=p.pin(data),
                    features=p.COMMON + (['local_coactivity_norm', 'dendrite_coincident_norm']
                                         if view == 'neural' else []),
                    training_mouse_indices=[i for i in range(20) if i != fold],
                    train_rows=771, query_rows=3,
                    training_target='next_day_ratio_with_NaN_unavailable',
                    query_target_or_followup_metadata=False,
                    neural_activity_values_physically_present=view == 'neural',
                    prediction_time='after_complete_Early_recording_for_next_day_size')
    body = encoded(manifest)
    submission = dict(schema='neural031_ordinary_prediction_v1', candidate_id='NEURAL-031',
                      fold=fold, view=view, input_manifest=p.pin(body),
                      rows=[{'row_id': int(row), 'prediction': value}
                            for row, value in zip(query, (0, 1, 2.5))])
    return data, manifest, submission


class PreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data, cls.manifest, cls.submission = fixture()

    @classmethod
    def tearDownClass(cls):
        print(json.dumps({'scope': 'generated only', 'fixture_write_bytes': WRITTEN,
                          'fixture_bytes_after_cleanup': 0, 'authentic_inputs_opened': 0,
                          'models_executed': 0, 'scores_computed': 0}))

    def test_all_folds_and_both_views_accept_zero_and_nonnegative_ratios(self):
        for fold in range(20):
            for view in ('baseline', 'neural'):
                data, manifest, value = fixture(fold, view)
                result = p.validate(data, encoded(manifest), encoded(value))
                self.assertEqual((result['fold'], result['view'], result['request_rows']),
                                 (fold, view, 3))
                self.assertFalse(result['score_computed'])
                self.assertFalse(result['scientific_qualification'])

    def test_every_request_is_required_in_exact_order(self):
        changes = ('missing', 'extra', 'reverse', 'duplicate', 'unknown', 'bool_id')
        for change in changes:
            value = copy.deepcopy(self.submission)
            if change == 'missing': value['rows'].pop()
            elif change == 'extra': value['rows'].append({'row_id': 18, 'prediction': 1})
            elif change == 'reverse': value['rows'].reverse()
            elif change == 'duplicate': value['rows'][1]['row_id'] = 2
            elif change == 'unknown': value['rows'][1]['row_id'] = 8
            else: value['rows'][0]['row_id'] = True
            with self.subTest(change=change), self.assertRaises(ValueError):
                p.validate(self.data, encoded(self.manifest), encoded(value))

    def test_invalid_numeric_predictions_rejected(self):
        for number in (-1, True, '1', None, 10 ** 400):
            value = copy.deepcopy(self.submission)
            value['rows'][1]['prediction'] = number
            with self.subTest(number=str(number)[:30]), self.assertRaises(ValueError):
                p.validate(self.data, encoded(self.manifest), encoded(value))
        body = encoded(self.submission).replace(b'"prediction":1', b'"prediction":1e999')
        with self.assertRaises(ValueError):
            p.validate(self.data, encoded(self.manifest), body)

    def test_wrong_manifest_or_context_refused(self):
        for change in ('fold', 'view', 'pin', 'extra'):
            value = copy.deepcopy(self.submission)
            if change == 'fold': value['fold'] = 1
            elif change == 'view': value['view'] = 'neural'
            elif change == 'pin': value['input_manifest']['sha256'] = '0' * 64
            else: value['targets'] = []
            with self.subTest(change=change), self.assertRaises(ValueError):
                p.validate(self.data, encoded(self.manifest), encoded(value))
        # Semantically equal manifest text still has a different required identity.
        with self.assertRaises(ValueError):
            p.validate(self.data, json.dumps(self.manifest, indent=2).encode(),
                       encoded(self.submission))

    def test_malformed_public_semantics_rejected(self):
        changes = {'held_mouse': 'wrong', 'query_target_or_followup_metadata': True,
                   'neural_activity_values_physically_present': True,
                   'train_rows': 770, 'training_mouse_indices': [True] + list(range(2, 20)),
                   'features': p.COMMON + ['answer'], 'query_rows': True}
        for key, value in changes.items():
            manifest = copy.deepcopy(self.manifest)
            manifest[key] = value
            body = encoded(manifest)
            output = copy.deepcopy(self.submission)
            output['input_manifest'] = p.pin(body)
            with self.subTest(key=key), self.assertRaises(ValueError):
                p.validate(self.data, body, encoded(output))

    def test_duplicate_keys_and_nonstandard_constants_rejected(self):
        original = encoded(self.submission)
        for body in (b'{"schema":0,"schema":1}',
                     original.replace(b'"prediction":1', b'"prediction":NaN')):
            with self.assertRaises(ValueError):
                p.validate(self.data, encoded(self.manifest), body)

    def test_archive_must_match_and_only_integer_identifiers_are_decoded(self):
        with self.assertRaises(ValueError):
            p.validate(self.data + b'x', encoded(self.manifest), encoded(self.submission))
        opened = []
        original = zipfile.ZipFile.open
        def observe(archive, name, *args, **kwargs):
            opened.append(name.filename if isinstance(name, zipfile.ZipInfo) else name)
            return original(archive, name, *args, **kwargs)
        with patch.object(zipfile.ZipFile, 'open', observe), \
                patch.object(np, 'load', side_effect=AssertionError('No whole archive decode')):
            p.validate(self.data, encoded(self.manifest), encoded(self.submission))
        self.assertEqual(opened, ['query_rowid.npy'])

    def test_only_supplied_context_files_and_pinned_sources_are_opened(self):
        bodies = {'data': self.data, 'manifest': encoded(self.manifest),
                  'submission': encoded(self.submission)}
        paths = []
        original = p.read
        def observe(path, cap):
            paths.append(str(path))
            return bodies[str(path)] if str(path) in bodies else original(path, cap)
        with patch.object(p, 'read', observe):
            result = p.run('data', 'manifest', 'submission')
        self.assertEqual(paths[:3], ['data', 'manifest', 'submission'])
        self.assertEqual(len(paths), 5)
        self.assertEqual({Path(x).name for x in paths[3:]}, {'control.py', 'endpoint.py'})
        self.assertEqual(result['private_targets_opened'], 0)
        self.assertEqual(result['other_contexts_opened'], 0)

    def test_changed_dependency_is_not_executed(self):
        with patch.object(p, 'read', return_value=b'raise RuntimeError("must not execute")\n'):
            with self.assertRaisesRegex(ValueError, 'source dependency changed'):
                p.dependencies()

    def test_cli_in_fresh_process_and_malformed_archive_failure(self):
        with tempfile.TemporaryDirectory(prefix='.generated031-preflight-', dir=HERE) as name:
            root = Path(name)
            paths = [root / key for key in ('data.npz', 'manifest.json', 'predictions.json')]
            for path, body in zip(paths, (self.data, encoded(self.manifest), encoded(self.submission))):
                write(path, body)
            command = [sys.executable, '-I', '-B', str(HERE / 'preflight.py'),
                       '--input', str(paths[0]), '--manifest', str(paths[1]),
                       '--submission', str(paths[2])]
            run = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['status'], 'valid_single_context_submission')
            self.assertEqual(run.stderr, '')
            malformed = b'not a zip archive'
            manifest = copy.deepcopy(self.manifest)
            manifest['data'] = p.pin(malformed)
            manifest_body = encoded(manifest)
            output = copy.deepcopy(self.submission)
            output['input_manifest'] = p.pin(manifest_body)
            for path, body in zip(paths, (malformed, manifest_body, encoded(output))):
                write(path, body)
            run = subprocess.run(command, capture_output=True, text=True, timeout=15)
            self.assertEqual(run.returncode, 2)
            self.assertEqual(json.loads(run.stderr)['error_type'], 'BadZipFile')
            self.assertEqual(run.stdout, '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
