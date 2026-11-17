"""Generated HDF5 controls only; no authentic data or scientific model fitting."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

import h5py

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('n045_nwb_reader', HERE / 'nwb_reader.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)
REPO = HERE.parents[4]


class NativeReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='n045-generated-')
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'invented.nwb'
        self.make_source()

    def make_source(self, aversive=False):
        with h5py.File(self.path, 'w') as h:
            h.create_dataset('/general/subject/subject_id', data='invented-subject')
            times = h.create_dataset('/processing/photometry/photometry_dff/timestamps', data=list(range(51)))
            times.attrs['unit'] = 'seconds'
            data = h.create_dataset('/processing/photometry/photometry_dff/data', data=[i / 10 for i in range(51)])
            data.attrs['unit'] = 'stored dff'
            # Stored samples are the registered target: do not apply NWB conversion.
            data.attrs['conversion'] = 100.0
            data.attrs['offset'] = 99.0
            if aversive:
                root = '/acquisition/photometry_event_times/'
                h.create_dataset(root + 'event_type', data=['cue_on', 'shock_on', 'shock_off', 'cue_off'])
                clock = h.create_dataset(root + 'timestamp', data=[10., 11., 12., 15.])
            else:
                root = '/acquisition/eventLog/'
                h.create_dataset(root + 'event_code', data=[15, 10, 5, 6, 0])
                h.create_dataset(root + 'event_flag', data=[0, 1, 0, 0, 0])
                clock = h.create_dataset(root + 'timestamp', data=[10., 11., 11.2, 12., 50.])
            clock.attrs['unit'] = 'seconds'
        exported_count = 3 if aversive else 4
        self.item = {'path': str(self.path), 'asset_id': 'invented-asset',
                     'expected_source_subject_id': 'invented-subject',
                     'max_samples': 100, 'max_events': 20,
                     'event_layout': 'aversive' if aversive else 'appetitive',
                     'condition': 'FC-45s' if aversive else '60s',
                     'units_verified': True, 'unit_evidence_sha256': 'a' * 64,
                     'event_join_evidence_sha256': 'b' * 64,
                     'expected_units': {'fluorescence': 'stored dff', 'photometry_time': 'seconds', 'event_time': 'seconds'},
                     'event_rows': [{'source_row': i, 'id': 'event-' + str(i), 'trial_id': 'trial-0'}
                                    for i in range(exported_count)],
                     'excluded_event_rows': [{'source_row': exported_count,
                                             'reason': 'cue offset retained in ledger' if aversive else 'session end retained in ledger'}]}
        self.repin()

    def repin(self):
        raw = self.path.read_bytes()
        self.item.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())

    def test_stored_native_values_and_omission_flag_survive(self):
        value, receipt = reader.read_session(self.item)
        self.assertEqual(value['photometry_times'], list(range(51)))
        self.assertEqual(value['photometry_values'], [i / 10 for i in range(51)])
        self.assertEqual(value['events'][1], {'id': 'event-1', 'trial_id': 'trial-0', 'code': 10, 'flag': 1, 'time': 11.})
        self.assertEqual(receipt['source_event_rows'], 5)
        self.assertEqual(receipt['source_row_order'], [0, 1, 2, 3])
        self.assertNotIn('path', receipt)
        self.assertNotIn('photometry_values', receipt)

    def test_aversive_layout_and_explicit_cue_offset_exclusion(self):
        self.make_source(aversive=True)
        value, receipt = reader.read_session(self.item)
        self.assertEqual([x['kind'] for x in value['events']], ['cue', 'shock_on', 'shock_off'])
        self.assertEqual(receipt['source_event_rows'], 4)

    def test_authentication_precedes_hdf5_parsing(self):
        self.path.write_bytes(b'not an HDF5 file')
        self.item['bytes'] = self.path.stat().st_size
        with self.assertRaisesRegex(reader.SourceError, 'digest mismatch'):
            reader.read_session(self.item)

    def test_signal_extent_and_nonfinite_values(self):
        for field, value, message in [('timestamps', 0, 'increasing'), ('data', float('nan'), 'nonfinite')]:
            with self.subTest(field=field):
                self.make_source()
                with h5py.File(self.path, 'r+') as h:
                    h['/processing/photometry/photometry_dff/' + field][1] = value
                self.repin()
                with self.assertRaisesRegex(reader.SourceError, message):
                    reader.read_session(self.item)

    def test_source_row_ledger_cannot_drop_or_duplicate_events(self):
        changes = [lambda x: x['event_rows'].pop(),
                   lambda x: x['event_rows'].append(copy.deepcopy(x['event_rows'][0])),
                   lambda x: x['excluded_event_rows'].clear()]
        for change in changes:
            with self.subTest(change=change):
                item = copy.deepcopy(self.item)
                change(item)
                with self.assertRaises(reader.SourceError):
                    reader.read_session(item)

    def test_required_event_cannot_be_reclassified_as_exclusion(self):
        self.item['event_rows'].pop(1)
        self.item['excluded_event_rows'].append({'source_row': 1, 'reason': 'undesirable outcome'})
        with self.assertRaisesRegex(reader.SourceError, 'required source event excluded'):
            reader.read_session(self.item)

    def test_wrong_units_and_missing_independent_unit_evidence(self):
        for change in (lambda x: x['expected_units'].update(photometry_time='milliseconds'),
                       lambda x: x.update(units_verified=False),
                       lambda x: x.update(unit_evidence_sha256='unknown')):
            item = copy.deepcopy(self.item)
            change(item)
            with self.assertRaises(reader.SourceError):
                reader.read_session(item)

    def test_bounds_subject_shape_and_event_flags(self):
        for updates in ({'max_samples': 10}, {'expected_source_subject_id': 'other'}):
            with self.subTest(updates=updates), self.assertRaises(reader.SourceError):
                reader.read_session(dict(self.item, **updates))
        with h5py.File(self.path, 'r+') as h:
            h['/acquisition/eventLog/event_flag'][1] = 2
        self.repin()
        with self.assertRaisesRegex(reader.SourceError, 'omission flag'):
            reader.read_session(self.item)

    def test_external_and_soft_links_are_not_followed(self):
        for external in (True, False):
            self.make_source()
            with h5py.File(self.path, 'r+') as h:
                del h['/processing/photometry/photometry_dff/data']
                h['/processing/photometry/photometry_dff/data'] = (
                    h5py.ExternalLink('/file-that-must-never-open', '/secret') if external
                    else h5py.SoftLink('/processing/photometry/photometry_dff/timestamps'))
            self.repin()
            with self.subTest(external=external), self.assertRaisesRegex(reader.SourceError, 'nonlocal HDF5'):
                reader.read_session(self.item)

    def test_callable_binds_digest_and_copies_input_manifest(self):
        native_reader = reader._AuthenticatedNWBReader([self.item])
        self.item['event_rows'].clear()
        result = native_reader('invented-asset', self.item['sha256'])
        self.assertEqual(len(result['events']), 4)
        self.assertEqual(len(native_reader.receipts), 1)
        with self.assertRaisesRegex(reader.SourceError, 'binding mismatch'):
            native_reader('invented-asset', 'f' * 64)

    def test_duplicate_asset_or_incompatible_layout(self):
        with self.assertRaises(reader.SourceError):
            reader._AuthenticatedNWBReader([self.item, self.item])
        with self.assertRaises(reader.SourceError):
            reader._AuthenticatedNWBReader([dict(self.item, event_layout='aversive')])

    def test_condition_reinterpretation_rejected_before_read_or_export(self):
        item = dict(self.item, condition='60s-CSminus')
        manifest = self.export_manifest()
        manifest['animals'][0]['condition'] = '600s-bgdmilk'
        # Even an unavailable file cannot mask a prior condition-binding failure.
        item['path'] = '/nonexistent-source-must-not-open.nwb'
        def forbidden_export(*args):
            self.fail('exporter called before complete condition preflight')
        with self.assertRaisesRegex(reader.SourceError, 'condition mismatch'):
            reader.export_authenticated_corpus(manifest, [item], forbidden_export)

    def test_complete_manifest_binding_and_no_target_rescaling(self):
        for mutate in (lambda m: m['animals'][0]['sessions'][0].update(fluorescence_scale=100),
                       lambda m: m['animals'][0]['sessions'][0].update(timestamp_scale=.001),
                       lambda m: m['animals'][0]['sessions'][0].update(expected_source_subject_id='other'),
                       lambda m: m['animals'][0]['sessions'].append(copy.deepcopy(m['animals'][0]['sessions'][0]))):
            manifest = self.export_manifest()
            mutate(manifest)
            with self.subTest(mutate=mutate), self.assertRaises(reader.SourceError):
                reader.export_authenticated_corpus(manifest, [self.item], lambda *args: self.fail('premature exporter'))

    def test_real_shared_exporter_and_trajectory_preparation(self):
        shared = REPO / 'benchmarks/shared/reward-spacing/programme/neural'
        sys.path.insert(0, str(shared))
        from neuro.native_export import export_corpus
        from neuro.prepare import prepare
        corpus = reader.export_authenticated_corpus(self.export_manifest(), [self.item], export_corpus)
        self.assertEqual(corpus['source_receipts'][-1]['schema'], 'authenticated_reward_nwb_read_v1')
        bank = prepare(corpus, 'NEURAL-045')
        self.assertEqual(len(bank['cases']), 1)
        case = bank['cases'][0]
        self.assertEqual(case['signal']['times'], list(range(-7, 30)))
        self.assertEqual(case['target'], [i / 10 for i in range(4, 41)])
        self.assertEqual(case['outcome_stratum'], 'omission')
        self.assertFalse(bank['scientific_qualification'])

    def export_manifest(self):
        shared = REPO / 'benchmarks/shared/reward-spacing/programme/neural'
        with (shared / 'spec/SHARED_SOURCE_CONTRACT.json').open() as stream:
            conditions = [x['source_condition'] for x in json.load(stream)['cohorts']]
        session = {'asset_id': self.item['asset_id'], 'sha256': self.item['sha256'],
                   'biological_join_verified': True, 'expected_source_subject_id': 'invented-subject',
                   'timestamp_scale': 1, 'clock_offset': 0, 'fluorescence_scale': 1,
                   'session_id': 'session-0', 'day': 1, 'duration_seconds': 50., 'max_gap_seconds': 1.1,
                   'history': {'duration_known': True, 'delivered_count_known': True, 'lick_history_known': True},
                   'units_verified': True}
        return {'schema': 'reward_neural_native_export_manifest_v1', 'source_access_authorized': True,
                    'shared_contract_sha256': 'cb50037867459c69ac4399f951c894fd3ea33fd3b10b3feb70885a6ccf7065c1',
                    'synthetic': True, 'corpus_id': 'generated-control', 'qualification': {},
                    'support': {x: {'state': 'source_unscorable', 'reason': 'generated control'} for x in conditions},
                    'animals': [{'biological_id': 'invented-animal', 'aliases': ['invented-subject'],
                                 'condition': '60s', 'sex': 'unknown', 'hardware': 'invented', 'sessions': [session]}]}


if __name__ == '__main__':
    import numpy
    print(json.dumps({'scope': 'invented_HDF5_software_controls', 'numpy': numpy.__version__,
                      'h5py': h5py.__version__, 'authentic_data_reads': 0, 'model_trials': 0}), flush=True)
    unittest.main(verbosity=2)
