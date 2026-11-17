"""Generated controls only; no original archive or response data is opened."""
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import census as c


def fixtures():
    n, w, u = 96, 8, 3
    timing = np.array([[.1, 1.], [1.1, 2.], [2.1, 3.], [3.1, 4.],
                       [4.1, 5.], [5.1, 6.], [6.1, 7.], [7.1, 8.]])
    qid = np.array([1., 1., 2., 2., 3., 3., 4., 4.])
    speaker = np.ones(n, dtype=np.uint8)
    speaker[14:18] = 0
    keep = {'sem_syn': np.array([1, 0, 1, 1, 1, 1, 1, 1], dtype=bool),
            'word2vec': np.array([1, 1, 1, 1, 0, 1, 1, 1], dtype=bool)}
    geometry = {'id': 'p1_1', 'time_bins': n, 'units': u, 'word_rows': w}
    return geometry, timing, qid, speaker, keep


def reference_session():
    g, timing, qid, speaker, keep = fixtures()
    source = c.load_source()
    spec = importlib.util.spec_from_file_location('original_census_prediction_oracle', c.INPUTS / 'prediction.py')
    prediction = importlib.util.module_from_spec(spec)
    old = sys.modules.get('inputs')
    try:
        sys.modules['inputs'] = source
        spec.loader.exec_module(prediction)
    finally:
        if old is None:
            sys.modules.pop('inputs', None)
        else:
            sys.modules['inputs'] = old
    session = {'session': g['id'], 'fr': np.arange(g['time_bins'] * g['units'], dtype=float).reshape(-1, g['units']) ** 2,
               'speaker': speaker.astype(float)[:, None], 'timing': timing, 'qid': qid}
    for f in source.FAMILIES:
        layers = 1 if f in ('sem_syn', 'word2vec', 'syn') else 33
        session[f] = np.arange(g['word_rows'] * 30 * layers, dtype=float).reshape(g['word_rows'], 30, layers)
        if f in keep:
            session[f][~keep[f], 0, 0] = np.nan
    return prediction, session


def generated_archives(root):
    g, timing, qid, speaker, keep = fixtures()
    source = c.load_source()
    by_archive = {k: {} for k in ('data_processed.zip', 'DNN.zip', 'transcription.zip')}
    def npy(a):
        b = io.BytesIO(); np.save(b, a, allow_pickle=False); return b.getvalue()
    by_archive['data_processed.zip'][f"data_processed/{g['id']}/speaker_matrix.npy"] = npy(speaker.astype(float)[:, None])
    for f in keep:
        value = np.arange(g['word_rows'] * 30, dtype=float).reshape(g['word_rows'], 30)
        value[~keep[f], 0] = np.nan
        by_archive['DNN.zip'][source.feature_member(g['id'], f)] = npy(value)
    text = 'start_time,end_time,qid\n' + ''.join(f'{a},{b},{q}\n' for (a, b), q in zip(timing, qid))
    by_archive['transcription.zip'][f"transcription/cleaned/{g['id']}.csv"] = text.encode()
    meta, paths, receipts = {'sessions': [g], 'archives': {}, 'members': {}}, {}, {}
    ranges = {'archives': {}, 'members': {}}
    for archive, members in by_archive.items():
        path = root / archive
        with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, raw in members.items():
                z.writestr(name, raw)
        paths[archive] = path
        meta['archives'][archive] = {'size': path.stat().st_size}
        ranges['archives'][archive] = {'size': path.stat().st_size, 'allowed_ranges': [[0, path.stat().st_size]]}
        with zipfile.ZipFile(path) as z:
            for name, raw in members.items():
                info = z.getinfo(name)
                row = {'archive': archive, 'bytes': len(raw), 'compressed_bytes': info.compress_size,
                       'crc32': f'{info.CRC:08x}'}
                if name.endswith('.npy'):
                    shape, fortran, dtype, _ = source.npy_header(raw)
                    row.update(shape=list(shape), fortran_order=fortran, dtype=str(dtype))
                meta['members'][name] = row
                receipts[name] = {'archive': archive, 'bytes': len(raw), 'crc32': row['crc32'],
                                  'sha256': hashlib.sha256(raw).hexdigest(), 'full_member_crc_verified': True}
                ranges['members'][name] = {**{k: row[k] for k in ('archive', 'bytes', 'compressed_bytes', 'crc32')},
                                           'header_offset': info.header_offset, 'expected_full_member_sha256': hashlib.sha256(raw).hexdigest()}
    return meta, paths, {'sessions': [{'input_receipts': receipts}]}, ranges


class CensusControls(unittest.TestCase):
    def census(self, *args, **kwargs):
        return c.session_census(*args, response_member_sha256='1' * 64, **kwargs)

    def test_complete_4209_jobs_match_original_support_and_response_lineage(self):
        g, timing, qid, speaker, keep = fixtures()
        report = self.census(g, timing, qid, speaker, keep)
        groups = {(r['field'], r['lag_index']): r for r in report['field_lag_groups']}
        prediction, session = reference_session()
        p, units = prediction.smooth_targets(session['fr'])
        total = 0
        for job in prediction.iter_jobs(session):
            row = groups[job['field'], job['lag_index']]
            expected = report['support_classes'][row['support_class']]
            np.testing.assert_array_equal(np.unique(job['qid']), expected['held_qids'])
            self.assertEqual(c.array_sha(job['time_indices'].astype('<i8')), expected['signature']['ordered_time_indices_sha256'])
            self.assertEqual(c.array_sha(job['qid'].astype('<f8')), expected['signature']['ordered_qid_sha256'])
            base = units if job['field'] == 'unit' else p
            rows = job['time_indices'] + min(job['lag_bins'], 0)
            pad = rows < 0
            if job['field'] == 'time_shuffle' or job['field'].endswith('_shuffle'):
                base = np.random.RandomState(20).permutation(base)
            y = base[np.maximum(rows, 0)].copy(); y[pad] = 0
            np.testing.assert_array_equal(y, job['y'])
            total += len(np.unique(job['qid']))
        self.assertEqual(report['jobs'], 4209)
        self.assertEqual(len(groups), 145)
        self.assertEqual(report['source_requests'], total)

    def test_overlap_sentinel_does_not_erase_prior_qid(self):
        source, _ = reference_session()
        timing = np.array([[0., 1.], [.2, .8], [.4, .6]])
        qid = np.array([1., 99999., 2.])
        expected = source.format_words(timing, qid, np.ones((3, 30)), 96)[1]
        np.testing.assert_array_equal(c.label_timeline(timing, qid, 96), expected)
        self.assertEqual(expected[3], 1.)
        self.assertEqual(expected[4], 2.)

    def test_positive_lag_retains_original_zero_qid_padding(self):
        g, timing, qid, speaker, keep = fixtures()
        report = self.census(g, timing, qid, speaker, keep)
        row = next(r for r in report['field_lag_groups'] if r['field'] == 'population' and r['lag_bins'] == 19)
        self.assertIn(0., report['support_classes'][row['support_class']]['held_qids'])

    def test_equivalence_requires_target_kind_shuffle_lag_and_support(self):
        g, timing, qid, speaker, keep = fixtures()
        report = self.census(g, timing, qid, speaker, keep)
        rows = {(r['field'], r['lag_bins']): r['support_class'] for r in report['field_lag_groups']}
        self.assertEqual(rows['population', -10], rows['random_token', -10])
        self.assertEqual(rows['population', -10], rows['ngram10', -10])
        self.assertNotEqual(rows['population', -10], rows['time_shuffle', -10])
        self.assertNotEqual(rows['population', -10], rows['unit', -10])
        self.assertNotEqual(rows['population', -10], rows['population', -9])
        self.assertNotEqual(rows['sem_syn', -1], rows['word2vec', -1])
        self.assertFalse(report['feature_jobs_may_be_combined'])
        self.assertLess(report['proven_class_held_units'], report['source_requests'])

    def test_cost_formula_matches_actual_callback_array_payloads(self):
        g, timing, qid, speaker, keep = fixtures()
        report = self.census(g, timing, qid, speaker, keep)
        prediction, session = reference_session()
        actual = 0
        for job in prediction.iter_jobs(session):
            for q in np.unique(job['qid']):
                train, query = job['qid'] != q, job['qid'] == q
                actual += sum(a.nbytes for a in (job['x'][train], job['y'][train], job['x'][query],
                              job['time_indices'][train], job['time_indices'][query], job['qid'][train]))
        self.assertEqual(actual, report['costs']['request_array_payload_bytes'])

    def test_masks_and_source_lineage_fail_closed(self):
        g, timing, qid, speaker, keep = fixtures()
        with self.assertRaises(ValueError):
            self.census(g, timing, qid, speaker, {'sem_syn': keep['sem_syn']})
        with self.assertRaises(ValueError):
            c.session_census(g, timing, qid, speaker, keep, response_member_sha256='unknown')
        qid[:] = 1
        with self.assertRaises(ValueError):
            self.census(g, timing, qid, speaker, keep)

    def test_compact_roster_retains_counts_and_binds_private_reconstruction(self):
        row = self.census(*fixtures())
        expected = {key: (c.array_sha(np.asarray(v['held_qids'], dtype='<f8')),
                          c.array_sha(np.asarray(v['query_rows'], dtype='<i8')))
                    for key, v in row['support_classes'].items()}
        requests, units = row['source_requests'], row['proven_class_held_units']
        c.compact_rosters(row)
        self.assertEqual((row['source_requests'], row['proven_class_held_units']), (requests, units))
        self.assertEqual(sum(v['held_roster']['count'] for v in row['support_classes'].values()), units)
        for key, value in row['support_classes'].items():
            self.assertNotIn('held_qids', value)
            self.assertEqual((value['held_roster']['held_qid_sha256'], value['held_roster']['query_counts_sha256']), expected[key])

    def test_complete_authenticated_selected_member_reader(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            meta, paths, preparation, ranges = generated_archives(Path(name))
            r = c.SupportReader(paths, preparation, archive_read_limit=65536, expanded_limit=65536, metadata=meta, ranges=ranges)
            try:
                actual = r.session(meta['sessions'][0])
                expected = fixtures()[1:]
                for a, b in zip(actual[:3], expected[:3]):
                    np.testing.assert_array_equal(a, b)
                for key in actual[3]:
                    np.testing.assert_array_equal(actual[3][key], expected[3][key])
                self.assertEqual(len(r.receipts), 4)
                self.assertGreater(r.budget.used, 0)
                self.assertEqual(r.expanded, sum(m['bytes'] + 1 for m in meta['members'].values()))
                with self.assertRaises(ValueError):
                    r.member('data_processed/p1_1/fr_matrix.npy')
                with self.assertRaises(ValueError):
                    r.session(meta['sessions'][0])
            finally:
                r.close()

    def test_member_mismatch_and_expanded_cap_precede_numeric_use(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            meta, paths, preparation, ranges = generated_archives(Path(name))
            member = next(iter(preparation['sessions'][0]['input_receipts']))
            preparation['sessions'][0]['input_receipts'][member]['sha256'] = '0' * 64
            ranges['members'][member]['expected_full_member_sha256'] = '0' * 64
            r = c.SupportReader(paths, preparation, archive_read_limit=65536, expanded_limit=65536, metadata=meta, ranges=ranges)
            try:
                with self.assertRaises(ValueError):
                    r.member(member)
            finally:
                r.close()
            r = c.SupportReader(paths, preparation, archive_read_limit=65536, expanded_limit=1, metadata=meta, ranges=ranges)
            try:
                with self.assertRaises(ValueError):
                    r.member(member)
                self.assertEqual(r.expanded, 0)
            finally:
                r.close()

    def test_archive_read_limit_counts_repeated_seek_reads(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            path = Path(name) / 'bytes'; path.write_bytes(b'0123456789')
            budget = c.ReadBudget(12)
            view = c.ArchiveView(path, 10, budget, [[0, 10]])
            try:
                self.assertEqual(view.read(6), b'012345')
                view.seek(0)
                self.assertEqual(view.read(6), b'012345')
                with self.assertRaises(ValueError):
                    view.read(1)
                self.assertEqual(budget.used, 12)
            finally:
                view.stream.close()

    def test_archive_replacement_and_symlink_rejected(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root = Path(name); path = root / 'bytes'; path.write_bytes(b'0123')
            link = root / 'link'; link.symlink_to(path)
            with self.assertRaises(ValueError):
                c.ArchiveView(link, 4, c.ReadBudget(10), [[0, 4]])
            view = c.ArchiveView(path, 4, c.ReadBudget(10), [[0, 4]])
            try:
                path.unlink(); path.write_bytes(b'0123')
                with self.assertRaises(ValueError):
                    view.stable()
            finally:
                view.stream.close()

    def test_private_output_freshness_cumulative_limit_and_modes(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            root = Path(name) / 'output'
            out = c.PrivateOutput(root, 6)
            out.write('private-support/x', b'abc')
            self.assertEqual((root / 'private-support/x').stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                out.write('private-support/x', b'abc')
            with self.assertRaises(ValueError):
                out.write('overflow', b'1234')
            self.assertFalse((root / 'overflow').exists())
            with self.assertRaises(FileExistsError):
                c.PrivateOutput(root, 6)
            self.assertEqual(out.used, 3)

    def test_selected_ranges_refuse_cross_boundary_read_before_io(self):
        with tempfile.TemporaryDirectory(dir=HERE) as name:
            path = Path(name) / 'bytes'; path.write_bytes(b'0123456789')
            budget = c.ReadBudget(30)
            view = c.ArchiveView(path, 10, budget, [[0, 3], [7, 10]])
            try:
                self.assertEqual(view.read(3), b'012')
                with self.assertRaises(ValueError):
                    view.read(1)
                self.assertEqual(budget.used, 3)
                view.seek(2)
                with self.assertRaises(ValueError):
                    view.read(6)
                self.assertEqual(view.tell(), 2)
                self.assertEqual(budget.used, 3)
                view.seek(7)
                self.assertEqual(view.read(), b'789')
            finally:
                view.stream.close()


if __name__ == '__main__':
    unittest.main()
