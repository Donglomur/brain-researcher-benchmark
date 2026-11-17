import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import packed as p

CONTEXT = dict(session_index=0, field_index=0, layer=0, lag_index=0, lag_bins=-20)
QID = np.array([1., 2., 1., 3., 2., 3.])
TIMES = np.array([2, 3, 5, 8, 13, 21], dtype=np.int64)
REQUESTS = tuple(str(i) * 64 for i in (5, 6, 7))


def raw(value):
    b = io.BytesIO(); np.save(b, value, allow_pickle=False); return b.getvalue()


def closure(request, data):
    return dict(schema='language-private-invocation-closure/v1', request_sha256=request,
                candidate_sha256='2' * 64, provider_source_sha256='4' * 64,
                natural_exit_zero=True, owned_processes_absent=True, private_view_retired=True,
                transport_sha256=p.sha(data))


def writer(root, **kw):
    args = dict(store_sha256='1' * 64, candidate_sha256='2' * 64, schedule_sha256='3' * 64,
                job_context_sha256=p.sha(p.encoded(CONTEXT)), expected_job_contexts=[CONTEXT],
                condition='paper_data', expected_jobs=1, expected_requests=3,
                output_limit=1024 * 1024, working_limit=16 * 1024 * 1024)
    args.update(kw)
    return p.PackedWriter(root, **args)


def begin(w):
    w.begin_job(context=CONTEXT, qid=QID, time_indices=TIMES, outputs=2,
                support_class_sha256='8' * 64, expected_request_hashes=REQUESTS)


def deliver(w):
    for i, q in enumerate((1., 2., 3.)):
        value = np.asfortranarray(np.array([[q, q + .25], [q + .5, q + .75]], dtype='>f4'))
        data = raw(value)
        w.accept(held_qid=q, request_sha256=REQUESTS[i], raw_prediction=data,
                 closure=closure(REQUESTS[i], data))


def complete(root):
    w = writer(root); begin(w); deliver(w)
    values = w.finish_job(); manifest = w.finish()
    return values, manifest


def reader(root, manifest, **kw):
    args = dict(manifest_sha256=p.sha((root / 'MANIFEST.json').read_bytes()),
                bindings={k: manifest[k] for k in ('store_sha256', 'candidate_sha256', 'schedule_sha256',
                                                  'job_context_sha256', 'condition')},
                expected_jobs=1, expected_requests=3, read_limit=1024 * 1024, working_limit=16 * 1024 * 1024)
    args.update(kw)
    return p.PackedReader(root, **args)


def recover(r, **kw):
    args = dict(qid=QID, time_indices=TIMES, expected_context=CONTEXT,
                expected_request_hashes=REQUESTS, support_class_sha256='8' * 64)
    args.update(kw)
    return r.next_job(**args)


class PackedControls(unittest.TestCase):
    def test_noncontiguous_original_rows_and_fixed_records_recover_every_value(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root = Path(name) / 'packed'
            w = writer(root); begin(w); deliver(w)
            matrix = w.finish_job()
            expected = np.array([[1., 1.25], [2., 2.25], [1.5, 1.75],
                                 [3., 3.25], [2.5, 2.75], [3.5, 3.75]])
            np.testing.assert_array_equal(matrix, expected)
            m = w.finish()
            self.assertEqual(set(x.name for x in root.iterdir()),
                             {'PREDICTIONS.f64le', 'REQUESTS.bin', 'JOBS.bin', 'MANIFEST.json'})
            self.assertFalse(m['protected_execution_qualified'])
            self.assertFalse(m['closure_records_independently_verified_by_collector'])
            payload = (root / 'PREDICTIONS.f64le').read_bytes()
            np.testing.assert_array_equal(np.frombuffer(payload, '<f8').reshape(6, 2), expected)
            job = p.JOB.unpack((root / 'JOBS.bin').read_bytes())
            self.assertEqual(job[:7], (0, 0, 3, 6, 2, 0, 96))
            self.assertEqual(job[-4].hex(), p.sha(QID.astype('<f8').tobytes()))
            self.assertEqual(job[-3].hex(), p.sha(TIMES.astype('<i8').tobytes()))
            self.assertEqual(job[-1].hex(), p.sha(payload))
            records = (root / 'REQUESTS.bin').read_bytes()
            for i, q in enumerate((1., 2., 3.)):
                record = p.REQUEST.unpack_from(records, i * 192)
                self.assertEqual(record[:9], (i, 0, 2, 2, 0, 32, q, 4, 1))
                recovered = expected[QID == q].astype('<f8').tobytes()
                self.assertEqual(record[-2].hex(), p.sha(recovered))
                self.assertEqual(record[-4].hex(), REQUESTS[i])
            for path in root.iterdir():
                self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_frozen_schedule_refuses_changed_job_before_allocating(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            w = writer(Path(name) / 'packed')
            try:
                with self.assertRaises(ValueError):
                    w.begin_job(context={**CONTEXT, 'layer': 1}, qid=QID, time_indices=TIMES, outputs=2,
                                support_class_sha256='8' * 64, expected_request_hashes=REQUESTS)
                self.assertIsNone(w.active)
                self.assertEqual(w.reserved, 0)
            finally:
                w.close()

    def test_one_bad_request_poisoned_and_cannot_be_retried(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            w = writer(Path(name) / 'packed'); begin(w)
            data = raw(np.zeros((2, 2)))
            with self.assertRaises(ValueError):
                w.accept(held_qid=2., request_sha256=REQUESTS[1], raw_prediction=data,
                         closure=closure(REQUESTS[1], data))
            self.assertTrue(w.failed)
            with self.assertRaises(ValueError):
                w.accept(held_qid=1., request_sha256=REQUESTS[0], raw_prediction=data,
                         closure=closure(REQUESTS[0], data))
            with self.assertRaises(ValueError):
                w.finish()
            w.close()

    def test_transport_cap_precedes_any_sha(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            w = writer(Path(name) / 'packed'); begin(w)
            with mock.patch.object(p, 'sha', side_effect=AssertionError('hash must not run')):
                with self.assertRaises(ValueError):
                    w.accept(held_qid=1., request_sha256=REQUESTS[0], raw_prediction=b'x' * 9000, closure={})
            self.assertTrue(w.failed); w.close()

    def test_workspace_and_output_reservation_precede_array_scans(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            w = writer(Path(name) / 'packed')
            w.working = 1
            with mock.patch.object(p.np, 'isfinite', side_effect=AssertionError('scan must not run')):
                with self.assertRaises(ValueError):
                    begin(w)
            self.assertEqual(w.reserved, 0)
            w.close()
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            w = writer(Path(name) / 'packed', output_limit=65536)
            with self.assertRaises(ValueError):
                begin(w)
            self.assertEqual(w.reserved, 0); w.close()

    def test_bad_closure_and_unsafe_npy_never_enter_products(self):
        for kind in ('closure', 'nan', 'object', 'trailing'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=HERE) as name:
                w = writer(Path(name) / 'packed'); begin(w)
                value = np.zeros((2, 2))
                if kind == 'nan': value[0, 0] = np.nan
                if kind == 'object': value = np.array([[{}, {}], [{}, {}]], dtype=object)
                if kind == 'object':
                    b = io.BytesIO(); np.save(b, value, allow_pickle=True); data = b.getvalue()
                else: data = raw(value)
                if kind == 'trailing': data += b'X'
                closed = closure(REQUESTS[0], data)
                if kind == 'closure': closed['owned_processes_absent'] = 1
                with self.assertRaises(ValueError):
                    w.accept(held_qid=1., request_sha256=REQUESTS[0], raw_prediction=data, closure=closed)
                self.assertTrue(w.failed)
                self.assertEqual(w.written, 0); w.close()

    def test_write_and_flush_failures_latch_and_preserve_partial_evidence(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            w = writer(Path(name) / 'packed'); begin(w)
            data = raw(np.zeros((2, 2)))
            original = w.streams['REQUESTS.bin']
            class Broken:
                def write(self, raw):
                    original.write(raw[:8]); raise OSError('generated partial write')
                def close(self): original.close()
            w.streams['REQUESTS.bin'] = Broken()
            with self.assertRaises(OSError):
                w.accept(held_qid=1., request_sha256=REQUESTS[0], raw_prediction=data, closure=closure(REQUESTS[0], data))
            self.assertTrue(w.failed)
            with self.assertRaises(ValueError): w.finish()
            w.close()
            self.assertEqual((Path(name) / 'packed/REQUESTS.bin').stat().st_size, 8)
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            w = writer(Path(name) / 'packed'); begin(w); deliver(w); w.finish_job()
            with mock.patch.object(p.os, 'fsync', side_effect=OSError('generated fsync failure')):
                with self.assertRaises(OSError): w.finish()
            self.assertTrue(w.failed)
            self.assertFalse((Path(name) / 'packed/MANIFEST.json').exists())
            with self.assertRaises(ValueError): w.finish()
            w.close()

    def test_incomplete_job_and_incomplete_run_have_no_final_manifest(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root = Path(name) / 'packed'; w = writer(root); begin(w)
            with self.assertRaises(ValueError): w.finish_job()
            with self.assertRaises(ValueError): w.finish()
            self.assertFalse((root / 'MANIFEST.json').exists()); w.close()

    def test_reader_recovers_exact_values_for_unchanged_original_pearson(self):
        # Original module import authenticates source code only; no data fixture
        # is constructed and no original source array is read.
        import test_layout
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root = Path(name) / 'packed'; expected, m = complete(root)
            r = reader(root, m)
            try:
                actual = recover(r)
                np.testing.assert_array_equal(actual, expected)
                target = np.array([[3., 1.], [1., 4.], [2., 5.], [0., 2.], [6., 0.], [4., 3.]])
                np.testing.assert_array_equal(test_layout.ORIGINAL.pooled_pearson(target, actual),
                                              test_layout.ORIGINAL.pooled_pearson(target, expected))
                receipt = r.finish()
                self.assertEqual((receipt['jobs'], receipt['requests']), (1, 3))
                self.assertFalse(receipt['provider_journal_independently_verified'])
            finally:
                r.close()

    def test_reader_rejects_wrong_rows_and_request_identity(self):
        for kind in ('row', 'request', 'class', 'context'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory(dir=HERE) as name:
                root = Path(name) / 'packed'; _, m = complete(root); r = reader(root, m)
                args = {'row': {'time_indices': TIMES + 1}, 'request': {'expected_request_hashes': REQUESTS[::-1]},
                        'class': {'support_class_sha256': '0' * 64}, 'context': {'expected_context': {**CONTEXT, 'layer': 1}}}[kind]
                with self.assertRaises(ValueError): recover(r, **args)
                self.assertTrue(r.failed)
                with self.assertRaises(ValueError): recover(r)
                r.close()

    def test_reader_whole_file_authentication_stability_and_budget(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root = Path(name) / 'packed'; _, m = complete(root)
            with self.assertRaises(ValueError): reader(root, m, read_limit=1)
            path = root / 'PREDICTIONS.f64le'
            before = path.read_bytes(); path.write_bytes(before[:-1] + b'X')
            with self.assertRaises(ValueError): reader(root, m)
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root = Path(name) / 'packed'; _, m = complete(root); r = reader(root, m)
            with (root / 'PREDICTIONS.f64le').open('ab') as stream: stream.write(b'X')
            with self.assertRaises(ValueError): recover(r)
            self.assertTrue(r.failed); r.close()


if __name__ == '__main__':
    unittest.main()
