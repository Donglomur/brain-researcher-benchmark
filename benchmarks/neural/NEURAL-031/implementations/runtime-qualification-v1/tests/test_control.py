"""Generated-only contract and failure controls; no Docker or authentic data."""
import importlib.util
import contextlib
import errno
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

import numpy as np

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('neural031_fixed_control', HERE / 'control.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
spec = importlib.util.spec_from_file_location('neural031_accepted_endpoint',
                                               HERE.parent / 'ratio-scoring-v1/endpoint.py')
endpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(endpoint)
WRITTEN_BYTES = 0


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


def archive(ids, *, features=4, y=9.0, dtype='<i8'):
    out = io.BytesIO()
    np.savez(out, train_x=np.full((2, features), 999.0), train_y=np.array([y, np.nan]),
             train_mouse=np.array([1, 2], dtype='<i8'), train_rowid=np.array([1000, 1001], dtype='<i8'),
             query_x=np.full((len(ids), features), -33.0), query_rowid=np.array(ids, dtype=dtype))
    return out.getvalue()


def manifest(data, ids, fold=0, view='baseline'):
    return encoded({'schema': 'neural031_ordinary_public_view_v1', 'candidate_id': 'NEURAL-031',
                    'fold': fold, 'view': view, 'data': control.pin(data), 'query_rows': len(ids),
                    'query_target_or_followup_metadata': False})


def write(path, body):
    global WRITTEN_BYTES
    path.write_bytes(body)
    WRITTEN_BYTES += len(body)
    assert WRITTEN_BYTES < 131072


class ControlTests(unittest.TestCase):
    def test_complete_40_outputs_and_unchanged_scorer_missing_policy(self):
        support = {'schema': 'neural031_ordinary_public_support_v1', 'candidate_id': 'NEURAL-031',
                   'folds': [], 'request_rows': 774, 'query_targets_included': False}
        bundle = {'schema': 'neural031_ordinary_submission_bundle_v1', 'candidate_id': 'NEURAL-031',
                  'outputs': []}
        for fold in range(20):
            ids = list(range(fold, 774, 20))
            item = {'fold': fold, 'rowids': ids, 'views': {}}
            for view in ('baseline', 'neural'):
                data = archive(ids, features=4 if view == 'baseline' else 6)
                meta = manifest(data, ids, fold, view)
                item['views'][view] = {'data': control.pin(data), 'manifest': control.pin(meta)}
                bundle['outputs'].append(json.loads(control.predict(data, meta)))
            support['folds'].append(item)
        predictions = endpoint.validate_all(bundle, support)
        self.assertEqual(sum(len(p) for p in predictions.values()), 1548)
        targets = {'schema': 'neural031_ratio_targets_v1', 'candidate_id': 'NEURAL-031',
                   'mice': list(endpoint.MICE), 'rows': []}
        for row in range(1143):
            request, observed = row < 774, row < 731
            targets['rows'].append({'rowid': row, 'mouse': row % 20,
                                    'y': (0.0 if row % 2 else 2.0) if observed else None,
                                    'request': int(request), 'observed': int(observed),
                                    'baseline_new': row % 2, 'compartment': row % 2})
        result = endpoint.grade_validated(predictions, support, targets)
        self.assertEqual(result['primary'], 0.0)
        self.assertEqual(result['macro']['baseline_mae'], 1.0)
        self.assertEqual(result['macro']['neural_mae'], 1.0)
        self.assertEqual(result['macro']['no_change_mae'], 1.0)
        self.assertEqual((result['request_rows'], result['scored_rows'], result['unavailable_rows']), (774, 731, 43))

    def test_training_labels_and_view_features_do_not_change_predictions(self):
        ids = [2, 11, 55]
        a, b = archive(ids, y=0.0), archive(ids, features=6, y=1e250)
        left = json.loads(control.predict(a, manifest(a, ids)))
        right = json.loads(control.predict(b, manifest(b, ids, view='neural')))
        self.assertEqual(left['rows'], right['rows'])
        self.assertEqual(left['rows'], [{'row_id': x, 'prediction': 1.0} for x in ids])

    def test_only_query_member_is_decompressed(self):
        ids = [1, 2, 9]
        data = archive(ids)
        opened = []
        original = zipfile.ZipFile.open
        def record(z, name, *args, **kwargs):
            opened.append(name.filename if isinstance(name, zipfile.ZipInfo) else name)
            return original(z, name, *args, **kwargs)
        with mock.patch.object(zipfile.ZipFile, 'open', record):
            control.predict(data, manifest(data, ids))
        self.assertEqual(opened, ['query_rowid.npy'])

    def test_identity_hash_and_exact_manifest_bytes(self):
        ids = [1, 5]
        data = archive(ids)
        meta = manifest(data, ids) + b' '
        self.assertEqual(json.loads(control.predict(data, meta))['input_manifest'], control.pin(meta))
        changed = bytearray(data); changed[-1] ^= 1
        with self.assertRaises(ValueError): control.predict(bytes(changed), meta)

    def test_invalid_query_dtype_order_count_and_bounds(self):
        for ids, dtype in [([2, 1], '<i8'), ([2, 2], '<i8'), ([-1, 2], '<i8'),
                           ([1, 1143], '<i8'), ([1, 2], '<f8'), ([1, 2], '<i4')]:
            with self.subTest(ids=ids, dtype=dtype):
                data = archive(ids, dtype=dtype)
                with self.assertRaises(ValueError): control.predict(data, manifest(data, ids))
        data = archive([1, 2])
        with self.assertRaises(ValueError): control.predict(data, manifest(data, [1]))

    def test_duplicate_json_and_wrong_context_refused(self):
        ids = [1, 2]; data = archive(ids)
        base = json.loads(manifest(data, ids))
        for key, value in [('fold', True), ('fold', 20), ('query_rows', True),
                           ('query_target_or_followup_metadata', True), ('view', 'test')]:
            wrong = dict(base); wrong[key] = value
            with self.subTest(key=key, value=value):
                with self.assertRaises(ValueError): control.predict(data, encoded(wrong))
        duplicate = manifest(data, ids).rstrip()[:-1] + b',"view":"baseline"}'
        with self.assertRaises(ValueError): control.predict(data, duplicate)

    def test_duplicate_extra_and_oversized_query_member_refused(self):
        ids = [1, 2]; original = archive(ids)
        for name, body in [('query_rowid.npy', b'x'), ('extra.npy', b'x')]:
            output = io.BytesIO()
            with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(output, 'w') as dest:
                for info in source.infolist(): dest.writestr(info, source.read(info))
                # Suppress only Python's expected duplicate-member warning.
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore', UserWarning)
                    dest.writestr(name, body)
            data = output.getvalue()
            with self.assertRaises(ValueError): control.predict(data, manifest(data, ids))
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(original)) as source, zipfile.ZipFile(output, 'w') as dest:
            for info in source.infolist():
                dest.writestr(info.filename, b'x' * 16385 if info.filename == 'query_rowid.npy' else source.read(info))
        data = output.getvalue()
        with self.assertRaises(ValueError): control.predict(data, manifest(data, ids))

    def test_main_original_arguments_and_exclusive_output_without_host_probe(self):
        global WRITTEN_BYTES
        ids = [2, 8, 17]; data = archive(ids); meta = manifest(data, ids)
        with tempfile.TemporaryDirectory(prefix='neural031-control-generated-') as temp:
            root = Path(temp)
            write(root / 'data.npz', data); write(root / 'manifest.json', meta)
            argv = ['--input', str(root / 'data.npz'),
                    '--manifest', str(root / 'manifest.json'), '--output', str(root / 'predictions.json')]
            stdout = io.StringIO()
            with mock.patch.object(control, 'runtime_probe', return_value={'generated_mock': True}) as probe:
                with contextlib.redirect_stdout(stdout): self.assertEqual(control.main(argv), 0)
            self.assertEqual(probe.call_count, 1)
            self.assertEqual(json.loads(stdout.getvalue()), {'generated_mock': True})
            body = (root / 'predictions.json').read_bytes(); WRITTEN_BYTES += len(body)
            self.assertEqual(body, control.predict(data, meta))
            self.assertEqual((root / 'predictions.json').stat().st_mode & 0o777, 0o600)
            with mock.patch.object(control, 'runtime_probe', return_value={'generated_mock': True}):
                with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(FileExistsError):
                    control.main(argv)
            self.assertEqual((root / 'predictions.json').read_bytes(), body)

    def probe_mocks(self, *, marker=False, output=None, uid=65534, network_errno=errno.ENETUNREACH,
                    allow_write=False):
        stack = contextlib.ExitStack()
        stack.enter_context(mock.patch.object(control.os, 'getuid', return_value=uid))
        stack.enter_context(mock.patch.object(control.os, 'getgid', return_value=65534))
        stack.enter_context(mock.patch.object(control.os.path, 'lexists', return_value=marker))
        stack.enter_context(mock.patch.object(control.os, 'listdir', return_value=[] if output is None else output))
        opened = []
        def open_generated(path, flags, mode=0o600):
            opened.append((path, flags))
            if path == '/tmp/n031-fixed-control-freshness' or allow_write: return 100
            raise OSError(errno.EROFS, 'generated read-only denial')
        stack.enter_context(mock.patch.object(control.os, 'open', side_effect=open_generated))
        stack.enter_context(mock.patch.object(control.os, 'close'))
        connection = mock.MagicMock()
        connection.__enter__.return_value = connection
        connection.connect.side_effect = (OSError(network_errno, 'generated network denial')
                                          if network_errno is not None else None)
        stack.enter_context(mock.patch.object(control.socket, 'socket', return_value=connection))
        stack.enter_context(mock.patch.object(control.platform, 'python_version', return_value='3.12.8'))
        stack.enter_context(mock.patch.object(control.np, '__version__', '2.2.6'))
        return stack, opened, connection

    def test_fixed_probe_reports_only_runtime_metadata_with_nondestructive_open_flags(self):
        stack, opened, connection = self.probe_mocks()
        with stack: result = control.runtime_probe()
        self.assertEqual(result['uid'], 65534)
        self.assertEqual((result['python'], result['numpy']), ('3.12.8', '2.2.6'))
        self.assertTrue(result['fresh_tmp_marker_before_creation'])
        self.assertTrue(result['empty_output_before_prediction'])
        self.assertEqual(result['write_denial_errnos'], dict.fromkeys(['root', 'data', 'manifest', 'program'], errno.EROFS))
        self.assertEqual(result['network_denial_errno'], errno.ENETUNREACH)
        self.assertLessEqual(len(encoded(result)), 4096)
        self.assertEqual(len(opened), 5)
        for path, flags in opened:
            self.assertFalse(flags & os.O_TRUNC)
            if path.startswith('/input/') or path.startswith('/program/'):
                self.assertFalse(flags & os.O_CREAT)
        connection.settimeout.assert_called_once_with(0.25)
        connection.connect.assert_called_once_with(('192.0.2.1', 9))

    def test_probe_rejects_nonfresh_identity_and_successful_access(self):
        cases = [{'marker': True}, {'output': ['old.json']}, {'uid': 0}, {'allow_write': True},
                 {'network_errno': None}, {'network_errno': errno.ECONNREFUSED}, {'network_errno': errno.ETIMEDOUT}]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs):
                stack, _, _ = self.probe_mocks(**kwargs)
                with stack, self.assertRaises(ValueError): control.runtime_probe()

    def test_regular_bounded_input_and_symlink_refusal(self):
        with tempfile.TemporaryDirectory(prefix='neural031-control-generated-') as temp:
            root = Path(temp)
            write(root / 'input', b'1234')
            self.assertEqual(control.read(root / 'input', 4), b'1234')
            with self.assertRaises(ValueError): control.read(root / 'input', 3)
            (root / 'link').symlink_to(root / 'input')
            with self.assertRaises(OSError): control.read(root / 'link', 4)
            with self.assertRaises(ValueError): control.predict(b'x' * (control.DATA_CAP + 1), b'{}')


if __name__ == '__main__':
    try:
        unittest.main(verbosity=2)
    finally:
        print(json.dumps({'generated_fixture_cumulative_write_bytes': WRITTEN_BYTES,
                          'fixture_write_cap': 131072, 'authentic_payload_reads': 0,
                          'Docker_calls': 0, 'model_fits': 0}), file=sys.stderr)
